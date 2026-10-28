import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import datacenter_migration_bundle as bundle


class MigrationBundleTests(unittest.TestCase):
    def test_dry_run_lists_native_exports_and_object_volumes(self):
        result = bundle.build(Path('/unused'), dry_run=True)
        self.assertEqual(result['state'], 'running')
        self.assertIn('office-postgres', [x['system'] for x in result['exports']])
        self.assertTrue(all(x['state'] == 'planned' for x in result['exports'] + result['volumes']))

    def test_missing_dependencies_produce_a_safe_partial_manifest(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(bundle, 'docker_container_exists', return_value=False), patch.object(bundle, 'docker_volume_exists', return_value=False):
            result = bundle.build(Path(tmp))
            manifest = Path(result['path']) / 'manifest.json'
            self.assertEqual(result['state'], 'partial')
            self.assertTrue(manifest.is_file())
            self.assertEqual((Path(result['path']) / 'SHA256SUMS').read_text(), '\n')

