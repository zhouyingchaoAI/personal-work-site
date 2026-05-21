# 犇犇 AI 原生办公平台架构设计

> 版本：v1.0
> 日期：2026-05-19
> 目标：将现有"传统 Web + AI 浮窗"升级为"Skill Runtime + Agent Runtime + Memory Layer + Workflow Engine"的 AI 原生架构

---

## 1. 核心原则

1. **交互 First，Chat Second**：保留现有页面、按钮、表单，AI 作为增强层嵌入
2. **所有操作 Skill 化**：前端按钮、Agent 调用、自动任务最终都走统一 Skill Runtime
3. **先审计，后记忆，再自动化**：Skill 调用全记录 → Memory 持久化 → Workflow 自动编排
4. **TDD 优先**：新增核心模块先写测试，再实现

---

## 2. 分层架构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  前端层 (UI + Agent 模式)                                                    │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────────────┐   │
│  │ 传统页面     │ │ Agent 对话   │ │ Skill 卡片   │ │ 任务进度时间线       │   │
│  │ (表单/表格)  │ │ (侧边栏常驻) │ │ (结果展示)   │ │ (Workflow 运行)     │   │
│  └──────┬──────┘ └──────┬──────┘ └──────┬──────┘ └─────────────────────┘   │
│         └─────────────────┴─────────────────┘                                │
│                              统一 UI Patch 协议                               │
└─────────────────────────────────────┬───────────────────────────────────────┘
                                      │
