from tests.unit.test_crm_excel import ExcelTests
import backend.runtime as r

class OrganizationTests(ExcelTests):
    def test_unit_delete_only_allows_an_empty_leaf(self):
        root = r.crm_unit_save({'name': '集团', 'type': '业主单位'}, 'alice')['unit']
        child = r.crm_unit_save({'name': '分公司', 'type': '业主单位', 'parent_unit_id': root['id']}, 'alice')['unit']

        blocked = r.crm_unit_delete(root['id'], 'alice')
        self.assertFalse(blocked['ok'])
        self.assertIn('下级组织', blocked['error'])

        person = r.crm_person_save({'name': '张工', 'unit_id': child['id']}, 'alice')['person']
        blocked = r.crm_unit_delete(child['id'], 'alice')
        self.assertFalse(blocked['ok'])
        self.assertIn('联系人', blocked['error'])
        self.assertIn(person['id'], r.crm_load('alice', 'people'))

        detached = r.crm_person_save({**person, 'unit_id': ''}, 'alice')['person']
        self.assertEqual(detached['unit_id'], '')
        deleted = r.crm_unit_delete(child['id'], 'alice')
        self.assertTrue(deleted['ok'])
        self.assertNotIn(child['id'], r.crm_load('alice', 'units'))

    def test_hierarchy_and_cycles(self):
        a=r.crm_unit_save({'name':'集团','type':'业主单位'},'alice')['unit']
        b=r.crm_unit_save({'name':'建设公司','type':'业主单位','parent_unit_id':a['id']},'alice')['unit']
        self.assertFalse(r.crm_unit_save({**a,'parent_unit_id':b['id']},'alice')['ok'])
        self.assertFalse(r.crm_unit_save({'name':'外部','parent_unit_id':a['id']},'bob')['ok'])
        boss=r.crm_person_save({'name':'主任','unit_id':a['id']},'alice')['person']
        worker=r.crm_person_save({'name':'张工','unit_id':b['id'],'manager_id':boss['id'],'department':'技术部','responsibilities':'验收'},'alice')['person']
        self.assertEqual(worker['department'],'技术部')
        self.assertFalse(r.crm_person_save({**boss,'manager_id':worker['id']},'alice')['ok'])
        self.assertFalse(r.crm_person_save({'name':'外部','manager_id':boss['id']},'bob')['ok'])
        legacy={k:v for k,v in worker.items() if k not in ('manager_id','department','responsibilities')}
        patched=r.crm_person_save({**legacy,'title':'经理'},'alice')['person']
        self.assertEqual(patched['department'],'技术部')
        self.assertEqual(patched['manager_id'],boss['id'])
        detached=r.crm_person_save({**patched,'manager_id':''},'alice')['person']
        self.assertEqual(detached['manager_id'],'')
    def test_quick_org_fields(self):
        boss=r.crm_person_save({'name':'主任'},'alice')['person']
        payload={'unit_name':'测试集团','unit_type':'业主单位','name':'李工','department':'采购部','manager_id':boss['id'],'responsibilities':'采购需求'}
        self.assertTrue(r.crm_quick_create(payload,'alice')['ok'])
        person=next(p for p in r.crm_load('alice','people').values() if p['name']=='李工')
        self.assertEqual(person['manager_id'],boss['id'])
        self.assertEqual(person['responsibilities'],'采购需求')
        self.assertFalse(r.crm_quick_create({**payload,'unit_name':'坏单位','manager_id':'unknown'},'alice')['ok'])
        self.assertFalse(any(u['name']=='坏单位' for u in r.crm_load('alice','units').values()))
