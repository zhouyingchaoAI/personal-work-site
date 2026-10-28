# 数据中台（统一数据平台）设计

2026-09-29 第一批上线。目标：为分散在 JSON、SQLite、Docker 卷和各产品数据库中的平台数据提供一个统一的管理入口，**先不影响现有业务，后续按模块逐步切换**。

## 原则

1. 只增不改：第一批不改动任何业务模块的读写路径，业务数据仍在原位置。
2. 数据中台页面只读：不提供修改、删除业务数据的操作；恢复在服务器上执行并先入沙箱。
3. 备份先行：统一数据库先就位，但业务切换前，文件级备份已经每天在跑。
4. 密钥不进仓库：数据库密码在同目录 `.env`（已加入 `.gitignore`）。

## 组成

| 部分 | 位置 | 说明 |
|---|---|---|
| 统一业务数据库 | 容器 `office-postgres`（postgres:15-alpine，固定版本） | 核心业务数据（A 级）的迁移目标。独立命名卷 `office-postgres-data`，仅 Docker 内网可达，不开放宿主端口。第一批只启动、不接业务。 |
| 备份服务 | 容器 `datacenter-backup`（复用主镜像，入口 `scripts/datacenter_backup.py`） | 每日 02:30 自动备份 + 手动触发；业务代码只读挂载；备份写入系统盘 `/srv/office-backups`（与业务数据盘 /home 不同磁盘）；保留最近 14 份；每次备份后重读归档校验条目数并记 sha256。 |
| 扫描与状态库 | `backend/datacenter_lib.py` | 纯标准库，可被 runtime 与备份进程共同导入：数据分级（A 核心 / B 用户文件 / C 可重建 / D 缓存）、目录扫描、原子写 JSON。 |
| 业务模块 | `backend/data_center.py`（注册于 runtime MODULES） | `/api/datacenter/*` 四个接口，均要求超级管理员。 |
| 前端助手 | 菜单 `datacenter`「数据中台」，`views/DataCenterView/` | 三个页签：数据资产总览 / 备份与恢复 / 存储与服务。roles 仅 superadmin，且加入 `ASSISTANT_DEFAULT_DENIED`。 |

## 双方约定（backend ↔ 备份容器）

通过 `user_data/_datacenter/` 交换，全部原子写：

- `scan.json`：资产扫描快照 + 逐日容量历史（120 天）。双方都可刷新，后写覆盖。
- `backups.json`：最近 60 次备份记录（结果、大小、条目数、sha256、错误）。仅备份进程写。
- `backup_status.json`：心跳（30 秒）、下次计划、备份盘余量。仅备份进程写。
- `backup.trigger`：前端“立即备份”写入，备份进程消费后删除。

## 备份内容与排除

- 包含：`user_data` 中 A/B 级数据、`app.db`（sqlite3 一致性快照）、`config.json`、部署文件快照。
- 排除：`mail_cache`、公众号缓存、`_news`、附件链接缓存（D 级，可重拉）；`.env`（密钥不进未加密归档）。
- 磁盘保护：备份盘剩余 < 5 GB 时跳过并记失败原因。

## API

| 接口 | 方法 | 说明 |
|---|---|---|
| `/api/datacenter/overview` | GET | 扫描快照、分级汇总、磁盘用量、数据服务状态、迁移路线 |
| `/api/datacenter/backups` | GET | 备份记录、三份副本状态、服务心跳 |
| `/api/datacenter/backup/run` | POST | 写触发文件，备份服务 1 分钟内执行 |
| `/api/datacenter/refresh` | POST | 强制重新扫描资产 |

## 迁移路线（后续批次）

1. 账号与配置迁入 office-postgres（auth/settings，邮箱密码统一加密）。
2. 业务模块按“导入 → 双写 → 切换 → 归档”逐个迁移：联指经营助手 → 资金测算 → 项目管理台账 → 工单论坛 → 智能体记录。
3. 用户文件迁对象存储；第二、三份备份副本（内网另一台机器、异地加密）。
4. 第二批页面：数据浏览（脱敏）、访问审计、数据质量；第三批：生命周期、密钥管理。

## 已知边界

