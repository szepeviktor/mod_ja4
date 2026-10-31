"""Regression tests for current reference imports and exports."""

import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import yaml

SCRIPT = Path(__file__).resolve().parents[1] / 'references/build.py'
spec = importlib.util.spec_from_file_location('references_build', SCRIPT)
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)
RAW = 't13d010300_1301_000d_0403'
JA4 = builder.raw_hash(RAW)


class ReferencesTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.write('sources/foxio/mapping.csv', f'Application,ja4\nExample,{JA4}\n')
        self.write('sources/workflow/results.json', json.dumps([
            {'success': True, 'language': 'Python', 'ja4': JA4, 'ja4_raw': RAW},
            {'success': False, 'language': 'Missing'}]))
        self.write('sources/live-traffic/debug-request-headers.log',
                   f'@@ja4 {JA4}\n@@ja4_raw {RAW}\n' * 2)
        self.write('sources/manual.yaml', '[]\n')

    def write(self, name, content):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)

    def test_merges_without_promoting_log_or_csv_labels(self):
        catalog, classifier = builder.build(self.root)
        self.assertEqual(len(catalog), 1)
        self.assertEqual(len(catalog[0]['observations']), 3)
        self.assertEqual(catalog[0]['observations'][2]['metadata']['count'], 2)
        self.assertEqual([row['family'] for row in classifier], ['python'])

    def test_manual_verification_and_conflicts(self):
        entry = dict(id='test', ja4=JA4, raw=RAW, family='other', label='Other',
                     verification='unverified', notes='Synthetic fixture')
        self.write('sources/manual.yaml', yaml.safe_dump([entry]))
        self.assertEqual(len(builder.build(self.root)[1]), 1)
        entry['verification'] = 'verified'
        self.write('sources/manual.yaml', yaml.safe_dump([entry]))
        catalog, classifier = builder.build(self.root)
        self.assertTrue(catalog[0]['conflict'])
        self.assertEqual(len(classifier), 2)
        self.write('sources/manual.yaml', yaml.safe_dump([entry, entry]))
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            builder.build(self.root)

    def test_php_apis_share_family_without_losing_labels(self):
        self.write('sources/workflow/results.json', json.dumps([
            dict(success=True, language=label, ja4=JA4, ja4_raw=RAW)
            for label in ('PHP', 'PHP / cURL')]))
        catalog, classifier = builder.build(self.root)
        self.assertFalse(catalog[0]['conflict'])
        self.assertEqual({row['family'] for row in classifier}, {'php'})
        self.assertEqual({row['label'] for row in classifier}, {'PHP', 'PHP / cURL'})

    def test_mismatch_removes_stale_exports(self):
        self.write('sources/manual.yaml', yaml.safe_dump([
            dict(id='bad', ja4=JA4, raw=RAW.replace('0403', '0503'),
                 label='Bad', verification='verified', notes='Synthetic fixture')]))
        for name in ('catalog.json', 'classifier-references.json'):
            self.write('generated/' + name, 'stale')
        result = subprocess.run([sys.executable, str(SCRIPT), '--root', str(self.root)],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn('mismatch', result.stderr)
        self.assertEqual(list((self.root / 'generated').iterdir()), [])

    def test_rebuild_replaces_old_entries(self):
        for name in ('catalog.json', 'classifier-references.json'):
            self.write('generated/' + name, '["old"]')
        subprocess.run([sys.executable, str(SCRIPT), '--root', str(self.root)],
                       check=True, capture_output=True)
        result = json.loads((self.root / 'generated/catalog.json').read_text())
        self.assertEqual([row['ja4'] for row in result], [JA4])


if __name__ == '__main__':
    unittest.main()
