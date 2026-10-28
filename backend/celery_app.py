"""联指经营助手的 Celery 应用与异步任务。

独立入口（不由 runtime 载入 HTTP 服务）：worker 容器执行
``celery -A backend.celery_app worker -B``。任务体通过 ``backend.runtime`` 复用
主应用的共享命名空间（crm_* 与存储辅助函数），import runtime 不会绑定端口。

broker/backend 使用 REDIS_URL；未配置时退回内存 broker，仅供本地降级，不建议生产。
"""
import os

from celery import Celery
from celery.schedules import crontab

_REDIS_URL = os.getenv("REDIS_URL", "").strip()
_BROKER = _REDIS_URL or "memory://"
_BACKEND = _REDIS_URL or "cache+memory://"

celery_app = Celery("crm", broker=_BROKER, backend=_BACKEND)
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone=os.getenv("TZ", "Asia/Shanghai"),
    enable_utc=False,
    task_default_queue="crm",
    broker_connection_retry_on_startup=True,
    beat_schedule={
        "crm-daily-decay-scan": {
            "task": "backend.celery_app.crm_daily_decay_scan",
            "schedule": crontab(hour=7, minute=30),  # 每日 07:30 扫描关系衰减
        },
    },
)


def _runtime():
    """惰性载入共享命名空间，避免 worker 启动即拉起全部依赖。"""
    import backend.runtime as runtime
    return runtime


@celery_app.task(name="backend.celery_app.crm_sync_graph_task", ignore_result=True)
def crm_sync_graph_task(username):
    """写操作后异步把该用户关系子图同步进 Neo4j。"""
    runtime = _runtime()
    try:
        return bool(runtime.crm_graph_sync_user(username))
    except Exception:
        return False


@celery_app.task(name="backend.celery_app.crm_daily_decay_scan")
def crm_daily_decay_scan():
    """遍历所有用户，重算关系强度/衰减并刷新总览缓存与图谱。"""
    runtime = _runtime()
    data_dir = runtime.USER_DATA_DIR
    scanned = 0
    if not data_dir.exists():
        return {"scanned": 0}
    for entry in data_dir.iterdir():
        if not entry.is_dir() or not (entry / "crm").is_dir():
            continue
        username = entry.name
        try:
            runtime.crm_overview(username)  # 内部会重算并落盘
            runtime.crm_cache_invalidate(username)
            runtime.crm_graph_sync_user(username)
            scanned += 1
        except Exception:
            continue
    return {"scanned": scanned}
