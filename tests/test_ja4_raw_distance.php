<?php

declare(strict_types=1);

require __DIR__ . '/../examples/Ja4RawDistance.php';
$base = 't13d0202h2_1301,1302_000a,000b_0403,0804';
$cases = [
    [$base, $base, 0.0],
    [$base, 't13d0202h2_1302,1301_000b,000a_0403,0804', 0.0],
    [$base, 't13d0202h2_1301,1302_000a,000b_0804,0403', 0.35],
    [$base, 't13d0102h2_1301_000a,000b_0403,0804', 0.15],
    [$base, 't13d0201h2_1301,1302_000a_0403,0804', 0.15],
    [$base, 't13d0202h1_1301,1302_000a,000b_0403,0804', 0.0125],
    [$base, 'q12i0202h1_1301,1302_000a,000b_0403,0804', 0.05],
    ['t00i000000___', 't00i000000___', 0.0],
    ['t00i000000___', 'qd3d0101h3_1301_000a_0403', 1.0],
];
foreach ($cases as [$a, $b, $expected]) {
    foreach ([[$a, $b], [$b, $a]] as [$left, $right]) {
        if (abs(Ja4RawDistance::distance($left, $right) - $expected) > 1e-12) {
            throw new RuntimeException('Unexpected RAW distance.');
        }
    }
}
try {
    Ja4RawDistance::distance('invalid', $base);
    throw new RuntimeException('Invalid RAW accepted.');
} catch (InvalidArgumentException) {
}
echo "JA4 RAW distance tests passed.\n";
