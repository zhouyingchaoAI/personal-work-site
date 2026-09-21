# 助手权限管理

入口：设置 → 用户管理 → 助手使用权限。超级管理员勾选或取消助手后点击保存。

- 普通成员、管理员：未单独配置时，默认开放全部助手，客户经营助手（crm）和经营管理台账（ledger，项目经理经营管理场景）除外。
- 项目助手（project）是独立的项目协作模块，默认开放。
- 超级管理员始终可使用全部助手；只有超级管理员可新增、修改、删除账号及修改助手授权。最后一位超级管理员不能降级。
- 旧账号无需迁移，新账号自动应用默认规则。权限存储于 config.json 用户条目的 assistant_permissions 对象，键为助手 ID，值为布尔值；缺失键采用默认值。
- 撤销使用权限不会删除已有业务数据。后端每次请求读取当前授权；菜单在页面导航、重新加载会话时更新。
- 菜单、助手中心、路由、助手 API 和 Skill 执行入口接入权限检查。合同 API 随经营管理台账权限控制。

验证：`python3 -m unittest tests.unit.test_assistant_permissions tests.unit.test_crm tests.unit.test_project_assistant`；前端 `npm run build`。
