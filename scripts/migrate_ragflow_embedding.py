#!/usr/bin/env python3
"""把 RAGFlow 存量知识库迁移到统一配置的 Xinference 嵌入模型。

用法（宿主机）：docker exec -i personal-work-site python3 - < scripts/migrate_ragflow_embedding.py

流程：扫描服务租户 + 全部用户租户的数据集 → 跳过已是目标嵌入/有文档解析中的库 →
下载原件备份到 user_data/kb_migration_backup/ → 删除文档 → 切换嵌入模型
（孤儿 chunk 计数导致拒绝时删库重建）→ 重新上传触发解析。
"""
import urllib.request
from pathlib import Path

from backend import runtime

config = runtime.read_config()
TARGET = f"{config.get('xinference_embedding_model', '')}@Xinference"
if TARGET == "@Xinference":
    raise SystemExit("统一配置里没有嵌入模型，先在设置页「统一模型服务」执行一键应用")

settings = runtime.kb_embedding_settings()
backup = Path("/app/user_data/kb_migration_backup")
backup.mkdir(parents=True, exist_ok=True)


def download(s, ds_id, doc, dest_dir):
    url = s["ragflow_url"].rstrip("/") + f"/api/v1/datasets/{ds_id}/documents/{doc['id']}"
    req = urllib.request.Request(url, headers={"Authorization": "Bearer " + s["ragflow_api_key"]})
    raw = urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req, timeout=300).read()
    dest_dir.mkdir(parents=True, exist_ok=True)
    (dest_dir / doc["name"]).write_bytes(raw)
    return raw


rounds = [("shared", settings)]
for username, entry in runtime._kb_mapping("ragflow_accounts.json").items():
    if entry.get("api_key"):
        rounds.append((username, {**settings, "ragflow_api_key": entry["api_key"]}))

seen = set()
for owner, s in rounds:
    try:
        datasets = runtime._ragflow_request(s, "GET", "/api/v1/datasets?page=1&page_size=200") or []
    except ValueError as exc:
        print(f"[跳过] {owner}: {exc}")
        continue
    for ds in datasets:
        if ds["id"] in seen:
            continue
        seen.add(ds["id"])
        if str(ds.get("embedding_model", "")) == TARGET:
            continue
        docs = (runtime._ragflow_request(s, "GET", f"/api/v1/datasets/{ds['id']}/documents?page=1&page_size=200") or {}).get("docs", [])
        # FAIL（run=4）的文档允许迁移（重传后重新解析），只跳过真正在跑的。
        parsing = [
            d for d in docs
            if str(d.get("run", "")).upper() not in ("DONE", "3", "FAIL", "4", "CANCEL", "2")
            and float(d.get("progress", 0) or 0) < 1
        ]
        if parsing:
            print(f"[跳过] {owner}《{ds['name']}》：{len(parsing)} 个文档解析中，请稍后重跑本脚本")
            continue
        files = []
        for doc in docs:
            raw = download(s, ds["id"], doc, backup / f"{owner}-{ds['name']}")
            files.append((doc["name"], raw))
        if docs:
            runtime._ragflow_request(s, "DELETE", f"/api/v1/datasets/{ds['id']}/documents", {"ids": [d["id"] for d in docs]})
        ds_id = ds["id"]
        try:
            runtime._ragflow_request(s, "PUT", f"/api/v1/datasets/{ds_id}", {"embedding_model": TARGET})
        except ValueError as exc:
            # 孤儿 chunk 计数残留：删库重建（个人库缓存键清掉后按需自动重建）
            print(f"[重建] {owner}《{ds['name']}》：{str(exc)[:60]}")
            runtime._ragflow_request(s, "DELETE", "/api/v1/datasets", {"ids": [ds_id]})
            mapping = runtime._kb_mapping("ragflow_datasets.json")
            mapping = {k: v for k, v in mapping.items() if v != ds_id}
            runtime._kb_mapping_save("ragflow_datasets.json", mapping)
            if owner == "shared":
                cfg = runtime.read_config()
                cfg.pop("knowledge_ragflow_dataset_id", None)
                runtime.write_config(cfg)
                ds_id = runtime._ragflow_shared_dataset_id(settings)
            else:
                ds_id = runtime._ragflow_user_dataset_id(s, owner)
        for name, raw in files:
            runtime._ragflow_upload(name, raw, s, ds_id, owner)
        print(f"[完成] {owner}《{ds['name']}》：{len(files)} 个文档已切到 {TARGET} 并重新解析")
print("迁移结束。")