- 备份目前只有一份副本（系统盘），仍在同一台虚拟机上；异机/异地副本待确定存放位置。
- FastGPT/RAGFlow 的数据库尚未纳入备份（页面服务状态中已可见），计划用各自导出工具接入。
- 恢复演练需人工执行：解包到临时目录核对后再替换；每月一次。

## 数据访问接口（第三批，2026-09-29）

面向业务系统的统一取数层：`GET /api/datacenter/data?dataset=<key>&…`，注册表即文档（`backend/data_center_api.py` 的 DAPI_DATASETS，14 个数据集：crm.units/people/relations/actions/opportunities、cashflow.history/insights、ledger.items、org.staff、tickets.list、forum.topics、agent.skill_invocations、meta.assets/backups）。

- 鉴权：业务系统请求头 `X-Data-Api-Key`（密钥仅存 SHA-256 哈希，明文只在创建时显示一次，可吊销、记录调用次数与最近使用）；平台内超级管理员会话可直接调用（页面在线测试）。server.py 两处放行：check_assistant_permission 与 do_GET 的 `/api/` 通配登录检查，均仅对 `/api/datacenter/data` + 带 Key 的请求生效，密钥有效性在路由内校验。
- 约束：只读；limit ≤ 500；敏感字段沿用 dc_mask 脱敏；每次调用写 access_log（action=api）。keyword 参数须 URL 编码。
- 前端：数据中台第四个页签「数据接口」（ApiTab.vue）：分组目录、参数/字段表、curl 示例、在线测试（显示服务端与端到端耗时）、API 密钥管理。
- 定位：智能办公平台自身业务逻辑未切换到本接口；数据迁入 office-postgres 后只换本层实现，外部调用方不感知。

## 全量镜像入库（2026-09-29，接续完成）

保持原 JSON/SQLite 为业务唯一数据源，不改登录、权限判断、业务读写或现有数据接口的取数路径。入库进程仅运行在 `datacenter-backup`，主服务不增加 PostgreSQL 依赖。新增 `backend/datacenter_db.py`，驱动为已放入 `vendor/pgdeps` 的 pg8000。

### 实际覆盖范围

- `auth`：完整账号记录、角色、用户权限覆盖项；`settings`：邮箱配置与 config.json 其余全部配置。权限默认规则仍由现有业务代码解释，尚未改成数据库驱动的权限系统。
- `crm/cashflow/ledger/collab/agentic/audit`：业务明细投影与审计记录；自然键和完整 JSONB payload 并存。智能体 ID 全部为 text，兼容 `evt_…` 等 ID，已有 bigint 列幂等转为 text。
- `raw.documents`：user_data 下所有常规 JSON/JSONL 文件（包含缓存、未知模块、日记、会议记录、数据中台元数据等），以及原始 config.json；保留完整原始字节、SHA-256，并提供可解析文档的 JSONB。无法解析或含 JSONB 不支持字符的文档保留原文并计数提示，不静默丢弃。符号链接不沿用。
- `raw.sqlite_schema/raw.sqlite_rows`：app.db 全部 12 张表的定义和行数据，包含之前遗漏的 workflow_instances 及 FTS 辅助表；单个 SQLite 读事务保证该镜像的读取一致性。BLOB 编码为 `{"__bytes_hex__":"..."}`；恢复工具需按源表定义解码，FTS 可重建。
- `files.catalog`：文件路径、所属用户/模块、级别、大小、修改时间、SHA-256。PDF/Excel/图片等附件本体仍在原目录及既有文件备份中，尚未迁入对象存储或数据库 BLOB。
- `meta.sync_runs`：同步历史。当前共 11 个 schema，28 张数据表及 1 张运行历史表。行数统计包括原文与业务投影的重复表达，不等于独立业务对象数量。

**范围边界：FastGPT、RAGFlow、Neo4j、Redis、对象存储等独立服务的数据仍由各自存储负责，服务在线不等于已导入 office-postgres。本次完成办公平台 config.json + user_data 的镜像层，不能称所有外围服务都已统一迁库。**

### 同步、安全及故障行为

