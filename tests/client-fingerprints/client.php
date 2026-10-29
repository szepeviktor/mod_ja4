<?php

printf("PHP %s; %s\n", PHP_VERSION, OPENSSL_VERSION_TEXT);
// Only the local HTTPS fixture is contacted.
$context = stream_context_create([
    'http' => ['timeout' => 15],
    'ssl' => [
        'cafile' => '/fixture/ca.pem',
        'verify_peer' => true,
        'verify_peer_name' => true,
    ],
]);
$body = file_get_contents('https://ja4-server/php.txt', false, $context);
exit($body === "ok\n" ? 0 : 1);
