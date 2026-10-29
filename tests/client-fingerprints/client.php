<?php

printf("PHP %s; %s\n", PHP_VERSION, OPENSSL_VERSION_TEXT);
// Only the local self-signed HTTPS fixture is contacted.
$context = stream_context_create([
    'http' => ['timeout' => 15],
    'ssl' => ['verify_peer' => false, 'verify_peer_name' => false],
]);
$body = file_get_contents('https://ja4-server/php.txt', false, $context);
exit($body === "ok\n" ? 0 : 1);