- 启动时、每日 02:30 任务以及 `POST /api/datacenter/sync/run` 手动触发。手动按钮发出请求，守护进程随后执行；不是实时双写。
- PostgreSQL advisory lock 防止两个同步进程并行覆盖。每张表单事务替换，失败保留该表旧数据；之前已提交的表不会整体回退。因此这不是跨文件、跨表、跨服务的同一时点快照。
- 每张已同步表执行实际 `SELECT count(*)`，与本次读到的源记录数对比；页面标明“行数核验”，不把它描述成完整内容一致性证明。完整原文校验由验收脚本执行。
- 源 JSON 解析失败不再当空列表清空业务镜像。连接失败也写失败状态；页面及守护进程的错误摘要不输出密码或源字段值。
- 容器实际挂载 `user_data:ro`，仅 `_datacenter` 子目录可写，备份目录另行可写；源码、配置、驱动均只读。主业务容器未重启。
- 数据库含完整账号和敏感配置，只供受控后端连接，不为普通用户/API Key 开放直连或原始 SQL。原始数据浏览与取数接口仍沿用脱敏和权限检查。
- 现有每日文件备份继续运行，保存原业务源；office-postgres 当前是可重建镜像，**尚未加入独立 pg_dump / PITR 备份**。切换唯一数据源前，必须完成数据库原生备份、恢复演练及异机副本。

### 界面与验收

数据中台 → 存储与服务：同步时间、结果、耗时、各表实际行数/源记录数、“立即同步入库”，以及附件/外围服务/同步时效的边界提示。页面构建通过。新增同步回归测试 6 项，加现有数据中台测试共 23 项，均在临时源目录中通过。

验收脚本：

```sh
# 读取真实 PostgreSQL，校验全部表行数和原文字节摘要；回滚/重复执行测试仅使用连接私有 TEMP 表
# 活跃邮件缓存可能在快照后改变，单独报告；非缓存源变化要求重新同步后再验收。
docker exec -w /app datacenter-backup python3 scripts/verify_datacenter_mirror.py

# 本地临时服务与临时数据目录，验证按钮、同步展示及未登录/普通用户/超级管理员权限
python3 scripts/verify_datacenter_ui.py <截图目录>
```

第一轮验收：28 张数据表，43,855 行；3,306 份原始文档，12 张 SQLite 源表共 1,827 行，14,697 个文件索引。165 个账号、186 条权限覆盖项、14 份邮箱配置、69 项平台配置。原文解析异常 0 项。真实 PostgreSQL 原文摘要校验、文本 ID、重复执行及失败回滚通过；接口权限为 401/403/200。总量随正常业务更新而变化。


## 完整文件本体入库（2026-09-29，本节取代上文“附件只有索引、无原生备份”的旧边界）

用户要求所有代码侧数据与用户目录数据均可随数据库搬迁。新增 `backend/datacenter_archive.py`，扫描整个项目目录，用户文件不按类型/缓存级别排除；包括附件、数字人资源、业务模板、隐藏密钥和部署配置。只排除可重建开发依赖/构建产物及数据库运行侧文件。文件本体分块存入 PostgreSQL，完整快照发布后才允许还原，SQLite 使用一致性副本。已有关系表镜像与业务访问路径保持不变。

新增 `datacenter-pg-backup` 独立容器：每次成功入库后原生 pg_dump，校验、配套恢复工具包、保留 14 份。完整的范围、限制、备份位置和新环境恢复步骤见 [data-center-migration.md](data-center-migration.md)。同步结果新增 `file_archive`，前端展示完整文件数量、体积、SQLite 快照数量与原生备份状态。新增与变更容器不重启主业务容器。

测试包括：路径越界、用户数据不被开发目录名误排除、独立 PostgreSQL 中完整二进制/目录/权限/SQLite 还原、内容去重、拒绝覆盖已有目录、失败快照不发布及内容损坏拒绝恢复。部署验收从真实 dump 恢复到另一个临时数据库，再只依赖该数据库还原全量文件并校验，临时文件与测试数据库验收后清理。

## 结构化查询优化（2026-09-29）

11 类高频业务数据增加类型化 STORED 列、67 个查询索引，数据中台接口显式 `source=database` 执行数据库筛选、分页和汇总；默认 source=live 保持旧访问行为。应用通过独立 SELECT-only 账号访问，镜像时间与异常值计数随响应返回。同步对查询表使用 MVCC 安全的事务替换。详细范围、用法、一致性边界和性能实测见 [datacenter-structured-query.md](datacenter-structured-query.md)。

本批为加载接口与只读连接配置重载了主应用；旧进程内登录会话可能需要重新登录。业务模块自身读写代码未切换。
