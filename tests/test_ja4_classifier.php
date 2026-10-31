<?php

declare(strict_types=1);

require __DIR__ . '/../examples/Ja4Classifier.php';

function expect(bool $condition, string $message): void
{
    if (!$condition) {
        throw new RuntimeException($message);
    }
}

// Synthetic references exercise decisions; these are NOT real browser profiles.
$base = 't13d0303h2_1301,1302,1303_000a,000b,000d_0403,0804';
$other = 't12i010100_002f_0017_0601';
$refs = [
    ['family' => 'browser-a', 'label' => 'Fixture A', 'raw' => $base],
    ['family' => 'browser-b', 'label' => 'Fixture B', 'raw' => $other],
];
$classifier = new Ja4Classifier($refs);
expect($classifier->classify($base)['match'] === 'exact', 'Exact reference not found.');
$modified = 't13d0304h2_1301,1302,1303_000a,000b,000d,0017_0403,0804';
$result = $classifier->classify($modified);
expect($result['match'] === 'close' && $result['family'] === 'browser-a', 'Small mutation not recognized.');
expect($result['differences']['extensions_added'] === ['0017'], 'Wrong mutation explanation.');
expect($result['differences']['extensions_removed'] === [], 'Wrong removed extensions.');
expect($classifier->classify('qd3d0101h3_ffff_ffff_ffff')['match'] === 'unknown', 'Distant client accepted.');

$duplicate = [...$refs, ['family' => 'browser-c', 'label' => 'Shared TLS profile', 'raw' => $base]];
$ambiguous = (new Ja4Classifier($duplicate))->classify($base);
expect($ambiguous['match'] === 'ambiguous' && $ambiguous['family'] === null, 'Exact collision not reported.');
expect((new Ja4Classifier($duplicate))->classify($modified)['match'] === 'ambiguous', 'Close collision not reported.');
$sameFamily = [...$refs, ['family' => 'browser-a', 'label' => 'Another version', 'raw' => $modified]];
expect((new Ja4Classifier($sameFamily))->classify($modified)['match'] === 'exact', 'Same-family versions caused ambiguity.');

$strict = new Ja4Classifier($refs, Ja4RawDistance::distance($base, $modified), 0);
expect($strict->classify($modified)['match'] === 'close', 'Inclusive threshold failed.');
expect((new Ja4Classifier($refs, 0))->classify($modified)['match'] === 'unknown', 'Zero threshold accepted mutation.');
$reordered = 't13d0303h2_1301,1302,1303_000a,000b,000d_0804,0403';
$details = $classifier->classify($reordered)['differences'];
expect(isset($details['signature_algorithms_observed']), 'Signature ordering lost.');

foreach ([-0.1, 1.1, NAN, INF] as $invalid) {
    try {
        new Ja4Classifier($refs, $invalid);
        throw new RuntimeException('Invalid threshold accepted.');
    } catch (InvalidArgumentException) {
    }
}
foreach (['', 't13d0303h2_ffff_zzzz_0403'] as $invalid) {
    try {
        $classifier->classify($invalid);
        throw new RuntimeException('Invalid RAW accepted.');
    } catch (InvalidArgumentException) {
    }
}
echo "JA4 classifier tests passed.\n";
