<?php

declare(strict_types=1);

/**
 * A heuristic metric for hashed JA4 TLS fingerprints (not JA4_RAW or JA4S).
 *
 * Eight equally weighted features: transport, version, SNI, cipher count,
 * extension count, ALPN, cipher hash and extension/signature hash.
 * Counts use absolute differences divided by 99; other features cost 0 or 1.
 * Hashes are opaque: character similarity says nothing about TLS similarity.
 * This cannot recover similarity between the original cipher/extension lists.
 */
final class Ja4Distance
{
    /** Returns 0.0 for identical fingerprints, up to 1.0 for maximum distance. */
    public static function distance(string $left, string $right): float
    {
        $a = self::parse($left);
        $b = self::parse($right);

        $distance = 0.0;

        foreach ([1, 2, 3, 6, 7, 8] as $field) {
            $distance += $a[$field] === $b[$field] ? 0.0 : 1.0;
        }

        foreach ([4, 5] as $field) {
            $distance += abs((int) $a[$field] - (int) $b[$field]) / 99;
        }

        return $distance / 8;
    }

    /** @return array<int, string> */
    private static function parse(string $fingerprint): array
    {
        // ALPN is case-sensitive; the specification requires lowercase hashes.
        $pattern = '/\A([tqd])(13|12|11|10|s3|s2|d1|d2|d3|00)([di])'
            . '([0-9]{2})([0-9]{2})([a-zA-Z0-9]{2})_'
            . '([a-f0-9]{12})_([a-f0-9]{12})\z/';

        if (preg_match($pattern, $fingerprint, $matches) !== 1) {
            throw new InvalidArgumentException(
                'Expected a hashed JA4 TLS fingerprint, e.g. t13d1516h2_8daaf6152771_b186095e22b6.'
            );
        }

        return $matches;
    }
}
