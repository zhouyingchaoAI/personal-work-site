"""Typed, indexed read projections. Original payloads remain for API compatibility."""
import os
import queue
import re
import sys
import threading
from contextlib import contextmanager
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'vendor/pgdeps'))
import pg8000.native

# column -> (SQL type, source payload field). Only these identifiers can enter SQL.
MODELS = {
 'crm.units': {'table':'crm.units','owner':True,'fields':{'type':('text','type'),'region':('text','region'),'business_region':('text','business_region'),'parent_unit_id':('text','parent_unit_id')},'filters':['type','region','business_region','parent_unit_id']},
 'crm.people': {'table':'crm.people','owner':True,'fields':{'unit_id':('text','unit_id'),'title':('text','title'),'department':('text','department'),'importance':('text','importance')},'filters':['unit_id','department','importance']},
 'crm.relations': {'table':'crm.relations','owner':True,'fields':{'person_id':('text','person_id'),'our_member':('text','our_member'),'strength':('text','strength'),'score':('numeric','score')},'filters':['person_id','our_member','strength']},
 'crm.actions': {'table':'crm.actions','owner':True,'fields':{'relation_id':('text','relation_id'),'action_type':('text','type'),'project_id':('text','project_id'),'happened_date':('date','happened_at'),'cost':('numeric','cost')},'filters':['relation_id','action_type','project_id'],'date':'happened_date'},
 'crm.opportunities': {'table':'crm.opportunities','owner':True,'fields':{'stage':('text','stage'),'status':('text','status'),'region':('text','region'),'owner_unit':('text','owner_unit'),'manager':('text','manager'),'amount':('numeric','amount'),'business_date':('date','business_date')},'filters':['stage','status','region','owner_unit','manager'],'date':'business_date','amount':'amount'},
 'cashflow.history': {'table':'cashflow.history_records','owner':True,'key':'idx','fields':{'record_id':('text','id'),'project_code':('text','project_code'),'project_name':('text','project_name'),'region':('text','region'),'status':('text','status'),'project_type':('text','project_type'),'contract_amount':('numeric','contract_amount'),'planned_amount':('numeric','planned_amount'),'received_amount':('numeric','received_amount'),'planned_date':('date','planned_date'),'received_date':('date','received_date')},'filters':['region','status','project_type','project_code','customer'],'date':'received_date','amount':'received_amount'},
 'ledger.items': {'table':'ledger.items','owner':True,'fields':{'project_name':('text','project_name'),'customer':('text','customer'),'stage':('text','stage'),'status':('text','status'),'contract_amount':('numeric','contract_amount'),'received_amount':('numeric','received_amount'),'payment_due':('date','payment_due')},'filters':['stage','status','customer'],'date':'payment_due','amount':'contract_amount'},
 'org.staff': {'table':'crm.staff_directory','fields':{'name':('text','name'),'department':('text','department'),'business_region':('text','business_region'),'manager_id':('text','manager_id'),'title':('text','title')},'filters':['department','business_region','manager_id'],'search':['name','username','region','position']},
 'tickets.list': {'table':'collab.tickets','fields':{'title':('text','title'),'module':('text','module'),'status':('text','status'),'author':('text','author')},'filters':['module','status','author'],'search':['title','module','status']},
 'forum.topics': {'table':'collab.forum_topics','fields':{'title':('text','title'),'author':('text','author')},'filters':['author'],'search':['title','author']},
 'agent.skill_invocations': {'table':'agentic.skill_invocations','fields':{'user_id':('text','user_id'),'skill_name':('text','skill_name'),'status':('text','status'),'started_date':('date','started_at')},'filters':['user_id','skill_name','status'],'date':'started_date'},
}
DEFAULT_SEARCH = ['name','title','project_name','customer','summary']
SCHEMA_VERSION = 2


