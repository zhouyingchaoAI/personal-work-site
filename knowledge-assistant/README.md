# 知识库助手抽取包

这是从办公助手中独立整理出的“知识库助手 + RAGFlow”源码包，不包含 FastGPT。
原平台文件保持不动；本目录用于迁移、二次开发或在其他宿主系统中重新接入。

## 目录

| 路径 | 内容 |
| --- | --- |
| `backend/knowledge.py` | 数据集、文档上传/解析、检索、问答、引用、会话、RAGFlow 用户与团队隔离的核心实现 |
| `backend/http_routes.py` | REST/SSE 路由分发适配；接入 FastAPI、Flask、Django 或现有 HTTP 服务时使用 |
| `backend/mcp_tools.py` | `knowledge.datasets/docs/search/ask/delete` MCP 工具定义与执行入口 |
| `frontend/KnowledgeBaseView/` | Vue 3 + Element Plus 知识库管理、对话、引用预览和外部调用说明页面 |
| `frontend/personalWorkApi.knowledge.ts` | 仅包含知识库所需接口和 TypeScript 类型 |
| `frontend/authSession.ts`、`frontend/markdown.ts` | 页面运行所需的最小鉴权状态与 Markdown/表格渲染工具 |
| `tests/upstream/` | 从原工程保留的知识库选择、引用显示回归测试；它们依赖原工程共享运行时 |
| `tests/test_extraction_manifest.py` | 不依赖原工程的抽取完整性与无 FastGPT 集成检查 |

## 迁移接入顺序

1. 将 `backend/knowledge.py` 纳入目标服务的运行时，并提供其依赖的宿主函数：配置读写、用户/管理员判断、模型调用、文件存储、会话存储与 JSON/HTTP 工具。现系统通过共享运行时注入这些能力；新系统建议显式依赖注入。
2. 在认证完成后，调用 `backend/http_routes.py` 的 `dispatch_get`、`dispatch_post`。用户名必须取自服务端认证主体，不能信任前端传入的用户名。
3. 将 `backend/mcp_tools.py` 的 `TOOLS` 注册到 MCP Server；执行时由认证层向 `execute_knowledge_tool` 注入用户名。
4. 将 `frontend/` 接入 Vue 3 项目，配置 `VITE_PERSONAL_WORK_BACKEND_URL`；未配置时默认使用原平台兼容路径 `/personal-work-api`。
5. 在管理端配置 RAGFlow 内网 API 地址、公开地址和服务账号 Key，再通过 `/ragflow/bootstrap` 初始化企业共享库与用户租户。

## 边界与安全要求

- RAGFlow 负责 DeepDoc 解析、切片、检索和对话；网关负责用户身份、个人/共享库范围、会话和 API 适配。
- 服务账号 Key、用户 API Key 和用户密码不得返回前端或写入日志。迁移后应将现有 JSON 映射迁至数据库加密字段或 Secret Manager。
- 个人库请求必须使用当前用户的 RAGFlow 身份；企业共享库的写、删、重解析必须由管理员拦截。
- 本目录特意不包含 FastGPT 连接器、同步逻辑或任何 FastGPT 密钥。

完整架构与迁移说明见原项目的 `docs/knowledge-ragflow-extraction-design.md`。
