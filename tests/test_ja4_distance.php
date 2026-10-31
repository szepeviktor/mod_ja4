<?php

declare(strict_types=1);

require_once __DIR__ . '/../examples/Ja4Distance.php';

function checkDistance(string $left, string $right, float $expected): void
{
    foreach ([[$left, $right], [$right, $left]] as [$a, $b]) {
        $actual = Ja4Distance::distance($a, $b);
        if (abs($actual - $expected) > 1e-12) {
            throw new RuntimeException("Expected {$expected}, got {$actual}");
        }
    }
}

$base = 't13d1516h2_8daaf6152771_b186095e22b6';
checkDistance($base, $base, 0.0);
checkDistance($base, 't13d1516h2_8daaf6152770_b186095e22b6', 1 / 8);
checkDistance($base, 't13d1516h2_000000000000_b186095e22b6', 1 / 8);
checkDistance($base, 't13d1616h2_8daaf6152771_b186095e22b6', 1 / 792);
checkDistance($base, 't13d1516H2_8daaf6152771_b186095e22b6', 1 / 8);
checkDistance(
    't13d0000h2_000000000000_000000000000',
    'q12i9999h1_ffffffffffff_ffffffffffff',
    1.0,
);

foreach (['', $base . "\n", strtoupper($base), 'invalid', str_replace('t13', 't99', $base)] as $invalid) {
    try {
        Ja4Distance::distance($base, $invalid);
    } catch (InvalidArgumentException) {
        continue;
    }

    throw new RuntimeException('Malformed fingerprint was accepted.');
}

echo "JA4 distance tests passed.\n";
