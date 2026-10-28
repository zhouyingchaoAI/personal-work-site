"""Read-only role verification. Run inside the office application container."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.datacenter_sql import query_connection, query_structured
with query_connection() as conn:
    assert conn.run('SELECT current_user')[0][0]=='datacenter_reader'
    for table in ['auth.users','settings.platform','raw.documents','archive.chunks']:
        schema,name=table.split('.')
        assert not conn.run("SELECT has_table_privilege(current_user,c.oid,'SELECT') FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname=:s AND c.relname=:t",s=schema,t=name)[0][0],table
    assert conn.run('SHOW default_transaction_read_only')[0][0]=='on'
    conn.run('SET default_transaction_read_only=off')
    for statement in ['DELETE FROM crm.units WHERE false','SELECT * FROM auth.users LIMIT 0','SELECT * FROM archive.chunks LIMIT 0']:
        try:conn.run(statement)
        except Exception as exc:
            assert isinstance(exc.args[0],dict) and exc.args[0].get('C')=='42501',type(exc).__name__
        else:raise AssertionError('Reader has excess privileges')
    conn.run('SET default_transaction_read_only=on')
    result=query_structured('cashflow.history',{'owner':'zhouyingchao','limit':'1'},conn)
    assert result['source']=='postgresql'
    print('Reader role: SELECT allowed; writes, account secrets and archived files denied; default read-only transaction PASS')