def ensure_structured_schema(conn):
    conn.run('CREATE SCHEMA IF NOT EXISTS meta')
    conn.run('''CREATE TABLE IF NOT EXISTS meta.query_models (
        dataset text PRIMARY KEY, version integer NOT NULL, refreshed_at timestamptz,
        rows bigint, invalid_typed_values bigint DEFAULT 0)''')
    conn.run('CREATE EXTENSION IF NOT EXISTS pg_trgm')
    conn.run('''CREATE OR REPLACE FUNCTION meta.dc_number(v text) RETURNS numeric
        LANGUAGE plpgsql IMMUTABLE AS $$ BEGIN
        IF v IS NULL OR btrim(v) = '' THEN RETURN NULL; END IF;
        IF v !~ '^[+-]?([0-9]+([.][0-9]*)?|[.][0-9]+)([eE][+-]?[0-9]+)?$' THEN RETURN NULL; END IF;
        RETURN v::numeric;
        EXCEPTION WHEN invalid_text_representation OR numeric_value_out_of_range THEN RETURN NULL;
        END $$''')
    conn.run('''CREATE OR REPLACE FUNCTION meta.dc_date(v text) RETURNS date
        LANGUAGE plpgsql IMMUTABLE AS $$ DECLARE parts text[]; BEGIN
        IF v IS NULL THEN RETURN NULL; END IF;
        parts := regexp_match(btrim(v),'^([0-9]{4})[-/]([0-9]{1,2})[-/]([0-9]{1,2})($|[ T])');
        IF parts IS NULL THEN RETURN NULL; END IF;
        RETURN make_date(parts[1]::integer,parts[2]::integer,parts[3]::integer);
        EXCEPTION WHEN datetime_field_overflow OR invalid_text_representation THEN RETURN NULL;
        END $$''')
    for dataset, model in MODELS.items():
        current=conn.run('SELECT version FROM meta.query_models WHERE dataset=:d',d=dataset)
        if current and current[0][0]==SCHEMA_VERSION:
            continue
        table=model['table']; ident=table.replace('.','_')
        conn.run('BEGIN')
        try:
            for column,(kind,field) in model['fields'].items():
                expr=f"payload->>'{field}'"
                if kind=='numeric':expr=f'meta.dc_number({expr})'
                elif kind=='date':expr=f'meta.dc_date({expr})'
                conn.run(f'ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {column} {kind} GENERATED ALWAYS AS ({expr}) STORED')
            expr="coalesce(nullif(payload->>'updated_at',''),payload->>'created_at','')"
            conn.run(f'ALTER TABLE {table} ADD COLUMN IF NOT EXISTS sort_at text GENERATED ALWAYS AS ({expr}) STORED')
            fields=model.get('search',DEFAULT_SEARCH)
            expr=" || chr(31) || ".join(f"coalesce(payload->>'{field}','')" for field in fields)
            conn.run(f'ALTER TABLE {table} ADD COLUMN IF NOT EXISTS search_text text GENERATED ALWAYS AS ({expr}) STORED')
            key=model.get('key','id'); prefix='owner, ' if model.get('owner') else ''
            order=f'{prefix}sort_at DESC, {key}' if dataset.startswith('crm.') else f'{prefix}{key}'
            conn.run(f'CREATE INDEX IF NOT EXISTS q_{ident}_page ON {table} ({order})')
            conn.run(f'CREATE INDEX IF NOT EXISTS q_{ident}_search ON {table} USING gin (search_text gin_trgm_ops)')
            indexed=set(model['filters'])|{model[k] for k in ('date','amount') if k in model}
            for column in sorted(indexed):
                conn.run(f'CREATE INDEX IF NOT EXISTS q_{ident}_{column} ON {table} ({prefix}{column}, {key})')
            # Refresh stored generated values after conversion-function migrations.
            conn.run('UPDATE '+table+' SET payload=payload')
            conn.run('INSERT INTO meta.query_models(dataset,version) VALUES (:d,:v) ON CONFLICT(dataset) DO UPDATE SET version=excluded.version',d=dataset,v=SCHEMA_VERSION)
            conn.run('COMMIT')
        except Exception:
            conn.run('ROLLBACK');raise


