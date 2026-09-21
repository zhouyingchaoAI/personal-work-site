# 智能写作助手 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 AI 智能办公助手中新增完整的智能写作助手，支持文件素材、知识库参考、模板、历史、改写和导出。

**Architecture:** 后端新增 `backend/writing.py`，沿用现有 runtime 模块加载、用户目录落盘、`assistant_settings()` 调用模型、`kb_search()` 检索知识库。前端新增 `WritingAssistantView`，挂到 `/workspace/writing` 菜单，复用 `personalWorkApi.ts` 的 request/post 封装。

**Tech Stack:** Python 标准库 + 现有 python-docx/openpyxl/PDF 解析兜底；Vue 3 + TypeScript + Element Plus；现有手写 HTTP server。

## Global Constraints

- 不新增独立服务，不影响现有周报、出差、知识库、邮件助手。
- 用户只能访问自己的写作上传、历史和模板。
- 上传文件不自动入知识库，只作为写作素材。
- 勾选知识库时复用现有知识库权限与检索逻辑。
- 生成结果保留引用来源和素材来源。
- 先用非流式生成，页面提供清晰 loading/error 状态。

---

### Task 1: 后端写作领域服务

**Files:**
- Create: `backend/writing.py`
- Modify: `backend/runtime.py`
- Test: `tests/unit/test_writing_assistant.py`

**Interfaces:**
- Produces: `writing_templates(username)`, `writing_save_template(payload, username)`, `writing_history(username)`, `writing_get_history(item_id, username)`, `writing_upload(payload, username)`, `writing_generate_outline(payload, username)`, `writing_generate(payload, username)`, `writing_rewrite(payload, username)`, `writing_export(payload, username)`, `writing_delete_history(payload, username)`.
- Consumes: `assistant_settings()`, `normalize_assistant_output()`, `kb_search(payload, username)`, `user_profile_dir(username)`.

- [ ] Write failing unit tests for upload parsing, template/history persistence, knowledge injection, and export.
- [ ] Run `python3 -m unittest tests.unit.test_writing_assistant -v` and verify failure because `backend.writing` is missing.
- [ ] Implement `backend/writing.py` with JSON file storage under `user_data/<username>/writing`.
- [ ] Add `writing.py` to `backend/runtime.py` module list.
- [ ] Run unit tests and verify pass.

### Task 2: HTTP API 接入

**Files:**
- Modify: `backend/server.py`
- Test: `tests/unit/test_writing_routes_static.py`

**Interfaces:**
- GET: `/api/writing/templates`, `/api/writing/history`, `/api/writing/history-item?id=...`, `/api/writing/download?id=...&format=...`
- POST: `/api/writing/upload`, `/api/writing/templates`, `/api/writing/outline`, `/api/writing/generate`, `/api/writing/rewrite`, `/api/writing/export`, `/api/writing/delete`

- [ ] Write static route regression tests.
- [ ] Run tests and verify routes are absent.
- [ ] Wire GET/POST routes in `backend/server.py` with `require_user()`.
- [ ] Run route tests and backend unit tests.

### Task 3: 前端 API、菜单和页面

**Files:**
- Modify: `ai-office-assistant-web/src/layout/menu.ts`
- Modify: `ai-office-assistant-web/src/views/WorkspaceView/index.vue`
- Modify: `ai-office-assistant-web/src/services/personalWorkApi.ts`
- Create: `ai-office-assistant-web/src/views/WritingAssistantView/index.vue`
- Create: `ai-office-assistant-web/src/views/WritingAssistantView/index.scss`
- Test: `tests/unit/test_writing_frontend.py`

**Interfaces:**
- Produces menu id `writing` and visible route `/workspace/writing`.
- Produces API helpers: `getWritingTemplates`, `saveWritingTemplate`, `getWritingHistory`, `uploadWritingFile`, `generateWritingOutline`, `generateWritingDraft`, `rewriteWritingDraft`, `exportWritingDraft`, `deleteWritingHistory`.

- [ ] Write frontend static tests for menu, WorkspaceView, API helpers, page controls.
- [ ] Run tests and verify failure.
- [ ] Add menu/API/page implementation.
- [ ] Run frontend static tests.

### Task 4: Verification and deployment refresh

**Files:**
- Existing app files only.

- [ ] Run `python3 -m unittest tests.unit.test_writing_assistant tests.unit.test_writing_routes_static tests.unit.test_writing_frontend -v`.
- [ ] Run `.venv/bin/python -m pytest` or existing unit command if available.
- [ ] Run `npm run build` in `ai-office-assistant-web`.
- [ ] Rebuild/restart `personal-work-site` container only after build passes.
