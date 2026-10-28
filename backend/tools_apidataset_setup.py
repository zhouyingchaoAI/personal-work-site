#!/usr/bin/env python3
"""一次性脚本：在 FastGPT 中创建「API 文件库」(apiDataset) 并同步 RAGFlow 文档。

在 personal-work-site 容器内运行（可直连 fastgpt-sso / fastgpt-app）：
    docker exec personal-work-site python3 /app/backend/tools_apidataset_setup.py <cmd>
cmd: token | models | list | create | detail <dsId> | collections <dsId> | sync <dsId>
"""
import json
import os
import sys
import urllib.request
import urllib.error

FASTGPT_INTERNAL_URL = os.getenv("FASTGPT_INTERNAL_URL", "http://fastgpt-app:3000").rstrip("/")
FASTGPT_SSO_URL = os.getenv("FASTGPT_SSO_URL", "http://fastgpt-sso:3100").rstrip("/")
FASTGPT_SSO_SECRET = os.getenv("FASTGPT_SSO_SECRET", "office_fastgpt_sso_9Rm4Kv7Lx2Np8Qw")

APIDATASET_BASE = os.getenv("APIDATASET_BASE", "http://personal-work-site:8765/api/fastgpt/apidataset")
APIDATASET_TOKEN = os.getenv("APIDATASET_TOKEN", "fastgpt_ragflow_bridge_8Qw3Rm7Lx2Np")


def sso_token(username="admin", system=True):
    path = "/system-token" if system else "/login"
    payload = {"username": username, "name": "办公助手", "role": "superadmin"}
    req = urllib.request.Request(
        FASTGPT_SSO_URL + path,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json", "X-Office-SSO-Secret": FASTGPT_SSO_SECRET},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        return str(json.loads(r.read().decode("utf-8")).get("token") or "")


def call(path, payload=None, token="", method="POST"):
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        FASTGPT_INTERNAL_URL + path, data=data,
        headers={"Content-Type": "application/json", "Cookie": "fastgpt_token=" + token},
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            result = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "ignore")
        raise SystemExit(f"HTTP {e.code} {path}: {detail}")
    if int(result.get("code", 200) or 200) >= 400:
        raise SystemExit(f"ERR {path}: {result.get('message')}")
    return result.get("data")


def get_models(token):
    raw = call("/api/core/ai/model/getConfigJson", {}, token)
    cfg = json.loads(raw) if isinstance(raw, str) else raw

    def mtype(m):
        return m.get("type") or (m.get("metadata") or {}).get("type")

    vec = [m["model"] for m in cfg if mtype(m) == "embedding"]
    llm = [m["model"] for m in cfg if mtype(m) == "llm"]
    return cfg, vec, llm


def create_dataset(token):
    cfg, vec, llm = get_models(token)
    if not vec:
        raise SystemExit("没有可用的嵌入模型，无法创建 API 文件库")
    body = {
        "type": "apiDataset",
        "avatar": "core/dataset/commonDatasetColor",
        "name": "企业知识库（RAGFlow）",
        "intro": "引用外部 RAGFlow 企业知识库，文档在 RAGFlow 维护，FastGPT 通过 API 文件库同步。",
        "vectorModel": vec[0],
        "agentModel": (llm[0] if llm else vec[0]),
        "apiDatasetServer": {
            "apiServer": {"baseUrl": APIDATASET_BASE, "authorization": APIDATASET_TOKEN, "basePath": ""}
        },
    }
    data = call("/api/core/dataset/create", body, token)
    return data


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "token"
    token = sso_token()
    if cmd == "token":
        print("token_len", len(token))
    elif cmd == "models":
        cfg, vec, llm = get_models(token)
        print("embedding:", vec)
        print("llm:", llm)
    elif cmd == "list":
        data = call("/api/core/dataset/list", {"parentId": None}, token)
        for d in data:
            print(d.get("_id"), "|", d.get("name"), "|", d.get("type"))
    elif cmd == "create":
        print(json.dumps(create_dataset(token), ensure_ascii=False))
    elif cmd == "detail":
        print(json.dumps(call("/api/core/dataset/detail?id=" + sys.argv[2], None, token, "GET"), ensure_ascii=False)[:1500])
    elif cmd == "apilist":
        # list files via configured apiServer for a dataset
        print(json.dumps(call("/api/core/dataset/apiDataset/list", {"datasetId": sys.argv[2], "parentId": ""}, token), ensure_ascii=False))
    elif cmd == "import":
        ds = sys.argv[2]
        files = call("/api/core/dataset/apiDataset/list", {"datasetId": ds, "parentId": ""}, token)
        body = {
            "datasetId": ds,
            "parentId": None,
            "apiFiles": files,
            "trainingType": "chunk",
            "chunkSettings": {"trainingType": "chunk"},
        }
        print(json.dumps(call("/api/core/dataset/collection/create/apiCollectionV2", body, token), ensure_ascii=False))
    elif cmd == "fixembed":
        raw = call("/api/core/ai/model/getConfigJson", {}, token)
        cfg = json.loads(raw) if isinstance(raw, str) else raw
        for m in cfg:
            meta = m.get("metadata") or m
            if meta.get("type") == "embedding":
                meta.setdefault("defaultToken", 512)
                meta.setdefault("maxToken", 3000)
                meta.setdefault("weight", 0)
                meta["defaultToken"] = 512
                meta["maxToken"] = 3000
        call("/api/core/ai/model/updateWithJson", {"config": json.dumps(cfg, ensure_ascii=False)}, token)
        print("embedding model patched: defaultToken=512 maxToken=3000")
    elif cmd == "retrain":
        ds = sys.argv[2]
        data = call("/api/core/dataset/collection/list", {"datasetId": ds, "parentId": None, "pageSize": 50, "offset": 0}, token)
        for c in data["data"]:
            if c.get("type") == "folder":
                continue
            try:
                r = call("/api/core/dataset/collection/create/reTrainingCollection", {"collectionId": c["_id"]}, token)
                print("retrain", c["name"][:20], "->", r)
            except SystemExit as e:
                print("retrain-fail", c["name"][:20], e)
    elif cmd == "autosync":
        ds = sys.argv[2]
        for path in ("/api/core/dataset/update",):
            try:
                r = call(path, {"id": ds, "autoSync": True}, token)
                print("autosync on ->", path, r)
                break
            except SystemExit as e:
                print("fail", path, e)
    elif cmd == "collections":
        print(json.dumps(call("/api/core/dataset/collection/list", {"datasetId": sys.argv[2], "parentId": None, "pageSize": 30, "offset": 0}, token), ensure_ascii=False)[:2000])
    else:
        print("unknown cmd")


if __name__ == "__main__":
    main()
