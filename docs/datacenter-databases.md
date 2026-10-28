# 数据中台「数据库直连」（2026-09-30）

数据中台新增「数据库」页签：超级管理员可只读浏览平台内**全部 15 个数据库实例**，
包括各独立服务（FastGPT / Dify / Foundry / RAGFlow）自己的库。

## 实例清单

| 系统 | 实例 | 类型 | 接入方式 |
|---|---|---|---|
| 办公平台 | office-postgres（统一业务库） | PostgreSQL 15 | 内网 `office-postgres:5432`，只读角色 `datacenter_reader` |
| 办公平台 | app.db | SQLite | 本地文件，`mode=ro` |
| 办公平台 | crm-redis / crm-neo4j / qdrant | Redis / Neo4j / Qdrant | 内网直连 |
| FastGPT | fastgpt-mongo（主库）、fastgpt-pg（向量）、fastgpt-aiproxy-pg、fastgpt-redis | MongoDB / PG / Redis | 内网直连 |
| Dify | docker-db-1、docker-redis-1 | PG / Redis | `docker_default` 网络 |
| Foundry | foundry-platform-postgres-1 | PG | `foundry-platform_default` 网络 |
| RAGFlow | ragflow-mysql、ragflow-redis、ragflow-es-01 | MySQL / Redis / ES | 宿主机映射端口（5455/16379/1200） |

## 功能

- **实例总览**：状态探测（up/down/认证失败）、版本、库大小/键数，按系统分组。
- **对象浏览**：SQL 库列 schema.表 + 行数估算 + 大小；Mongo 列集合；Redis 按模式扫描键；
  ES 列索引；Qdrant 列集合；Neo4j 列节点标签与关系类型。
- **数据浏览**：分页查看行/文档/键值/向量点 payload/图节点，Mongo 支持 JSON 过滤。
- **只读 SQL 控制台**：仅 PostgreSQL / MySQL / SQLite；单条语句，仅
  SELECT/WITH/SHOW/EXPLAIN/DESCRIBE，最多返回 200 行。

## 安全设计

- 全部接口 `require_superadmin`；业务系统 API Key 不能访问这些接口。
- 只读强制（多层）：语句白名单 + PG `BEGIN READ ONLY`（office 另有 `datacenter_reader`
  只读角色 + `pg_read_all_data`，INHERIT 生效）+ MySQL `READ ONLY` 事务 + SQLite `mode=ro`；
  Redis/ES/Qdrant/Neo4j 只发白名单只读命令。
- 行数据经 `dc_mask` 脱敏（password/token/key 等字段）；每次浏览与查询写
  `_datacenter/access_log.jsonl`。
- **凭据不进代码仓库**：`user_data/_datacenter/db_connections.json`（600 权限）由宿主机脚本
  `scripts/datacenter_db_connections_setup.py` 从各容器运行环境生成；凭据轮换后重跑即可。

## 类别分色（2026-09-30）

实例按数据库类别统一配色（`DataCenterView/dbCategories.ts`，两个页签共用）：
结构化（蓝 #3a7bd5）、文档（绿 #22a06b）、向量（紫 #8a6bd1，含 pgvector 的
fastgpt-pg）、图（橙 #e08a00）、缓存·键值（粉 #d4568a）、全文检索（青 #0aa2a2）、
对象存储（灰 #64748b）。类别写在注册文件每个实例的 `category` 字段（setup 脚本
按 kind 推导 + CATEGORY_OVERRIDES 覆盖）。同时新增 fastgpt-minio / ragflow-minio
两个对象存储实例（kind=minio，仅 /minio/health/live 健康探测，不提供内容浏览），
实例总数 15 → 17，并接入数据流向拓扑（工作流中心 / 知识库）。

## 数据流向页签（2026-09-30 新增）

「数据流向」页签实时可视化 数据库 ↔ 助手 拓扑（`backend/data_center_dataflow.py`，
`GET /api/datacenter/databases/flow`，前端 `DataFlowTab.vue`，5 秒自动刷新）：

- **连接归属**：各库的客户端地址（pg_stat_activity / MySQL processlist / Redis
  CLIENT LIST）经注册文件 `client_map`（IP→容器→助手，setup 脚本生成，容器重启
  IP 变化后重跑刷新）反查出"哪个助手正在连"。