def refresh_query_stats(conn):
    for dataset,model in MODELS.items():
        table=model['table']
        conditions=[f"CASE WHEN nullif(btrim(payload->>'{field}'),'') IS NOT NULL AND {col} IS NULL THEN 1 ELSE 0 END"
                    for col,(kind,field) in model['fields'].items() if kind!='text']
        invalid='coalesce(sum('+ '+'.join(conditions)+'),0)' if conditions else '0'
        count,bad,latest=conn.run(f'SELECT count(*), {invalid}, max(synced_at) FROM {table}')[0]
        conn.run("SELECT gin_clean_pending_list(:idx::regclass)",idx=table.split('.')[0]+'.q_'+table.replace('.','_')+'_search')
        conn.run('ANALYZE '+table)
        conn.run('UPDATE meta.query_models SET refreshed_at=coalesce(:t::timestamptz,now()),rows=:n,invalid_typed_values=:b WHERE dataset=:d',n=count,b=bad,d=dataset,t=latest)


def compile_query(dataset,params):
    from datetime import date
    from decimal import Decimal, InvalidOperation
    if dataset not in MODELS:raise ValueError('该数据集尚未启用结构化查询')
    m=MODELS[dataset];where=[];values={}
    try:
        limit=min(500,max(1,int(params.get('limit') or 100)));offset=max(0,int(params.get('offset') or 0))
    except (ValueError,TypeError):raise ValueError('limit / offset 必须是整数')
    allowed={'source','dataset','limit','offset','keyword'}|set(m['filters'])
    if m.get('owner'):
        allowed.add('owner')
        owner=str(params.get('owner') or '').strip()
        if not owner or not re.fullmatch(r'[A-Za-z0-9_@.-]+',owner) or owner.startswith('.'):
            raise ValueError('owner 必须是有效用户名')
        where.append('owner=:owner');values['owner']=owner
    if m.get('date'):
        allowed.update(['date_from','date_to'])
        for param,operator in [('date_from','>='),('date_to','<=')]:
            value=params.get(param)
            if value:
                try: values[param]=date.fromisoformat(value)
                except (ValueError,TypeError):raise ValueError(param+' 必须是 YYYY-MM-DD')
                where.append(f"{m['date']}{operator}:{param}")
        if values.get('date_from') and values.get('date_to') and values['date_from']>values['date_to']:
            raise ValueError('起始日期不能晚于结束日期')
    if m.get('amount'):
        allowed.update(['min_amount','max_amount','summary'])
        if params.get('summary') not in (None,'','0','1'):raise ValueError('summary 只能为 0 或 1')
        for param,operator in [('min_amount','>='),('max_amount','<=')]:
            value=params.get(param)
            if value not in (None,''):
                try:
                    number=Decimal(str(value))
                    if not number.is_finite():raise InvalidOperation
                except InvalidOperation:raise ValueError(param+' 必须是有限数字')
                values[param]=number;where.append(f"{m['amount']}{operator}:{param}")
        if 'min_amount' in values and 'max_amount' in values and values['min_amount']>values['max_amount']:
            raise ValueError('最小金额不能大于最大金额')
    unknown={k for k,v in params.items() if v not in ('',None) and k not in allowed}
    if unknown:raise ValueError('不支持的查询参数：'+','.join(sorted(unknown)))
    for field in m['filters']:
        if params.get(field) not in ('',None):where.append(f'{field}=:{field}');values[field]=str(params[field])
    kw=str(params.get('keyword') or '').strip()
    if kw:
        if len(kw)>200:raise ValueError('keyword 最多 200 个字符')
        values['keyword']='%'+kw.replace('!','!!').replace('%','!%').replace('_','!_')+'%'
        where.append("search_text LIKE :keyword ESCAPE '!'")
    condition=' WHERE '+' AND '.join(where) if where else ''
    key=m.get('key','id')
    order=f'sort_at DESC, {key}' if dataset.startswith('crm.') else (key+' DESC' if dataset=='agent.skill_invocations' else key)
    return m['table'],condition,values,order,limit,offset


