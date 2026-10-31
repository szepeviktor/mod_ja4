<?php

declare(strict_types=1);

require __DIR__ . '/../examples/Ja4RawDistance.php';

// Usage: php8.5 tests/compare_raw_clients.php /path/to/request.log
if ($argc !== 2) {
    fwrite(STDERR, "Usage: php8.5 tests/compare_raw_clients.php /path/to/request.log\n");
    exit(1);
}
$log = file_get_contents($argv[1]);
if ($log === false) {
    exit(1);
}
$clients = [];
foreach (json_decode(file_get_contents(__DIR__ . '/../references/generated/classifier-references.json'), true, flags: JSON_THROW_ON_ERROR) as $reference) {
    $clients[$reference['raw']][] = $reference['label'];
}
if ($clients === []) {
    throw new RuntimeException('No RAW references found.');
}

$entries = [];
$ja4 = null;
foreach (preg_split('/\R/', $log) as $line) {
    if (str_starts_with($line, '@@ja4 ')) {
        $ja4 = substr($line, 6);
    } elseif (str_starts_with($line, '@@ja4_raw ')) {
        if ($ja4 === null) {
            throw new RuntimeException('RAW without preceding JA4.');
        }
        $raw = substr($line, 10);
        $key = $ja4 . "\n" . $raw;
        $entries[$key] ??= ['ja4' => $ja4, 'raw' => $raw, 'count' => 0];
        $entries[$key]['count']++;
        $ja4 = null;
    }
}
usort($entries, fn ($a, $b) => $b['count'] <=> $a['count']);
echo "| JA4 | Előfordulás | Legközelebbi RAW referencia | Távolság | Második | Távolság |\n";
echo "|---|---:|---|---:|---|---:|\n";
foreach ($entries as $entry) {
    $scores = [];
    foreach ($clients as $raw => $names) {
        $scores[] = [Ja4RawDistance::distance($entry['raw'], $raw), implode(' / ', $names)];
    }
    usort($scores, fn ($a, $b) => $a[0] <=> $b[0]);
    printf("| `%s` | %d | %s | %.4f | %s | %.4f |\n",
        $entry['ja4'], $entry['count'], $scores[0][1], $scores[0][0], $scores[1][1] ?? '-', $scores[1][0] ?? 1.0);
}
