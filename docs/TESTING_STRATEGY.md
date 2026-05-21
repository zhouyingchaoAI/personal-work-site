# personal-work-site 测试策略

## 测试目标

AI 原生改造后，系统核心风险集中在：

1. Skill 是否被正确注册和执行；
2. Agent 是否能稳定解析和调用 Skill；
3. Memory/历史是否正确持久化；
4. 写入/发邮件/发布等动作是否受确认和审计保护；
5. 旧页面功能是否不被破坏。

## 测试命令

统一入口：

```bash
./scripts/run_tests.sh
```

内部使用 Python 标准库 unittest，避免额外依赖：

```bash
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

## 测试分层

### 1. Unit Tests

覆盖：

- `backend.db`：SQLite 初始化、表结构、插入/查询；
- `backend.skill_runtime`：SkillDefinition、Registry、执行分发、参数校验；
- `backend.memory`：remember/search/list/delete；
- `backend.agent_runtime`：消息裁剪、Skill 选择、确认中断。

### 2. Regression Tests

覆盖当前已有行为：

- `skill_defs()` 返回 Skill 名称唯一；
- 每个 Skill 都有 name/module/title/description/parameters/safe；
- `parse_skill_call()` 能解析严格 JSON 和 Markdown 包裹 JSON；
- `execute_skill('utils.get_date')` 返回日期字段；
- 未知 Skill 抛出明确错误。

### 3. Integration Tests

覆盖业务链路：

- 周报：`weekly.compose → weekly.preview`；
- 日记：`diary.save → diary.get → diary.list`；
- 邮件：`mail.send` 在无 SMTP 时生成草稿；
- Skill 审计：每次执行都写入 `skill_invocations`。

### 4. Safety Tests

覆盖危险动作：

- `safe=False` 的 Skill 需要确认；
- `mail.send`、`weekly.send_confirmed`、`forum.create`、`forum.comment` 必须有审计记录；
- 跨用户读取数据应被阻止；
- 文件路径必须防止 `../` 逃逸。

### 5. Frontend Smoke Tests

暂不引入重型 E2E，先保证：

- 首页能加载；
- 登录接口返回正确结构；
- `/api/skills` 超级管理员可访问；
- `/api/skills/execute` 能执行安全 Skill。

后续如果引入 Playwright，再补浏览器级测试。

## 每轮开发验收标准

每个任务完成前必须：

1. 有测试覆盖；
2. 本地运行 `./scripts/run_tests.sh` 通过；
3. 更新 `.ai-native-dev-state.json`；
4. `git diff --stat` 可解释；
5. 写清楚下一步。

## TDD 规则

新增核心模块时必须：

1. 写失败测试；
2. 运行测试确认失败；
3. 写最小实现；
4. 运行测试确认通过；
5. 再做重构。

例外：文档、纯配置、测试脚本本身。
