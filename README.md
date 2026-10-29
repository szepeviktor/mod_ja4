# mod_ja4

Standalone Apache httpd 2.4 module for JA4 TLS client fingerprints. It builds as
`mod_ja4.so` and works with an unpatched `mod_ssl` and OpenSSL. Loading the module
enables capture for all incoming TLS connections; it does not fingerprint outbound
proxy connections.

## Build and install on Debian

On a minimal Debian system, install the build dependencies and Apache. Run the
package installation and module installation/configuration commands as root;
compilation itself can run as an ordinary user. The examples use `rtk` as a CLI
proxy; omit that prefix on servers where RTK is not installed.

```sh
rtk apt-get update
rtk apt-get install --no-install-recommends apache2 apache2-dev build-essential libssl-dev libtool-bin binutils
```

`build-essential` supplies the compiler and `make`; `apache2-dev` supplies `apxs`
and the Apache headers, and pulls in the APR and PCRE development packages.
`libssl-dev` provides OpenSSL headers/libraries, `libtool-bin` provides the
libtool executable, and `binutils` provides `strip`.
See the Debian package descriptions for [apache2-dev](https://packages.debian.org/stable/apache2-dev)
and [libssl-dev](https://packages.debian.org/stable/libssl-dev).

From this repository's root directory, compile both C files into one module:

```sh
rtk make APXS=/usr/bin/apxs
```

Alternatively, the equivalent direct build command is:

```sh
rtk apxs -c -Wc,-Wall -Wc,-Wextra -Wc,-Werror mod_ja4.c ja4.c -lcrypto -lssl
```

Build output: `.libs/mod_ja4.so` and its libtool descriptor `mod_ja4.la`.
Use the `apxs` belonging to the target Apache installation.

Install the module under `/usr/local/`, following the same layout as
[mod_444](https://github.com/szepeviktor/apache-httpd-module-444-drop/blob/master/README.md):

```sh
rtk install -d -m 755 /usr/local/lib/apache2/modules
rtk apxs -i -S LIBEXECDIR=/usr/local/lib/apache2/modules mod_ja4.la
rtk strip --strip-unneeded /usr/local/lib/apache2/modules/mod_ja4.so
```

## Load and configure

On Debian, create `/etc/apache2/mods-available/ja4.load` with this content:

```apache
# Depends: ssl
LoadModule ja4_module /usr/local/lib/apache2/modules/mod_ja4.so
```

Then enable the modules, validate the configuration and reload Apache as root:

```sh
rtk a2enmod ssl ja4
rtk apache2ctl configtest
rtk systemctl reload apache2
```

Run the reload only if the configuration check succeeds. If Apache is not
running yet, use `rtk systemctl start apache2` instead of the reload.
For other Apache layouts, add the `LoadModule` line to the server configuration
after loading `mod_ssl`.

To log fingerprints, add this to the server or virtual-host configuration
(choose an appropriate access-log path):

```apache
LogFormat "%h %r %>s ja4=%{ja4}n" with_ja4
CustomLog ${APACHE_LOG_DIR}/ja4_access.log with_ja4
```

The module does not require `SSLClientHelloVars` or `SSLOptions +StdEnvVars`.
It exports request environment variables `JA4` and `JA4_RAW`, and request notes
`ja4` and `ja4_raw`. Plain HTTP and connections without a successfully parsed
ClientHello have no fingerprint. No value is taken from a client HTTP header.

With PHP/CGI/FastCGI configured to forward the request environment:

```php
$ja4 = $_SERVER['JA4'] ?? null;
```

`ja4.php` is the older, separate experiment using Apache ClientHello variables;
it is not used by this module. The module computes the finished fingerprint in C.

For diagnostics, with `mod_headers` enabled:

```apache
Header always set X-JA4 "%{JA4}e" env=JA4
```

## Design and compatibility

The inspected Apache 2.5 source (`httpd/`, commit
`425ec5ed32266c56d3e96ac2c1e79f315f312edc`) copies ClientHello fields in
`ssl_engine_kernel.c:copy_clienthello_vars()` into a private `SSLConnRec` member.
`ssl_engine_vars.c:ssl_var_lookup_ssl_clienthello()` later exposes hex buffers.
That design needs a `mod_ssl` patch when backported directly to 2.4.

This module instead registers the public optional `ssl/pre_handshake` hook and
uses `SSL_set_msg_callback()` on each incoming SSL connection. OpenSSL supplies
complete handshake messages after fragment collection. The module parses the
initial ClientHello, calculates JA4 once and stores only the resulting strings
in its own connection configuration. It leaves the `mod_ssl` ClientHello/SNI and
info callbacks untouched. HTTP/2 requests resolve the master connection before
reading this data. The initial fingerprint survives HelloRetryRequest and is
exported again for keepalive requests and internal redirects.

The `pre_handshake` hook is present in the Apache 2.4.19 source. Target Apache
2.4.19 or newer, with OpenSSL 1.1.1 or 3.x. Older releases in that range have not
been runtime-tested. Validation here used **Apache 2.4.68, OpenSSL 3.0.22**, event
MPM and HTTP/2. Build against the headers/libraries for the Apache you will run;
do not assume a binary built here is portable to another installation.

OpenSSL supports one message callback per SSL connection. Another module using
`SSL_set_msg_callback()` or an inherited context message callback can conflict;
this module does not chain unknown callbacks. It does not change TLS negotiation
or provide a TLS termination proxy. TLS must terminate at this Apache to measure
the end user's ClientHello. HTTP/3/QUIC and DTLS are outside its scope.

The JA4 calculation follows the [FoxIO JA4 specification](https://github.com/FoxIO-LLC/ja4/blob/main/technical_details/JA4.md):
GREASE is excluded, ciphers/extensions are sorted, signature algorithms retain
their offered order, SNI/ALPN are omitted from the extension hash, ALPN uses its
first/last bytes with the specified hexadecimal fallback, and empty hash inputs
use twelve zeroes. `JA4_RAW` is the sorted, unhashed representation with separate
cipher, extension and signature lists. Counts saturate at 99.

Parsing checks all consumed lengths, rejects duplicate extensions and limits
the handshake input to 128 KiB. Malformed messages produce no fingerprint and
do not change OpenSSL's decision to accept or reject the connection.

## Tests

```sh
rtk make test
rtk make integration
```

Parser tests check the published JA4 example, GREASE/permutation invariance,
signature order, binary ALPN, legacy versions, empty inputs, saturated counts,
truncations, malformed vectors and deterministic random inputs.

Integration tests start a temporary, unprivileged Apache on loopback ports and
compare exported values with the actual ClientHello sent by the test client.
They cover TLS 1.2/1.3, HTTP keepalive, SNI virtual hosts, absent SNI, resumed TLS
sessions, HelloRetryRequest, plain HTTP, and two HTTP/2 streams. They require
`/usr/sbin/apache2`, `apxs`, `openssl`, `/etc/mime.types`, the usual Apache modules,
and Python's standard library. The HTTP/2 test additionally uses the Python `h2`
package and skips if it or `mod_http2` is missing. Tests do not install anything,
modify system configuration, or restart the system Apache.
