<?php

$version = curl_version();
printf("PHP %s; libcurl %s; %s\n", PHP_VERSION, $version['version'], $version['ssl_version']);
// Only the local HTTPS fixture is contacted; retain libcurl's default TLS and ALPN settings.
$client = curl_init('https://ja4-server/php-curl.txt');
curl_setopt_array($client, [
    CURLOPT_RETURNTRANSFER => true,
    CURLOPT_TIMEOUT => 15,
    CURLOPT_CAINFO => '/fixture/ca.pem',
    CURLOPT_SSL_VERIFYPEER => true,
    CURLOPT_SSL_VERIFYHOST => 2,
]);
$body = curl_exec($client);
if ($body === false) {
    fwrite(STDERR, curl_error($client) . "\n");
}
exit($body === "ok\n" && curl_getinfo($client, CURLINFO_RESPONSE_CODE) === 200 ? 0 : 1);
