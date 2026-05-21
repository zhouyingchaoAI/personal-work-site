# personal-work-site AI 原生改造开发清单

> 目标：把当前“传统办公 Web + AI 浮窗”升级为“Skill Runtime + Agent Runtime + Memory Layer + Workflow Engine + Long-term History”的 AI 原生办公平台。

## 总原则

1. **交互 First，Chat Second**：保留现有页面、按钮、表单，AI 能力作为增强层嵌入，不用聊天替代表单。
2. **所有软件操作 Skill 化**：前端按钮、Agent 调用、自动任务最终都走统一 Skill Runtime。
3. **先审计，后记忆，再自动化**：先记录 Skill 调用与 Agent 会话，再做长期 Memory，最后做 Workflow 自动编排。
4. **TDD 优先**：新增核心模块必须先写测试，再实现。
5. **每轮开发必须更新状态文件**：`.ai-native-dev-state.json` 是自动续跑入口，任何中断前都要写入当前阶段、完成项、下一步。

---

## Phase 0：工程化与测试底座

- [ ] 新增 `scripts/run_tests.sh`，统一使用 `python3 -m unittest discover`。
- [ ] 新增 `tests/` 测试目录。
- [ ] 增加 Skill 注册回归测试：Skill 名称唯一、必要字段完整、安全字段存在。
- [ ] 增加 Agent Skill 调用解析测试：JSON、Markdown JSON、非法文本。
- [ ] 增加 SQLite DB 初始化测试。
- [ ] 增加 CI/本地测试说明文档。

验收：

```bash
./scripts/run_tests.sh
```

全部通过。

---

## Phase 1：Skill Runtime 统一入口

- [ ] 新增 `backend/skill_runtime.py`。
- [ ] 定义 `SkillDefinition` 数据结构。
- [ ] 定义 `SkillRegistry`：注册、查询、导出、校验。
- [ ] 把现有 `skill_defs()` 逐步迁移到 Registry。
- [ ] 新增统一执行函数：`run_skill(name, arguments, username, source, session_id)`。
- [ ] 增加参数校验与安全级别。
- [ ] 新增 `/api/skills/execute`。
- [ ] 保留旧 API，但内部转调 Skill。
- [ ] Skill 执行结果统一返回 `invocation_id/result/artifacts/requires_confirmation`。

验收：

- 前端旧功能不受影响；
- `/api/skills/execute` 可执行 `utils.get_date`、`diary.list`、`weekly.compose`；
- 所有 Skill 调用可被记录。

---

## Phase 2：长期历史与审计

- [ ] 新增 `backend/db.py`，使用 SQLite 存储 AI 原生运行状态。
- [ ] 新建表：`agent_sessions`、`agent_messages`、`skill_invocations`、`memory_items`。
- [ ] 每次 Agent 对话写入 `agent_messages`。
- [ ] 每次 Skill 调用写入 `skill_invocations`。
- [ ] 增加 `/api/agent-sessions` 查询历史会话。
- [ ] 增加 `/api/skill-invocations` 查询 Skill 调用历史。
- [ ] 前端系统 Skill 页显示最近调用记录。

验收：

- 用户能查看“犇犇最近帮我做过什么”；
- 每次发邮件、生成报告、保存日记都有审计记录。

---

## Phase 3：Memory Layer

- [ ] 新增 `backend/memory.py`。
- [ ] 支持 `memory.remember` Skill。
- [ ] 支持 `memory.search` Skill。
- [ ] 支持用户偏好 Memory：周报风格、常用收件人、常用表达、常用工作分类。
- [ ] 支持事件 Memory：历史周报、日记、邮件摘要、论坛讨论。
- [ ] 第一阶段用 SQLite FTS5；向量库后置。
- [ ] Agent 每轮调用前自动注入相关 Memory。
- [ ] 前端增加“记住这个偏好 / 忘记 / 纠正”入口。

验收：

- 用户说“按我常用周报风格写”，Agent 能检索偏好；
- 用户说“参考上次出差报告”，Agent 能找到历史记录。

---

## Phase 4：Workflow Skill / Skill 调 Skill

- [ ] 新增 `backend/workflows.py`。
- [ ] 定义 Workflow JSON 格式。
- [ ] 支持步骤间变量引用：`{{previous.result.xxx}}`。
- [ ] 支持安全中断确认。
- [ ] 支持失败重试、恢复运行。
- [ ] 新增 Workflow Skill：`weekly.from_diary_to_preview`。
- [ ] 新增 Workflow Skill：`mail.summarize_and_reply_draft`。
- [ ] 前端展示 Workflow 运行进度。

验收：

- 一句话“根据本周日记生成周报预览”能自动执行：`utils.get_date → diary.list → weekly.compose → weekly.preview`。

---

## Phase 5：Agent Runtime 标准化

- [ ] 新增 `backend/agent_runtime.py`。
- [ ] 引入 Agent Session ID。
- [ ] Agent 响应统一结构：`reply/actions/ui_patches/memory_updates`。
- [ ] Skill 参数先校验再执行。
- [ ] 写入/外部动作必须走确认卡。
- [ ] Agent 可恢复上次任务。
- [ ] Agent 支持按页面/角色裁剪可用 Skill。
- [ ] 前端不再靠 Skill 名称大量分支，而是消费统一 `ui_patches`。

验收：

- 周报、日记、邮件、论坛都能通过统一 Agent Runtime 运行；
- 用户刷新页面后仍能恢复未完成任务。

---

## Phase 6：前端 AI 原生体验增强

- [ ] 系统 Skill 页升级为 Skill 控制台。
- [ ] 增加 Memory 管理页。
- [ ] 增加 Agent 历史页。
- [ ] 增加任务进度时间线。
- [ ] 每个表单字段增加 AI 辅助按钮。
- [ ] Skill 调用结果以卡片形式展示。
- [ ] 危险操作显示确认卡与参数 diff。

验收：

- 用户能清楚看到 Agent 做了什么、为什么做、改了哪里、是否可撤销。

---

## 自动续跑规则

每次自动开发循环必须：

1. 读取 `.ai-native-dev-state.json`。
2. 读取本清单。
3. 选择第一个未完成、风险最小、可测试的任务。
4. 遵循 TDD：先测试、验证失败、再实现、验证通过。
5. 更新 `.ai-native-dev-state.json`。
6. 运行 `./scripts/run_tests.sh`。
7. 若上下文/Token 不足，必须先保存：
   - 当前完成项；
   - 当前失败项；
   - 下一步文件路径；
   - 推荐下一条命令；
   - git diff 摘要。
