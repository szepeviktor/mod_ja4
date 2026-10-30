"""Check matrix report aggregation without Docker or network access."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


SPEC = importlib.util.spec_from_file_location(
    'client_fingerprints', Path(__file__).parent / 'client-fingerprints' / 'run.py')
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


class MatrixReportTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.output = self.root / 'output'
        self.inputs = self.root / 'inputs'
        replacement = patch.object(runner, 'RESULTS', self.output)
        replacement.start()
        self.addCleanup(replacement.stop)

    def seed(self, failed=None, missing=None):
        for key, language, image, api, _ in runner.REPORT_CASES:
            if key == missing:
                continue
            directory = self.inputs / f'https-client-{key}'
            directory.mkdir(parents=True)
            record = dict(language=language, image=image, api=api, runtime='test runtime',
                          ja4='t13d1011h2_61a7ad8aa9b6_3fcd1a44f3e3',
                          ja4_raw='raw fixture', success=key != failed)
            (directory / 'results.json').write_text(json.dumps([record]))
            (directory / 'requests.tsv').write_text(f'/{key}.txt\t200\tJA4\tRAW\n')

    def records(self):
        return json.loads((self.output / 'results.json').read_text())

    def test_complete_matrix_preserves_order_and_client_logs(self):
        self.seed()
        self.assertEqual(runner.aggregate(self.inputs), 0)
        self.assertEqual([row['language'] for row in self.records()],
                         [case[1] for case in runner.REPORT_CASES])
        for key, *_ in runner.REPORT_CASES:
            self.assertEqual((self.output / 'clients' / key / 'requests.tsv').read_text(),
                             (self.inputs / f'https-client-{key}' / 'requests.tsv').read_text())
        self.assertIn('raw fixture', (self.output / 'summary.md').read_text())

    def test_failed_client_makes_combined_report_fail(self):
        self.seed(failed='rust')
        self.assertEqual(runner.aggregate(self.inputs), 1)
        self.assertEqual(sum(row['success'] for row in self.records()), len(runner.REPORT_CASES) - 1)
        self.assertIn('FAILED', (self.output / 'summary.md').read_text())

    def test_missing_client_is_reported_without_losing_other_results(self):
        self.seed(missing='go')
        self.assertEqual(runner.aggregate(self.inputs), 1)
        rows = self.records()
        self.assertEqual(len(rows), len(runner.REPORT_CASES))
        missing = next(row for row in rows if row['language'] == 'Go')
        self.assertFalse(missing['success'])
        self.assertEqual(missing['runtime'], 'Missing matrix result')
        self.assertEqual(sum(row['success'] for row in rows), len(runner.REPORT_CASES) - 1)

    def test_missing_windows_capture_is_reported(self):
        self.seed(missing='powershell')
        self.assertEqual(runner.aggregate(self.inputs), 1)
        missing = next(row for row in self.records() if row['language'] == 'PowerShell')
        self.assertFalse(missing['success'])
        self.assertEqual(missing['runtime'], 'Missing matrix result')


if __name__ == '__main__':
    unittest.main()