_pool=queue.LifoQueue(maxsize=4)
_slots=threading.BoundedSemaphore(4)

@contextmanager
def query_connection():
    if not _slots.acquire(timeout=3):raise RuntimeError('数据库查询繁忙')
    conn=None;healthy=False
    try:
        try:conn=_pool.get_nowait()
        except queue.Empty:
            conn=pg8000.native.Connection(user=os.getenv('OFFICE_QUERY_USER','datacenter_reader'),
                password=os.environ['OFFICE_QUERY_PASSWORD'],host=os.getenv('OFFICE_QUERY_HOST','office-postgres'),
                database=os.getenv('OFFICE_QUERY_DB','office'),port=int(os.getenv('OFFICE_QUERY_PORT','5432')),timeout=8)
        yield conn
        healthy=True
    finally:
        if conn:
            if healthy:_pool.put_nowait(conn)
            else:
                try:conn.close()
                except Exception:pass
        _slots.release()


def query_structured(dataset,params,connection=None):
    table,condition,values,order,limit,offset=compile_query(dataset,params)
    def execute(conn):
        conn.run('BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY')
        try:
            conn.run("SET LOCAL statement_timeout='3000ms'")
            meta=conn.run('SELECT refreshed_at,rows,invalid_typed_values FROM meta.query_models WHERE dataset=:d',d=dataset)
            if not meta or not meta[0][0]:raise RuntimeError('该数据集尚未完成结构化同步')
            total=conn.run('SELECT count(*) FROM '+table+condition,**values)[0][0]
            rows=conn.run('SELECT payload FROM '+table+condition+' ORDER BY '+order+' LIMIT :page_limit OFFSET :page_offset',**values,page_limit=limit,page_offset=offset)
            summary={}
            if params.get('summary')=='1':
                columns=[col for col,(kind,_) in MODELS[dataset]['fields'].items() if kind=='numeric']
                totals=conn.run('SELECT '+','.join('sum('+col+')' for col in columns)+' FROM '+table+condition,**values)[0]
                summary={'summary':{col:str(value) if value is not None else None for col,value in zip(columns,totals)}}
            conn.run('COMMIT')
            return {**summary,'items':[r[0] for r in rows],'total':total,'limit':limit,'offset':offset,
                    'source':'postgresql','synced_at':meta[0][0].isoformat(),
                    'invalid_typed_values':meta[0][2]}
        except Exception:
            conn.run('ROLLBACK');raise
    if connection is not None:return execute(connection)
    with query_connection() as conn:return execute(conn)


def ensure_query_role(conn):
    """Provision the application reader independently from the ingestion owner."""
    password=os.getenv('OFFICE_QUERY_PASSWORD')
    if not password:return
    from pg8000.native import literal,identifier
    if not conn.run("SELECT 1 FROM pg_roles WHERE rolname='datacenter_reader'"):
        conn.run('CREATE ROLE datacenter_reader LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT')
    conn.run('ALTER ROLE datacenter_reader PASSWORD '+literal(password))
    # 数据中台「数据库直连」需要读全库：INHERIT 让 pg_read_all_data 生效，仍受只读约束。
    conn.run('ALTER ROLE datacenter_reader INHERIT')
    conn.run('GRANT pg_read_all_data TO datacenter_reader')
    conn.run('ALTER ROLE datacenter_reader SET default_transaction_read_only=on')
    conn.run("ALTER ROLE datacenter_reader SET statement_timeout='3s'")
    database=conn.run('SELECT current_database()')[0][0]
    conn.run('GRANT CONNECT ON DATABASE '+identifier(database)+' TO datacenter_reader')
    for schema in ('crm','cashflow','ledger','collab','agentic','meta'):
        conn.run('GRANT USAGE ON SCHEMA '+schema+' TO datacenter_reader')
    for table in [m['table'] for m in MODELS.values()]+['meta.query_models']:
        conn.run('GRANT SELECT ON '+table+' TO datacenter_reader')
