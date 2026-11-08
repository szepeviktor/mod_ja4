/* Identical fresh-connection probe for upstream OpenSSL 1.0.2 through 4.x. */
#include <openssl/ssl.h>
#include <openssl/err.h>
#include <stdio.h>
#include <string.h>

int main(int argc, char **argv)
{
    static const unsigned char alpn[] = "\x02h2\x08http/1.1";
    SSL_CTX *ctx;
    BIO *connection;
    SSL *ssl;
    char request[256], response[4096];
    int n, first = 1, ok = 0;

    if (argc != 2) return 1;
#if OPENSSL_VERSION_NUMBER < 0x10100000L
    SSL_library_init();
    SSL_load_error_strings();
    ctx = SSL_CTX_new(SSLv23_client_method());
    printf("%s; %s\n", __VERSION__, SSLeay_version(SSLEAY_VERSION));
#else
    ctx = SSL_CTX_new(TLS_client_method());
    printf("%s; %s\n", __VERSION__, OpenSSL_version(OPENSSL_VERSION));
#endif
    if (!ctx) return 1;
    SSL_CTX_set_verify(ctx, SSL_VERIFY_PEER, NULL);
    if (SSL_CTX_load_verify_locations(ctx, "/fixture/ca.pem", NULL) != 1 ||
        SSL_CTX_set_alpn_protos(ctx, alpn, sizeof(alpn) - 1) != 0) {
        SSL_CTX_free(ctx);
        return 1;
    }
    connection = BIO_new_ssl_connect(ctx);
    if (!connection) { SSL_CTX_free(ctx); return 1; }
    BIO_get_ssl(connection, &ssl);
    if (SSL_set_tlsext_host_name(ssl, "ja4-server") != 1 ||
        X509_VERIFY_PARAM_set1_host(SSL_get0_param(ssl), "ja4-server", 0) != 1)
        goto done;
    BIO_set_conn_hostname(connection, "ja4-server:443");
    if (BIO_do_connect(connection) <= 0 || BIO_do_handshake(connection) <= 0)
        goto done;
    snprintf(request, sizeof(request),
             "GET /%s.txt HTTP/1.1\r\nHost: ja4-server\r\nConnection: close\r\n\r\n", argv[1]);
    if (BIO_write(connection, request, (int)strlen(request)) != (int)strlen(request))
        goto done;
    while ((n = BIO_read(connection, response, sizeof(response))) > 0) {
        if (first) {
            ok = n >= 12 && memcmp(response, "HTTP/1.1 200", 12) == 0;
            first = 0;
        }
    }
done:
    if (!ok) ERR_print_errors_fp(stderr);
    BIO_free_all(connection);
    SSL_CTX_free(ctx);
    return ok ? 0 : 1;
}
