import copy
import unittest
from backend.crm_region_identity import region_identity, normalize_business_regions


class RegionIdentityTests(unittest.TestCase):
    def test_four_regions_and_three_offices(self):
        for raw, expected in [('东区-浙北办事处', ('东区', '浙北')), ('宁波', ('东区', '浙南')), ('上海作战平台', ('东区', '浙南')), ('东区－江苏', ('东区', '江苏')), ('西区作战平台', ('西区', '')), ('中区', ('中区', '')), ('广东作战平台', ('广东区', ''))]:
            self.assertEqual(region_identity(raw), expected)
        self.assertEqual(region_identity('铁路先遣队'), ('', ''))
        self.assertEqual(region_identity('公司-其他'), ('', ''))

    def test_normalization_preserves_amounts_originals_and_totals(self):
        sheets = [{'key': '02_作战平台经营结果', 'headers': ['区域', '金额'], 'rows': [['上海作战平台', 123], ['铁路先遣队', 456], ['合计', 579]]}]
        original = copy.deepcopy(sheets)
        result = normalize_business_regions(sheets)
        self.assertEqual(sheets, original)
        self.assertEqual(result[0]['rows'], [['东区-浙南', 123, '上海作战平台'], ['归属待核验', 456, '铁路先遣队'], ['合计', 579, '']])
        self.assertEqual(result, normalize_business_regions(result))


if __name__ == '__main__':
    unittest.main()
