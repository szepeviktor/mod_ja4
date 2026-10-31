<?php

declare(strict_types=1);

require_once __DIR__ . '/Ja4RawDistance.php';

/** Nearest-family matching, not proof of browser identity or benign traffic. */
final class Ja4Classifier
{
    /** @var list<array{family: string, label: string, raw: string}> */
    private array $references;

    /**
     * References should include competing browser AND non-browser families.
     * Thresholds are experimental RAW scores; calibrate against your traffic.
     * @param list<array{family: string, label: string, raw: string}> $references
     */
    public function __construct(
        array $references,
        private readonly float $maxDistance = 0.10,
        private readonly float $ambiguityMargin = 0.02,
    ) {
        foreach ([$maxDistance, $ambiguityMargin] as $threshold) {
            if (!is_finite($threshold) || $threshold < 0 || $threshold > 1) {
                throw new InvalidArgumentException('Thresholds must be finite numbers between 0 and 1.');
            }
        }
        if ($references === []) {
            throw new InvalidArgumentException('At least one reference is required.');
        }
        foreach ($references as $reference) {
            foreach (['family', 'label', 'raw'] as $key) {
                if (!isset($reference[$key]) || !is_string($reference[$key]) || $reference[$key] === '') {
                    throw new InvalidArgumentException('Each reference needs nonempty family, label and raw strings.');
                }
            }
            Ja4RawDistance::distance($reference['raw'], $reference['raw']);
        }
        $this->references = array_values($references);
    }

    /**
     * family is null for ambiguous/unknown results. Candidates are the closest
     * reference per family, including poor matches, in increasing distance order.
     * @return array<string, mixed>
     */
    public function classify(string $raw): array
    {
        Ja4RawDistance::distance($raw, $raw);
        $families = [];
        foreach ($this->references as $reference) {
            $distance = Ja4RawDistance::distance($raw, $reference['raw']);
            $family = $reference['family'];
            if (!isset($families[$family]) || $distance < $families[$family]['distance']) {
                $families[$family] = [
                    'family' => $family,
                    'label' => $reference['label'],
                    'distance' => $distance,
                    'differences' => self::differences($reference['raw'], $raw),
                ];
            }
        }
        $candidates = array_values($families);
        usort($candidates, static fn (array $a, array $b): int =>
            ($a['distance'] <=> $b['distance']) ?: strcmp($a['family'], $b['family']));
        $best = $candidates[0];
        $gap = isset($candidates[1]) ? $candidates[1]['distance'] - $best['distance'] : null;
        $status = 'unknown';
        if ($best['distance'] <= $this->maxDistance) {
            // A sole exact family wins over merely close alternatives. Exact
            // collisions between different families must remain ambiguous.
            $ambiguous = $gap !== null && ($best['distance'] === 0.0
                ? $candidates[1]['distance'] === 0.0
                : $gap <= $this->ambiguityMargin);
            $status = $ambiguous ? 'ambiguous' : ($best['distance'] === 0.0 ? 'exact' : 'close');
        }

        return [
            'match' => $status,
            'family' => in_array($status, ['exact', 'close'], true) ? $best['family'] : null,
            'distance' => $best['distance'],
            'margin' => $gap,
            'differences' => $best['differences'],
            'candidates' => $candidates,
        ];
    }

    /** Changes are always from reference to observed RAW. @return array<string, mixed> */
    private static function differences(string $reference, string $observed): array
    {
        $a = explode('_', $reference);
        $b = explode('_', $observed);
        $result = [];
        foreach (['ciphers' => 1, 'extensions' => 2, 'signature_algorithms' => 3] as $name => $index) {
            $left = $a[$index] === '' ? [] : explode(',', $a[$index]);
            $right = $b[$index] === '' ? [] : explode(',', $b[$index]);
            $result[$name . '_added'] = array_values(array_unique(array_diff($right, $left)));
            $result[$name . '_removed'] = array_values(array_unique(array_diff($left, $right)));
            if ($index === 3 && $left !== $right) {
                // Full lists also expose reorderings and duplicate-count changes.
                $result['signature_algorithms_reference'] = $left;
                $result['signature_algorithms_observed'] = $right;
            }
        }
        foreach (['transport' => [0, 1], 'version' => [1, 2], 'sni' => [3, 1], 'alpn' => [8, 2]] as $name => [$offset, $length]) {
            $left = substr($a[0], $offset, $length);
            $right = substr($b[0], $offset, $length);
            if ($left !== $right) {
                $result[$name] = ['reference' => $left, 'observed' => $right];
            }
        }

        return $result;
    }
}
