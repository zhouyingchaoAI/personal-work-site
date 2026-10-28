import json
import os
import unittest
from decimal import Decimal
from backend.datacenter_sql import compile_query, ensure_structured_schema, refresh_query_stats, query_structured

class QueryValidationTests(unittest.TestCase):
    def test_owner_required_and_cannot_escape(self):
        for owner in ['', '../alice', "x' OR TRUE --"]:
            with self.assertRaises(ValueError):compile_query('crm.units',{'owner':owner})
    def test_limits_whitelist_and_wildcards(self):
        table,where,values,order,limit,offset=compile_query('crm.units',{'owner':'alice','keyword':'50%_off','limit':'9999'})
        self.assertEqual(limit,500)
        self.assertEqual(values['keyword'],'%50!%!_off%')
        self.assertNotIn('alice',where)
        with self.assertRaises(ValueError):compile_query('crm.units',{'owner':'alice','arbitrary_sql':'select 1'})
    def test_invalid_ranges_rejected(self):
        for params in [{'min_amount':'NaN'},{'min_amount':'Infinity'},{'date_from':'2026-02-30'}, {'date_from':'2026-09-30','date_to':'2026-09-01'}, {'min_amount':'10','max_amount':'2'}]:
            with self.assertRaises(ValueError):compile_query('cashflow.history',{'owner':'alice',**params})

@unittest.skipUnless(os.getenv('DC_SQL_TEST_DB'),'requires isolated PostgreSQL database')
class PostgreSQLQueryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from backend.datacenter_db import db_connect, ensure_schema
        assert os.getenv('OFFICE_PG_DB','').startswith('dc_sql_test_')
        cls.conn=db_connect();ensure_schema(cls.conn)
        for table in ['cashflow.history_records','crm.units','ledger.items','crm.opportunities']:cls.conn.run('TRUNCATE '+table)
        # Load an isolated dataset large enough for the planner to select the real indexes.
        cls.conn.run("""INSERT INTO cashflow.history_records(owner,idx,customer,payload)
            SELECT CASE WHEN n<=20000 THEN 'alice' ELSE 'bob' END,n,'客户',
              jsonb_build_object('id',n,'customer','客户','project_name',CASE WHEN n=17 THEN 'rare-target' ELSE '普通项目' END,
                 'region',CASE WHEN n=17 THEN '华南' ELSE '华东' END,'received_amount',n/10.0,'planned_amount',n/5.0,
                 'received_date','2026-09-01')
            FROM generate_series(1,22000) n""")
        cls.conn.run("INSERT INTO crm.units(owner,id,name,payload) VALUES ('alice','literal','50%_off','{\"id\":\"literal\",\"name\":\"50%_off\"}'), ('alice','other','50xxoff','{\"id\":\"other\",\"name\":\"50xxoff\"}')")
        cls.conn.run("INSERT INTO ledger.items(owner,id,payload) VALUES ('alice','bad','{\"id\":\"bad\",\"contract_amount\":\"未知\",\"payment_due\":\"2026-02-30\"}')")
        cls.conn.run("INSERT INTO crm.opportunities(owner,id,name,payload) VALUES ('alice','slash-date','x','{\"id\":\"slash-date\",\"business_date\":\"2024/5/3\",\"amount\":\"12.50\"}')")
        refresh_query_stats(cls.conn)
    @classmethod
    def tearDownClass(cls):cls.conn.close()
    def test_database_filter_aggregate_and_pagination(self):
        r=query_structured('cashflow.history',{'owner':'alice','region':'华南','min_amount':'1.70','date_from':'2026-09-01','limit':'1','summary':'1'},self.conn)
        self.assertEqual(r['total'],1)
        self.assertEqual(r['items'][0]['id'],17)
        self.assertEqual(Decimal(r['summary']['received_amount']),Decimal('1.7'))
        self.assertTrue(r['synced_at'])
        r=query_structured('cashflow.history',{'owner':'alice','offset':'50000'},self.conn)
        self.assertEqual(r['total'],20000);self.assertEqual(r['items'],[])
    def test_legacy_slash_dates_are_queryable_without_changing_payload(self):
        r=query_structured('crm.opportunities',{'owner':'alice','date_from':'2024-05-01','date_to':'2024-05-31'},self.conn)
        self.assertEqual(r['total'],1)
        self.assertEqual(r['items'][0]['business_date'],'2024/5/3')
        self.assertEqual(r['invalid_typed_values'],0)
    def test_literal_keyword_and_owner_isolation(self):
        r=query_structured('crm.units',{'owner':'alice','keyword':'50%_off'},self.conn)
        self.assertEqual(r['total'],1);self.assertEqual(r['items'][0]['id'],'literal')
        self.assertEqual(query_structured('crm.units',{'owner':'bob'},self.conn)['total'],0)
    def test_invalid_values_preserved_and_reported(self):
        r=query_structured('ledger.items',{'owner':'alice'},self.conn)
        self.assertEqual(r['items'][0]['contract_amount'],'未知')
        self.assertEqual(r['invalid_typed_values'],2)
        self.assertEqual(self.conn.run("SELECT contract_amount,payment_due FROM ledger.items WHERE id='bad'"),[[None,None]])
    def test_failed_refresh_keeps_old_rows_available_to_concurrent_readers(self):
        import threading
        from backend.datacenter_db import db_connect,_replace
        ready,release=threading.Event(),threading.Event()
        errors=[]
        class DelayedRows(list):
            def __iter__(self):
                ready.set()
                if not release.wait(5):raise RuntimeError('reader timed out')
                return super().__iter__()
        rows=DelayedRows([['alice','duplicate','new','{}'],['alice','duplicate','new','{}']])
        def writer():
            c=db_connect()
            try:_replace(c,'crm.units',['owner','id','name','payload'],rows,{'payload':'::jsonb'})
            except Exception as exc:errors.append(type(exc).__name__)
            finally:c.close()
        thread=threading.Thread(target=writer);thread.start()
        try:
            self.assertTrue(ready.wait(5))
            self.assertEqual(query_structured('crm.units',{'owner':'alice'},self.conn)['total'],2)
        finally:
            release.set();thread.join(8)
        self.assertFalse(thread.is_alive())
        self.assertTrue(errors)
        self.assertEqual(query_structured('crm.units',{'owner':'alice'},self.conn)['total'],2)

    def test_repeat_schema_install_and_real_index_plan(self):
        ensure_structured_schema(self.conn)
        plan=self.conn.run("EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) SELECT payload FROM cashflow.history_records WHERE owner='alice' AND region='华南' LIMIT 20")[0][0]
        self.assertIn('q_cashflow_history_records_region',json.dumps(plan))
        plan=self.conn.run("EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) SELECT payload FROM cashflow.history_records WHERE search_text LIKE '%rare-target%' LIMIT 20")[0][0]
        self.assertIn('q_cashflow_history_records_search',json.dumps(plan))


class ApiSourceTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        import backend.runtime as runtime
        self.r=runtime
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        p=patch.object(runtime,'USER_DATA_DIR',self.root);p.start();self.addCleanup(p.stop)
        (self.root/'alice'/'crm').mkdir(parents=True)
        (self.root/'alice'/'crm'/'units.json').write_text('{"x":{"id":"x","name":"live-name"}}')
    def test_default_keeps_live_storage(self):
        from unittest.mock import patch
        with patch('backend.datacenter_sql.query_structured',side_effect=AssertionError('must not query DB')):
            result=self.r.dapi_query('crm.units',{'owner':'alice'},'test')
        self.assertEqual(result['source'],'live')
        self.assertEqual(result['items'][0]['name'],'live-name')
    def test_database_masks_each_item_without_truncating_page(self):
        from unittest.mock import patch
        payload={'items':[{'id':i,'api_key':'sensitive-fixture'} for i in range(300)],'source':'postgresql','synced_at':'fixture'}
        with patch('backend.datacenter_sql.query_structured',return_value=payload):
            result=self.r.dapi_query('crm.units',{'owner':'alice','source':'database'},'test')
        self.assertEqual(len(result['items']),300)
        self.assertEqual(result['items'][0]['api_key'],'••• 已脱敏')
    def test_failure_does_not_silently_fall_back_or_leak(self):
        from unittest.mock import patch
        with patch('backend.datacenter_sql.query_structured',side_effect=Exception('secret-password')):
            with self.assertRaises(RuntimeError) as exc:
                self.r.dapi_query('crm.units',{'owner':'alice','source':'database'},'test')
        self.assertNotIn('secret-password',str(exc.exception))
    def test_live_filters_not_silently_ignored(self):
        with self.assertRaises(ValueError):self.r.dapi_query('crm.units',{'owner':'alice','region':'华南'},'test')
    def test_catalog_explains_typed_columns_and_source(self):
        docs=self.r.dapi_catalog()['datasets']
        sql=[d for d in docs if d.get('database_table')]
        self.assertEqual(len(sql),11)
        self.assertTrue(all(d['typed_fields'] for d in sql))

if __name__=='__main__':unittest.main()
