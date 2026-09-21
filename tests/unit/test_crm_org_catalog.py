import io
import unittest
from openpyxl import load_workbook
import backend.runtime as r

class OrgCatalogTests(unittest.TestCase):
    def test_template_has_shared_company_and_department_choices(self):
        b=load_workbook(io.BytesIO(r.crm_business_template()))
        self.assertIn('我方组织目录',b.sheetnames)
        rows=list(b['我方组织目录'].values)
        self.assertTrue(any('湖南承希科技有限公司' in row for row in rows))
        self.assertTrue(any('服务解决方案中心 / 场景研究院' in row for row in rows))
        dvs=list(b['经营收集表'].data_validations.dataValidation)
        self.assertTrue(any('Q2:Q501' in str(v.sqref) for v in dvs))
        self.assertTrue(any('R2:R501' in str(v.sqref) for v in dvs))
        b.close()
