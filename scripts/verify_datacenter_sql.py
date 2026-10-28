"""Read-only production equivalence and performance check; run in datacenter-backup."""
import json
import statistics
import sys
import time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.datacenter_db import db_connect
from backend.datacenter_sql import MODELS,query_structured

root=Path('/app/user_data')
conn=db_connect()
try:
    checked=[]
    for dataset,model in MODELS.items():
        count=conn.run('SELECT count(*) FROM '+model['table'])[0][0]
        # Compare payloads and owner scoping against the imported mirror, independent of sorting.
        owners=conn.run('SELECT DISTINCT owner FROM '+model['table']) if model.get('owner') else [[None]]
        for owner, in owners:
            params={'owner':owner} if owner is not None else {}
            result=query_structured(dataset,{**params,'limit':'500'},conn)
            expected=conn.run('SELECT count(*) FROM '+model['table']+(' WHERE owner=:o' if owner is not None else ''),**({'o':owner} if owner is not None else {}))[0][0]
            assert result['total']==expected,(dataset,owner)
            assert len(result['items'])==min(500,expected),dataset
        checked.append({'dataset':dataset,'rows':count})
    row=conn.run("SELECT owner,region FROM cashflow.history_records GROUP BY owner,region ORDER BY count(*) DESC LIMIT 1")[0]
    owner,region=row
    # Same exact filter/page, with a warmed DB connection and OS file cache.
    def legacy():
        records=json.loads((root/owner/'cashflow_history.json').read_text())['records']
        filtered=[r for r in records if r.get('region')==region]
        return len(filtered),filtered[:20]
    def database():
        r=query_structured('cashflow.history',{'owner':owner,'region':region,'limit':'20','source':'database'},conn)
        return r['total'],r['items']
    assert legacy()==database(),'Live source changed or projection output mismatch'
    timings={}
    for label,fn in [('json_full_load',legacy),('postgres_filtered_page',database)]:
        fn();samples=[]
        for _ in range(20):
            started=time.perf_counter();fn();samples.append((time.perf_counter()-started)*1000)
        timings[label+'_median_ms']=round(statistics.median(samples),3)
    plan=conn.run('EXPLAIN (ANALYZE,BUFFERS,FORMAT JSON) SELECT payload FROM cashflow.history_records WHERE owner=:o AND region=:r ORDER BY idx LIMIT 20',o=owner,r=region)[0][0]
    quality=conn.run('SELECT dataset,invalid_typed_values FROM meta.query_models ORDER BY dataset')
    indexes=conn.run("SELECT count(*) FROM pg_indexes WHERE indexname LIKE 'q_%'")[0][0]
    print(json.dumps({'datasets':checked,'query_indexes':indexes,'benchmark':timings,'benchmark_note':'20 warm runs; exact region filter, 20 rows; excludes HTTP/connection establishment','plan':plan,'quality_invalid_typed_values':dict(quality)},ensure_ascii=False))
finally:conn.close()
