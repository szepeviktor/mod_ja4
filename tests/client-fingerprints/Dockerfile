FROM debian:13-slim

RUN apt-get update \
    && apt-get install --no-install-recommends -y \
        apache2 apache2-dev build-essential libssl-dev libtool-bin openssl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build
COPY Makefile ja4.c ja4.h mod_ja4.c ./
RUN make \
    && install -m 644 .libs/mod_ja4.so /usr/lib/apache2/modules/mod_ja4.so \
    && printf '%s\n' 'LoadModule ja4_module /usr/lib/apache2/modules/mod_ja4.so' \
        > /etc/apache2/mods-available/ja4.load \
    && a2enmod ssl ja4 \
    && a2dissite 000-default \
    && openssl req -x509 -newkey rsa:2048 -nodes -days 1 \
        -subj /CN=ja4-test-ca \
        -addext 'basicConstraints=critical,CA:TRUE' \
        -addext 'keyUsage=critical,keyCertSign,cRLSign' \
        -keyout /etc/ssl/private/ja4-ca.key -out /etc/ssl/certs/ja4-ca.crt \
    && openssl req -new -newkey rsa:2048 -nodes \
        -subj /CN=ja4-server \
        -addext 'subjectAltName=DNS:ja4-server' \
        -addext 'basicConstraints=critical,CA:FALSE' \
        -addext 'keyUsage=critical,digitalSignature,keyEncipherment' \
        -addext 'extendedKeyUsage=serverAuth' \
        -keyout /etc/ssl/private/ja4-test.key -out /tmp/ja4-test.csr \
    && openssl x509 -req -in /tmp/ja4-test.csr -days 1 \
        -CA /etc/ssl/certs/ja4-ca.crt -CAkey /etc/ssl/private/ja4-ca.key \
        -CAcreateserial -copy_extensions copy -out /etc/ssl/certs/ja4-test.crt \
    && mkdir -p /results \
    && for client in c cpp python php php-curl ruby node go rust; do \
        printf 'ok\n' > "/var/www/html/${client}.txt"; \
    done

COPY tests/client-fingerprints/server.conf /etc/apache2/sites-enabled/ja4-test.conf
CMD ["apache2ctl", "-D", "FOREGROUND"]
