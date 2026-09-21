"""知识库助手的独立 MCP 工具适配层。

宿主 MCP Server 只需把 ``TOOLS`` 注册为工具定义，并在收到工具调用时调用
``execute_knowledge_tool(name, arguments, username)``。认证、限流与审计属于宿主。
"""

from .knowledge import kb_ask, kb_datasets, kb_delete, kb_list, kb_search


TOOLS = [
    {
        "name": "knowledge.datasets",
        "title": "查看知识库列表",
        "description": "列出当前用户可用的知识库（含文档数、切片数）。",
        "parameters": {},
        "safe": True,
    },
    {
        "name": "knowledge.docs",
        "title": "查看知识库文档",
        "description": "按范围列出知识库中的文档。",
        "parameters": {"scope": "范围：mine(默认)/shared/all，可选"},
        "safe": True,
    },
    {
        "name": "knowledge.search",
        "title": "检索知识库",
        "description": "在知识库中做语义检索，返回命中片段与来源，用于引用溯源。",
        "parameters": {"query": "检索关键词，必填", "top_k": "返回片段数，默认 5，可选", "kb_ids": "限定知识库 ID 数组，可选"},
        "safe": True,
    },
    {
        "name": "knowledge.ask",
        "title": "知识库问答",
        "description": "基于知识库检索结果回答问题，返回答案与引用来源。",
        "parameters": {"question": "问题，必填", "top_k": "检索片段数，默认 5，可选", "kb_ids": "限定知识库 ID 数组，可选"},
        "safe": True,
    },
    {
        "name": "knowledge.delete",
        "title": "删除知识库文档",
        "description": "按 ID 删除一篇知识库文档（共享库需管理员）。",
        "parameters": {"id": "文档 ID", "scope": "范围，可选"},
        "safe": False,
    },
]


def execute_knowledge_tool(name: str, arguments: dict | None, username: str) -> dict:
    """执行一个知识库 MCP 工具；``username`` 必须由已认证的宿主注入。"""
    args = arguments or {}
    if name == "knowledge.datasets":
        return kb_datasets(username)
    if name == "knowledge.docs":
        return kb_list(str(args.get("scope", "mine") or "mine"), username)
    if name == "knowledge.search":
        return kb_search(args, username)
    if name == "knowledge.ask":
        return kb_ask(args, username)
    if name == "knowledge.delete":
        return kb_delete(args, username)
    raise ValueError(f"不支持的知识库工具：{name}")
