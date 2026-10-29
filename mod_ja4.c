/* Standalone Apache httpd 2.4 module; no private mod_ssl structures. */
#include "httpd.h"
#include "http_config.h"
#include "http_log.h"
#include "http_protocol.h"
#include "http_request.h"
#include "apr_optional_hooks.h"
#include "apr_strings.h"
#include "mod_ssl.h"
#include <openssl/ssl.h>
#include <stdlib.h>
#include "ja4.h"

/* Public optional hook from mod_ssl_openssl.h. Some distributions omit that
 * header from apache2-dev, so declare just the interface used here. */
APR_DECLARE_EXTERNAL_HOOK(ssl, SSL, int, pre_handshake,
                         (conn_rec *c, SSL *ssl, int is_proxy))

module AP_MODULE_DECLARE_DATA ja4_module;

typedef struct { const char *fingerprint; const char *raw; int captured; } ja4_conn;

static void observe(int write_p, int version, int content_type,
                    const void *buffer, size_t length, SSL *ssl, void *arg)
{
    conn_rec *c = arg;
    ja4_conn *state = ap_get_module_config(c->conn_config, &ja4_module);
    const unsigned char *message = buffer;
    ja4_result result;
    (void)version; (void)ssl;
    if (write_p || content_type != SSL3_RT_HANDSHAKE || !length ||
        message[0] != SSL3_MT_CLIENT_HELLO || state->captured) return;
    /* Keep the initial ClientHello across HelloRetryRequest / renegotiation. */
    state->captured = 1;
    if (!ja4_compute(message, length, &result)) return;
    state->fingerprint = apr_pstrdup(c->pool, result.fingerprint);
    state->raw = apr_pstrdup(c->pool, result.raw);
    free(result.raw);
}

static int before_handshake(conn_rec *c, SSL *ssl, int is_proxy)
{
    ja4_conn *state;
    if (is_proxy) return DECLINED;
    state = apr_pcalloc(c->pool, sizeof(*state));
    ap_set_module_config(c->conn_config, &ja4_module, state);
    /* Leave mod_ssl's SNI/ClientHello and info callbacks untouched. */
    SSL_set_msg_callback(ssl, observe);
    SSL_set_msg_callback_arg(ssl, c);
    return OK;
}

static int export_fingerprint(request_rec *r)
{
    conn_rec *c = r->connection;
    ja4_conn *state;
    while (c->master) c = c->master;
    state = ap_get_module_config(c->conn_config, &ja4_module);
    if (state && state->fingerprint) {
        apr_table_setn(r->subprocess_env, "JA4", state->fingerprint);
        apr_table_setn(r->subprocess_env, "JA4_RAW", state->raw);
        apr_table_setn(r->notes, "ja4", state->fingerprint);
        apr_table_setn(r->notes, "ja4_raw", state->raw);
    }
    return DECLINED;
}

static int check_ssl(apr_pool_t *p, apr_pool_t *plog, apr_pool_t *ptemp, server_rec *s)
{
    (void)p; (void)plog; (void)ptemp;
    if (!ap_find_linked_module("mod_ssl.c")) {
        ap_log_error(APLOG_MARK, APLOG_ERR, 0, s, "mod_ja4 requires mod_ssl");
        return HTTP_INTERNAL_SERVER_ERROR;
    }
    return OK;
}

static void register_hooks(apr_pool_t *p)
{
    (void)p;
    APR_OPTIONAL_HOOK(ssl, pre_handshake, before_handshake, NULL, NULL, APR_HOOK_LAST);
    ap_hook_post_config(check_ssl, NULL, NULL, APR_HOOK_MIDDLE);
    ap_hook_post_read_request(export_fingerprint, NULL, NULL, APR_HOOK_FIRST);
    ap_hook_fixups(export_fingerprint, NULL, NULL, APR_HOOK_LAST);
}

module AP_MODULE_DECLARE_DATA ja4_module = {
    STANDARD20_MODULE_STUFF,
    NULL, NULL, NULL, NULL, NULL, register_hooks,
#if AP_MODULE_MAGIC_AT_LEAST(20120211, 70)
    AP_MODULE_FLAG_NONE
#endif
};