┌─────────────────────────────────────┼───────────────────────────────────────┐
│  API 网关层 (/api/*)                                                         │
│  /agent/chat  /agent/sessions  /skills/execute  /memory/*  /workflows/*     │
└─────────────────────────────────────┬───────────────────────────────────────┘
                                      │
┌─────────────────────────────────────┼───────────────────────────────────────┐
│  Agent Runtime (backend/agent_runtime.py)                                    │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────────────┐   │
│  │ Session 管理 │ │ 消息历史     │ │ Skill 路由   │ │ 上下文组装 (Memory)  │   │
│  │ 创建/恢复    │ │ 持久化      │ │ 发现/执行    │ │ + Skill Docs        │   │
│  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────────────┘   │
│  统一响应协议: {reply, actions[], ui_patches[], memory_updates[], requires_confirmation} │
└─────────────────────────────────────┬───────────────────────────────────────┘
                                      │
┌─────────────────────────────────────┼───────────────────────────────────────┐
│  Skill Runtime (backend/skill_runtime.py)                                    │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────────────┐   │
│  │ Skill 注册表 │ │ 参数校验     │ │ 安全确认门   │ │ 审计记录             │   │
│  │ (装饰器注册) │ │ (JSONSchema)│ │ (safe/unsafe)│ │ (skill_invocations) │   │
│  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────────────┘   │
└─────────────────────────────────────┬───────────────────────────────────────┘
                                      │
┌─────────────────────────────────────┼───────────────────────────────────────┐
│  Memory Layer (backend/memory.py)                                            │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────────────┐   │
│  │ 用户偏好     │ │ 事件记忆     │ │ 工作上下文   │ │ 检索引擎 (FTS5)      │   │
│  │ 风格/习惯    │ │ 周报/日记   │ │ 当前任务     │ │ 向量库后置          │   │
│  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────────────┘   │
│  Skills: memory.remember / memory.search / memory.forget / memory.summarize │
└─────────────────────────────────────┬───────────────────────────────────────┘
                                      │
┌─────────────────────────────────────┼───────────────────────────────────────┐
│  Workflow Engine (backend/workflows.py)                                      │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────────────┐   │
│  │ 工作流定义   │ │ 步骤编排     │ │ 变量传递     │ │ 状态恢复             │   │
│  │ JSON/YAML    │ │ 顺序/分支   │ │ {{prev.res}}│ │ 中断后继续          │   │
│  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────────────┘   │
│  例: weekly.from_diary → diary.list → weekly.compose → weekly.preview       │
└─────────────────────────────────────┬───────────────────────────────────────┘
                                      │
┌─────────────────────────────────────┴───────────────────────────────────────┐
│  业务 Skill 层 (backend/skills/ 或现有 backend/*.py)                          │
│  weekly.* | trip.* | diary.* | mail.* | forum.* | news.* | utils.* | reports.*
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. 核心协议

### 3.1 Agent 响应协议

Agent Runtime 返回统一结构，前端只消费此协议：

```json
{
  "session_id": "sess_xxx",
  "reply": "给用户看的自然语言回复",
  "actions": [
    {"type": "skill_call", "name": "weekly.compose", "arguments": {...}}
  ],
  "ui_patches": [
    {"op": "set_field", "selector": "#weeklySummary", "value": "..."},
    {"op": "show_card", "card_type": "preview", "data": {...}},
    {"op": "navigate", "task": "weekly"},
    {"op": "append_message", "role": "assistant", "content": "..."}
  ],
  "memory_updates": [
    {"action": "remember", "type": "preference", "content": "..."}
  ],
  "requires_confirmation": false,
  "confirmation_context": null
}
```

### 3.2 UI Patch 操作类型

| op | 作用 | 示例 |
|----|------|------|
| `set_field` | 填充表单字段 | 周报内容自动填入 |
| `show_card` | 展示结果卡片 | 预览图、邮件草稿 |
| `navigate` | 切换页面 | 生成完周报跳转到预览页 |
| `append_message` | 追加对话消息 | Agent 回复 |
| `show_timeline` | 显示任务进度 | Workflow 运行中 |
| `request_confirm` | 请求用户确认 | 危险操作确认卡 |

### 3.3 Skill 注册协议

使用装饰器自动注册，替代手动维护 `skill_defs()` 列表：

```python
from backend.skill_runtime import skill

@skill(
    name="weekly.compose",
    module="周报",
    title="编写周报草稿",
    description="将原始工作内容整理成周报三段式结构",
    parameters={"raw_work": "string", "period": "string?"},
    safe=True,
)
def weekly_compose(arguments, username):
    ...
```

---

## 4. Memory Layer 设计

### 4.1 记忆类型

| type | 用途 | 示例 |
|------|------|------|
| `preference` | 用户偏好 | "周报编号清晰、体现工作量" |
| `event` | 事件记录 | 某次出差报告摘要 |
| `fact` | 事实知识 | "用户负责算法平台开发" |
| `context` | 当前上下文 | 本次对话主题 |
| `workflow_state` | 工作流状态 | 步骤 2/5，等待用户输入 |

### 4.2 Memory Skill

- `memory.remember` — 保存记忆（safe）
- `memory.search` — 检索记忆（safe，FTS5）
- `memory.forget` — 删除记忆（unsafe，需确认）
- `memory.summarize` — 总结近期记忆（safe）

### 4.3 Agent 上下文注入

每次 Agent 调用前自动组装：

```
[System Prompt]
[用户偏好 Memory (top 5)]
[近期相关事件 Memory (top 5)]
[当前会话历史 (最近 10 轮)]
[可用 Skill 文档]
[用户输入]
```

---

## 5. Workflow Engine 设计

### 5.1 工作流定义格式

```json
{
  "id": "weekly.from_diary",
  "name": "根据日记生成周报",
  "steps": [
    {"id": "get_date", "skill": "utils.get_date", "arguments": {}},
    {"id": "list_diary", "skill": "diary.list", "arguments": {"start": "{{get_date.result.week_start}}", "end": "{{get_date.result.week_end}}"}},
    {"id": "compose", "skill": "weekly.compose", "arguments": {"raw_work": "{{list_diary.result.summary}}"}},
    {"id": "preview", "skill": "weekly.preview", "arguments": {"period": "{{get_date.result.week_range}}", "weekly_summary": "{{compose.result.weekly_summary}}"}}
  ],
  "on_error": "pause",
  "requires_confirmation_at": ["preview"]
}
```

### 5.2 状态机

```
pending → running → paused → running → completed
                    ↓
                 failed (可重试)
```

---

## 6. 实施路线图

### Phase 1：Agent Runtime + Memory Layer（当前）
- [ ] 新建 `backend/agent_runtime.py`
- [ ] 新建 `backend/memory.py`（Memory Skill + FTS5 检索）
- [ ] 修改 `backend/skills_agent.py`：agent_chat 走新 runtime
- [ ] 新增 API：`/api/agent/chat`, `/api/agent/sessions`
- [ ] 测试：Agent 会话 CRUD、Memory 检索、Skill 调用带记忆

### Phase 2：Workflow Engine
- [ ] 新建 `backend/workflows.py`
- [ ] 实现工作流解析、执行、变量传递
- [ ] 新增复合 Skill：`weekly.from_diary`, `mail.summarize_and_reply`
- [ ] 前端任务时间线组件

### Phase 3：前端 AI 原生体验
- [ ] Agent 侧边栏常驻
- [ ] UI Patch 协议消费
- [ ] Skill 结果卡片化
- [ ] Memory 管理页
- [ ] 确认卡 + 参数 diff

---

## 7. 数据流示例

### 场景：用户说"帮我根据本周日记写周报"

```
用户输入 → Agent Runtime
              ↓
        [组装上下文: Memory + Skill Docs + 历史]
              ↓
        LLM 决策 → 需要调用 workflow "weekly.from_diary"
              ↓
        Workflow Engine 执行:
          Step 1: utils.get_date → {week_start, week_end, week_range}
          Step 2: diary.list(start=..., end=...) → [日记列表]
          Step 3: weekly.compose(raw_work=日记摘要) → {weekly_summary, ...}
          Step 4: weekly.preview(...) → {file, preview_image_url}
              ↓
        Agent Runtime 组装响应:
          reply: "已根据本周 5 篇日记生成周报预览"
          ui_patches: [
            {op: "navigate", task: "weekly"},
            {op: "set_field", selector: "#previewArea", value: preview_image_url},
            {op: "show_card", card_type: "preview", data: {...}}
          ]
          memory_updates: [
            {action: "remember", type: "event", content: "2026.05.11-05.15 周报已生成"}
          ]
              ↓
        前端渲染 → 跳转周报页 + 显示预览 + 追加对话
```

---

## 8. 关键文件清单

| 文件 | 职责 | 状态 |
|------|------|------|
| `backend/agent_runtime.py` | Agent 会话、消息、上下文、响应协议 | 新建 |
| `backend/memory.py` | Memory CRUD、FTS5 检索、Memory Skill | 新建 |
| `backend/workflows.py` | 工作流定义、执行、状态管理 | 新建 |
| `backend/skill_runtime.py` | Skill 注册、执行、审计（已有，需增强） | 增强 |
| `backend/db.py` | SQLite 基础（已有） | 已有 |
| `frontend/js/agent.js` | Agent 对话、UI Patch 消费 | 新建 |
| `docs/ARCHITECTURE.md` | 本文档 | 已有 |
