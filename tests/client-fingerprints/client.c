/* Compiled as both C and C++. Only the local test server is contacted. */
#include <openssl/ssl.h>
#include <stdio.h>
#include <string.h>

int main(int argc, char **argv)
{
    SSL_CTX *ctx = SSL_CTX_new(TLS_client_method());
    BIO *connection;
    SSL *ssl;
    char request[256], response[4096];
    int n, first = 1, ok = 0;
    if (!ctx || argc != 2) return 1;
    SSL_CTX_set_verify(ctx, SSL_VERIFY_NONE, NULL); /* Local self-signed fixture. */
    connection = BIO_new_ssl_connect(ctx);
    if (!connection) { SSL_CTX_free(ctx); return 1; }
    BIO_get_ssl(connection, &ssl);
    SSL_set_tlsext_host_name(ssl, "ja4-server");
    BIO_set_conn_hostname(connection, "ja4-server:443");
    printf("%s; %s\n", __VERSION__, OpenSSL_version(OPENSSL_VERSION));
    if (BIO_do_connect(connection) <= 0 || BIO_do_handshake(connection) <= 0) goto done;
    snprintf(request, sizeof(request),
             "GET /%s.txt HTTP/1.1\r\nHost: ja4-server\r\nConnection: close\r\n\r\n", argv[1]);
    if (BIO_write(connection, request, (int)strlen(request)) != (int)strlen(request)) goto done;
    while ((n = BIO_read(connection, response, sizeof(response))) > 0) {
        if (first) {
            ok = n >= 12 && memcmp(response, "HTTP/1.1 200", 12) == 0;
            first = 0;
        }
    }
done:
    BIO_free_all(connection);
    SSL_CTX_free(ctx);
    return ok ? 0 : 1;
}
