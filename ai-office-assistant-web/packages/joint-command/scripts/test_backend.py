import os
import sys
import unittest
from pathlib import Path

root = Path(__file__).resolve().parents[4]
os.chdir(root)
sys.path.insert(0, str(root))
loader = unittest.TestLoader()
suite = unittest.TestSuite()
for pattern in ('test_crm*.py', 'test_monthly_battle.py', 'test_joint_command_subproject.py', 'test_analysis_block_templates.py'):
    suite.addTests(loader.discover(str(root / 'tests/unit'), pattern=pattern, top_level_dir=str(root)))
result = unittest.TextTestRunner(verbosity=1).run(suite)
sys.exit(0 if result.wasSuccessful() else 1)
