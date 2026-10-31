<?php

declare(strict_types=1);

/** Experimental RAW metric; scores are not calibrated language probabilities. */
final class Ja4RawDistance
{
    /**
     * Weights: cipher set 30%, extension set 30%, ordered signature algorithms
     * 35%, metadata 5% (transport, version, SNI, ALPN equally within metadata).
     * Cipher/extension counts are already represented by the actual lists.
     */
    public static function distance(string $left, string $right): float
    {
        $a = self::parse($left);
        $b = self::parse($right);
        $metadata = 0;
        foreach ([0, 1, 2, 3] as $i) {
            $metadata += $a[0][$i] === $b[0][$i] ? 0 : 1;
        }

        return 0.30 * self::setDistance($a[1], $b[1])
            + 0.30 * self::setDistance($a[2], $b[2])
            + 0.35 * self::sequenceDistance($a[3], $b[3])
            + 0.05 * ($metadata / 4);
    }

    /** @return array{list<string>, list<string>, list<string>, list<string>} */
    private static function parse(string $raw): array
    {
        $list = '(?:[a-f0-9]{4}(?:,[a-f0-9]{4})*)?';
        $pattern = '/\A([tqd])(13|12|11|10|s3|s2|d1|d2|d3|00)([di])'
            . '[0-9]{4}([a-zA-Z0-9]{2})_(' . $list . ')_(' . $list . ')_(' . $list . ')\z/';
        if (preg_match($pattern, $raw, $m) !== 1) {
            throw new InvalidArgumentException('Expected a JA4_RAW fingerprint with three hex lists.');
        }

        return [
            [$m[1], $m[2], $m[3], $m[4]],
            $m[5] === '' ? [] : explode(',', $m[5]),
            $m[6] === '' ? [] : explode(',', $m[6]),
            $m[7] === '' ? [] : explode(',', $m[7]),
        ];
    }

    /** @param list<string> $a @param list<string> $b */
    private static function setDistance(array $a, array $b): float
    {
        $a = array_unique($a);
        $b = array_unique($b);
        $union = count(array_unique([...$a, ...$b]));

        return $union === 0 ? 0.0 : 1 - count(array_intersect($a, $b)) / $union;
    }

    /** Token Levenshtein: each complete signature algorithm is one token.
     * @param list<string> $a @param list<string> $b
     */
    private static function sequenceDistance(array $a, array $b): float
    {
        $length = max(count($a), count($b));
        if ($length === 0) {
            return 0.0;
        }
        $previous = range(0, count($b));
        foreach ($a as $i => $token) {
            $current = [$i + 1];
            foreach ($b as $j => $other) {
                $current[] = min(
                    $previous[$j + 1] + 1,
                    $current[$j] + 1,
                    $previous[$j] + ($token === $other ? 0 : 1),
                );
            }
            $previous = $current;
        }

        return $previous[count($b)] / $length;
    }
}
