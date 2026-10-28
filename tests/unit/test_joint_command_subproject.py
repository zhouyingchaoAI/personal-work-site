import unittest
from pathlib import Path
from backend import runtime as rt
from backend.joint_command_loader import PROJECT_ROOT, load_module
from backend.crm_region_identity import region_identity


class JointCommandSubprojectTests(unittest.TestCase):
    def test_runtime_uses_subproject_implementation(self):
        for name in ('monthly_battle_read', 'crm_read_snapshot', 'crm_capabilities'):
            source = Path(getattr(rt, name).__code__.co_filename)
            self.assertEqual(source.parent, PROJECT_ROOT / 'backend')

    def test_original_import_contract(self):
        self.assertEqual(region_identity('东区-江苏'), ('东区', '江苏'))

    def test_loader_rejects_paths_outside_project(self):
        with self.assertRaises(ValueError):
            load_module('../core.py', {})

    def test_shared_runtime_paths_are_preserved(self):
        self.assertEqual(Path(rt.__file__).name, 'app.py')
        self.assertEqual(Path(rt.APP_ROOT), PROJECT_ROOT.parents[2])

    def test_frontend_compatibility_entry(self):
        root = PROJECT_ROOT.parents[2]
        wrapper = root / 'ai-office-assistant-web/src/views/CrmAssistantView/index.vue'
        self.assertIn('packages/joint-command/frontend/index.vue', wrapper.read_text())
