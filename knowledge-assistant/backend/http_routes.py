"""框架无关的知识库 HTTP 路由分发。

Web 框架适配层在完成认证后，将可信 ``username`` 和请求数据传入本模块；不得从
客户端请求体直接取得用户名。文件下载和 SSE 由宿主框架分别包装 ``document_file``
与 ``stream_ask`` 的返回值。
"""

from .knowledge import (
    kb_ask, kb_ask_stream, kb_chat_clear, kb_chat_history, kb_chat_sessions,
    kb_config_api, kb_dataset_manage, kb_delete, kb_doc_chunks, kb_doc_file,
    kb_datasets, kb_external_api_info, kb_list, kb_ragflow_bootstrap,
    kb_ragflow_save_chunk_config, kb_ragflow_sso, kb_ragflow_status,
    kb_reparse, kb_search, kb_upload, save_kb_config,
)


def dispatch_get(path: str, query: dict[str, str], username: str) -> dict:
    if path == "/knowledge-config":
        return kb_config_api()
    if path == "/knowledge/list":
        return kb_list(query.get("scope", "mine"), username)
    if path == "/knowledge/kbs":
        return kb_datasets(username)
    if path == "/knowledge/chat-history":
        return kb_chat_history(username, query.get("session_id", ""))
    if path == "/knowledge/external-info":
        return kb_external_api_info(username)
    if path == "/knowledge/doc-chunks":
        return kb_doc_chunks(query.get("dataset_id", ""), query.get("doc_id", ""), username)
    if path == "/ragflow/status":
        return kb_ragflow_status()
    if path == "/ragflow/sso":
        return kb_ragflow_sso(username)
    raise ValueError(f"未知知识库 GET 路由：{path}")


def dispatch_post(path: str, payload: dict, username: str, *, is_admin: bool = False) -> dict:
    if path == "/knowledge-config":
        if not is_admin:
            raise PermissionError("仅管理员可修改知识库配置")
        return save_kb_config(payload)
    if path == "/knowledge/upload":
        return kb_upload(payload, username)
    if path == "/knowledge/delete":
        return kb_delete(payload, username)
    if path == "/knowledge/search":
        return kb_search(payload, username)
    if path == "/knowledge/ask":
        return kb_ask(payload, username)
    if path == "/knowledge/reparse":
        return kb_reparse(payload, username)
    if path == "/knowledge/kbs":
        return kb_dataset_manage(payload, username)
    if path == "/knowledge/chat-sessions":
        return kb_chat_sessions(payload, username)
    if path == "/knowledge/chat-clear":
        return kb_chat_clear(username, payload.get("session_id", ""))
    if path == "/ragflow/bootstrap":
        if not is_admin:
            raise PermissionError("仅管理员可初始化 RAGFlow")
        return kb_ragflow_bootstrap(payload)
    if path == "/ragflow/chunk-config":
        if not is_admin:
            raise PermissionError("仅管理员可修改解析配置")
        return kb_ragflow_save_chunk_config(payload)
    raise ValueError(f"未知知识库 POST 路由：{path}")


def document_file(dataset_id: str, doc_id: str, username: str) -> tuple[str, bytes]:
    return kb_doc_file(dataset_id, doc_id, username)


def stream_ask(handler, payload: dict, username: str) -> None:
    """传入宿主的 SSE handler，复用原有 RAGFlow 流式问答实现。"""
    kb_ask_stream(handler, payload, username)
