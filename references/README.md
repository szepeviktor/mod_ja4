# JA4 references

This directory maintains the current JA4 knowledge catalog from FoXIO labels, controlled HTTPS client measurements, live traffic log observations and manually curated knowledge for exact lookup and experimental RAW client-family classification.

Keep only the current external sources, replace them in place without backups, and rebuild with `rtk python3 references/build.py` using Python 3 and PyYAML.

| File | Purpose | Git |
| --- | --- | --- |
| `README.md` | Describes reference files and their retention rules. | Yes |
| `schema.json` | Defines the structure of manual entries after YAML decoding. | Yes |
| `build.py` | Validates the four required sources and rebuilds both exports while preserving source observations and reporting conflicting families. | Yes |
| `sources/foxio/mapping.csv` | Contains the current unmodified FoXIO CSV download for exact JA4 lookup. | No |
| `sources/workflow/results.json` | Contains the current unmodified combined workflow results with measured client and runtime details. | No |
| `sources/live-traffic/debug-request-headers.log` | Contains the current original request log, whose JA4 and RAW pairs are counted without exporting request headers. | No |
| `sources/manual.yaml` | Contains manually maintained entries with unique IDs, JA4, optional RAW and family, label, verification, notes and optional evidence links. | Yes |
| `generated/catalog.json` | Groups current observations and distinct RAW values by JA4 without replacing competing source claims. | No |
| `generated/classifier-references.json` | Contains deduplicated RAW references from successful workflow measurements and verified manual entries with a family. | No |
| `../tests/test_references.py` | Checks merging, source validation, manual eligibility and replacement of generated outputs using temporary fixtures. | Yes |

To refresh from the repository root:

1. Create the ignored source directories with `rtk mkdir -p references/sources/foxio references/sources/workflow references/sources/live-traffic`, since a fresh clone contains none of the external data.
2. Download the original FoXIO CSV with `rtk proxy curl_chrome145 --fail --location --silent --show-error https://raw.githubusercontent.com/FoxIO-LLC/ja4/main/ja4plus-mapping.csv --output references/sources/foxio/mapping.csv`, replacing the previous file.
3. Obtain the combined `results.json` from the `https-client-fingerprints` artifact of the latest successful **HTTPS client fingerprints** run in `szepeviktor/mod_ja4` and replace `sources/workflow/results.json` without modifying its contents or mixing runs.
4. Obtain the current original request log from the site operator and replace `sources/live-traffic/debug-request-headers.log` without modifying its contents, using the project's existing access configuration rather than assuming a remote path or URL.
5. Edit `sources/manual.yaml` when curated knowledge changes, removing obsolete entries rather than archiving them.
6. Run `rtk python3 references/build.py` and `rtk python3 -m unittest discover -s tests -p test_references.py`, then inspect the generated catalog for unexpected family conflicts.
7. Commit only maintained code, documentation, schema and manual YAML changes, leaving external sources and generated exports ignored.

All `sources/` paths in these instructions are relative to `references/`, and downloads must replace current files without retaining artifact archives or older copies in the project.

The workflow is defined in `../.github/workflows/client-fingerprints.yml`, and a local measurement run with `rtk python3 tests/client-fingerprints/run.py` produces `../fingerprint-results/results.json`, which can replace the workflow source when explicitly using local measurements instead.

Python 3 and PyYAML must already be available in the selected runtime, and missing dependencies should be reported rather than installed globally or into the project without authorization.

Each manual entry requires a unique `id`, a hashed `ja4`, `label`, `verification` and explanatory `notes`, while `raw`, `family` and a list of `evidence` strings are optional.

Use `unverified` for an unsupported identification, `corroborated` for a source-supported association without a controlled measurement, and `verified` for a directly checked reference measurement, recording evidence for the choice.

The `raw` field accepts the complete sorted JA4_RAW with separate cipher, extension and ordered signature lists, or `null` when unavailable, and the builder checks its recomputed JA4 against `ja4` without reconstructing RAW from a hash.

The current manual entries document measured Go 1.27.3 and Rust/native-tls/OpenSSL profiles plus a FoXIO Python association whose identification as Requests remains unverified, with precise earlier-session evidence recorded in the YAML.

External sources and generated files have no retained history or backups, while Git intentionally retains the edit history of the manually curated YAML.

The catalog groups entries by JA4, retains each source observation and distinct RAW, and sets `conflict` when nonempty family claims differ without giving manual entries automatic precedence.

Only successful workflow records and verified manual entries with RAW and a family enter the classifier export, with duplicates removed by family, label and RAW; CSV labels and log observations alone never qualify.

A matching profile describes a TLS configuration and does not prove an unknown client's language, browser identity, operator or intent, so this catalog is not itself a blocking policy.

Every source is required, intentionally empty inputs must use a CSV header containing `ja4`, a JSON list `[]`, an empty log and a YAML list `[]` respectively, and source validation failures remove existing exports to prevent stale results from being used.

The source imports validate expected fields, manual fields and JA4/RAW consistency in code, while `schema.json` documents the manual YAML structure and is not loaded by the builder as a JSON Schema validator.
