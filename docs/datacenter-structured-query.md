# 数据中台结构化查询层

2026-09-29。原始文件与完整 JSON 镜像继续保留，在业务镜像表增加类型化查询列和索引。此次优化数据中台取数接口；办公平台自身 JSON/SQLite 的业务读写未切换，也未实施双写。

## 范围与模型

11 个数据集：客户单位、联系人、关系、跟进动作、商机、历史回款、项目台账、员工目录、工单、论坛主题、技能调用。

- 保留原有主键（用户数据为 owner + id，回款为 owner + idx）、完整 payload、源同步时间。
- 常用关系、分类和筛选字段成为 text 列；金额使用 numeric，业务日期使用 date。查询列使用 PostgreSQL STORED 生成列，从 payload 自动生成，不需要第二套手动更新逻辑。
- 支持历史 `YYYY/M/D` 日期、ISO 日期/时间。非法金额和日期保留原文，类型列为 NULL，计入 invalid_typed_values；不静默改成 0 或随意指定日期。
- 67 个查询索引包含 owner + 关系/分类/日期/金额、稳定排序与分页索引，以及关键词 pg_trgm GIN 索引。金额与日期比较直接使用类型列；数据库完成筛选、COUNT、SUM、LIMIT/OFFSET，仅将当前页 payload 发给接口。
- 保留 JSONB 用于未知字段、嵌套内容和返回格式兼容。当前是结构化读模型，不是所有 JSON 都已经完成第三范式建模；关系字段可索引查询，但尚未对历史数据强制外键约束。后续业务写入切换时再逐模块明确子表、外键、写事务和冲突处理。

## 接口用法

保持原入口 `GET /api/datacenter/data` 和原有 API Key / 超级管理员鉴权。

- 省略 source 或 `source=live`：保持原有实时文件访问；旧调用方行为不变。
- `source=database`：使用 PostgreSQL 镜像；返回 `source=postgresql` 和 `synced_at`。页面在线测试对支持的数据集默认选择数据库镜像。
- 数据中台「数据接口」显示每个数据集的结构化表名、查询列、数据库类型、来源字段和支持的筛选参数。
- 数据库分支遇到连接错误或未完成结构化同步时返回 503，不悄悄退回文件读取。未知参数、非法日期/金额范围返回 400。

示例（owner 替换为真实用户名；请求头为已有 `X-Data-Api-Key`）：

```text
/api/datacenter/data?dataset=cashflow.history&owner=<用户名>&source=database&region=<区域>&date_from=2026-01-01&date_to=2026-12-31&min_amount=100&limit=20&offset=0&summary=1
```

每个数据集支持的精确字段见目录，不拼接任意 SQL、列名或排序表达式。现金回款的日期区间对应 received_date，金额区间对应 received_amount；商机对应 business_date/amount，台账对应 payment_due/contract_amount。金额单位保持原业务口径，不在查询层擅自换算。`summary=1` 返回筛选结果全体金额总计（不是当前页总计），用十进制字符串保留精度。CRM 同更新时间按 id 稳定排序，其他列表按主键排序，技能调用按 id 降序。

默认最多 500 条。结果逐条沿用既有 dc_mask 处理，不因整页超过 200 条而被预览截断规则截断；数据库分支不会返回连接凭据或开放原始 SQL。

## 同步、一致性与权限

- 仍是每日/手动镜像，并非实时数据。`synced_at` 来源于该表实际导入记录的同步时间，结构迁移本身不会伪造新的业务同步时间。
- 生成列随导入自动更新；同步后刷新统计信息并清理 GIN 待处理项。对外查询的业务表用事务内 DELETE + INSERT 替换，避免 TRUNCATE 使并发读者看到空表；失败回滚保留上一版。
- COUNT、当前页及汇总在同一个 REPEATABLE READ READ ONLY 事务中查询。不同业务表的镜像仍按表提交，不能当作全平台同一时点快照。
- 应用使用独立 `datacenter_reader`，仅 SELECT 11 张业务表和 meta.query_models；无账号密码表、设置原文、raw 原文仓库或 archive 文件块访问权，无写权限，默认只读事务。
- 连接池最多 4 个连接，查询超时 3 秒，参数绑定且字段白名单。OFFICE_QUERY_PASSWORD 在 .env 中，分别注入应用与入库进程；入库进程创建/更新只读角色，主应用不持有数据库写入账号。
- SQLite 只读挂载支持：先复制稳定的 DB/WAL/journal 文件组到私有临时目录，再通过 SQLite backup API 生成完整性检查通过的副本。读取前后检查 inode、大小、mtime、ctime，变化则重试；不会用 immutable 模式忽略 WAL，也不在原目录创建 SHM。原始记录镜像和专用智能体表共享这一份 SQLite 快照。

## 验收证据

- 14 个结构化查询测试：输入白名单、owner 隔离、百分号/下划线字面关键词、分页、金额汇总、历史斜杠日期、异常值保留、真实索引执行计划、并发读旧数据/失败回滚、接口 source 兼容与错误处理。另补两个 WAL 读取回归测试。
- 隔离 HTTP 服务的真实 PostgreSQL 请求、在线测试界面、401/403/400 验证通过；线上 API Key 实测数据库与文件首屏结果一致，临时验收密钥随后吊销并验证不能再用。
- 应用只读角色实测：允许业务 SELECT，即使将事务只读默认值关掉也不能 DELETE；不能访问账号密钥表和原始归档。
- 22,000 条独立测试数据中实际执行计划使用区域复合索引和关键词 GIN 索引，未强制关闭顺序扫描。小表或低选择性的查询可由 PostgreSQL 正常选择顺序扫描。
- 相同真实回款区域过滤、20 条分页、预热后 20 次中位数：JSON 全文件读取约 35.7 ms，复用连接的 PostgreSQL 查询约 2.6 ms。另在线上本机 HTTP 路径、回款分页 20 条、预热后 20 次中位数：live 38.527 ms，database 8.168 ms。前者不含网络/首次连接，后者含 HTTP、鉴权、脱敏与审计。不是所有业务页面或冷启动请求的性能保证。

相关文件：backend/datacenter_sql.py、backend/datacenter_db.py、backend/data_center_api.py、tests/unit/test_datacenter_sql.py、scripts/verify_datacenter_sql.py、scripts/verify_datacenter_sql_role.py、scripts/verify_datacenter_sql_ui.py。
