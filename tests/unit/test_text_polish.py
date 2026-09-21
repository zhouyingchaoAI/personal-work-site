import unittest

import backend.runtime as rt


class TextPolishTests(unittest.TestCase):
    def test_polish_normalization_keeps_existing_structure(self):
        source = "一、项目推进\n1. 完成接口联调\n2. 跟进现场问题"

        self.assertEqual(rt.normalize_assistant_output(source), source)


if __name__ == "__main__":
    unittest.main()
