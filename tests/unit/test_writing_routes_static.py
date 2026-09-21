import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SERVER = ROOT / "backend" / "server.py"


class WritingRoutesStaticTest(unittest.TestCase):
    def setUp(self):
        self.source = SERVER.read_text(encoding="utf-8")

    def test_get_routes_are_registered(self):
        for route in [
            '"/api/writing/templates"',
            '"/api/writing/history"',
            '"/api/writing/history-item"',
            '"/api/writing/download"',
        ]:
            self.assertIn(route, self.source)

    def test_post_routes_are_registered(self):
        for route in [
            '"/api/writing/upload"',
            '"/api/writing/templates"',
            '"/api/writing/outline"',
            '"/api/writing/generate"',
            '"/api/writing/rewrite"',
            '"/api/writing/export"',
            '"/api/writing/delete"',
        ]:
            self.assertIn(route, self.source)

    def test_routes_call_writing_service_functions(self):
        for name in [
            "writing_templates",
            "writing_history",
            "writing_get_history",
            "writing_upload",
            "writing_generate_outline",
            "writing_generate",
            "writing_rewrite",
            "writing_export",
            "writing_delete_history",
        ]:
            self.assertIn(name, self.source)


if __name__ == "__main__":
    unittest.main()