- **交互速率**：活动计数器（PG xact/tup、MySQL Questions/Innodb rows、Redis
  commands、Mongo opcounters、ES search/index、Qdrant 点数、Neo4j 节点+关系、
  SQLite mtime）两次采样差分成每秒速率；office 只读角色已授 `pg_read_all_stats`。
- **异常**：不可达/采样失败（critical）、死锁增长、Redis 拒绝连接、MySQL
  连接失败、事务回滚异常、ES red、同步/备份失败；写入
  `_datacenter/db_alerts.jsonl`（同实例同类型 10 分钟去重），页面显示当前 + 最近 30 条。
- MySQL 健康探测使用完整认证查询，不使用裸 TCP 握手后断开。
  2026-09-30 复现确认旧的端口探测每次会增加一次 `Aborted_connects`，导致中台自身制造告警；
  已同时修复数据库清单、数据流向、存储与服务三处探测。真实新增失败仍正常告警。
- 页面把当前异常与历史告警分开展示。历史日志保留追溯，默认折叠，不表示当前故障。
- **选中交互**（2026-09-30 第二版）：点击左侧助手 → 高亮其连线与关联库（其余
  淡化）；选中后点击关联库 → 自动滚动展示"该助手在此库的相关数据表"
  （`GET /api/datacenter/databases/flow/tables?assistant=&instance=`，复用
  dcdb_objects 按 `DCFLOW_EDGE_TABLES` 归属规则过滤：office-postgres 内
  crm.* 归联指经营助手、其余 schema 归数据中台；整库专属的系统不过滤）。

## 运维注意

- 「存储对应」页签按助手、具体数据类别列出实际主存储、路径/表名与统一库副本。
  `GET /api/datacenter/storage-map` 仅超级管理员可用，CRM 分类读取当前业务开关。
  同步证据来自 `db_sync.json` 最近一次记录；空表明确显示 0 行，不计作已有业务记录。
  SQLite 按数据库归类；对象存储单列；OpenClaw、外部邮箱未经核验，不标成已迁移。
  JSON 镜像、文件索引和 `archive.*` 文件本体归档分别说明用途；存在副本不改变主存储归属。
  映射由 `backend/data_center_storage.py` 维护，读写位置调整时需同步更新；
  该清单不代替逐文件实时完整性校验。

- 数据流向目录以 `ASSISTANT_IDS` 为完整性基准：当前 17 个助手入口，另列智能体、
  模型网关、Dify、Foundry、工单 5 个支撑系统。新助手未配置映射时仍显示为待核实。
- 写作、周报、出差报告、日记、论坛、资讯、邮件、会议、项目、台账、资金测算、
  报销保留实际文件/外部服务主存储说明，统一库关联标为定时镜像或索引。
  镜像边使用紫色点线，不使用数据库总流量推断助手正在交互。
- 台账、资金、论坛、工单分别过滤到 `ledger.*`、`cashflow.*`、
  `collab.forum_topics`、`collab.tickets`。其余文件助手显示 `raw.documents`、
  `files.catalog` 共享表，不显示全表行数/容量作为单助手统计；来源见清单说明。
- 龙虾基地的 OpenClaw SQLite、工作目录和对象存储尚未纳入中台数据库注册，
  保留助手节点并明确标记未接入监测。目录完整不代表所有外部存储均已接入。
- 数据库连接来源识别依赖容器标签；共享办公进程的连接无法确定到具体助手，
  不作为该助手活动证据。实例层指标仍展示数据库整体状态。

- 主容器需在 `docker_default`、`foundry-platform_default`、`personal-work-site_default`
  网络（已用 `docker network connect` 接入）。**容器重建后需重新执行**：
  ```
  docker network connect docker_default personal-work-site
  docker network connect foundry-platform_default personal-work-site
  docker network connect personal-work-site_default personal-work-site
  ```
- 驱动为纯内置/vendor 依赖：pg8000、PyMySQL、pymongo（vendor/pgdeps），Redis 用内置
  RESP 客户端，ES/Qdrant/Neo4j 走 HTTP。
- 代码：`backend/data_center_databases.py`（server.py 路由
  `/api/datacenter/databases[/objects|/rows|/query]`），前端
  `DataCenterView/DatabasesTab.vue`；单测 `tests/unit/test_datacenter_databases.py`。
