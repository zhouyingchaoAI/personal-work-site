# 联指经营助手切换至数据中台存储（2026-09-30）

联指经营助手的全部业务数据读写已从本地 JSON 文件切换到 office-postgres
（迁移路线"导入→双写→切换"的切换步），本地模式代码保留仅作回滚开关。

## 切换范围

| 数据 | 切换后位置 |
|---|---|
| 7 类集合（units/people/relations/actions/links/staff/opportunities）| `crm.<collection>`（payload jsonb + pos 顺序列 + 生成列）|
| 员工目录 `_crm_staff_directory.json` | `crm.staff_directory` |
| 变更历史 `crm/history/*.jsonl` | `crm.live_history` |
| 经营分析快照（legacy + 归档目录）| `crm.live_blobs`（key `business_analysis:*`，json 类型保键序）|
| 导入完善任务 tasks.json | `crm.live_blobs`（key `import_tasks`）|

第二轮已补齐此前遗漏的 CRM 业务配置与操作审计：

| 数据 | 当前主存储 |
|---|---|
| 权限策略、人员区域归属、标准区域、质量规则、高德地图配置 | `crm.configuration`，按配置键保存 JSONB，版本校验防止覆盖并发修改 |
| 操作审计 | `crm.security_events`，顺序主键，时间/操作者/操作/状态/对象结构化列与操作者索引 |

已迁移 3 份现有配置和 10,096 条审计，逐条 payload 等价校验通过；尚未配置的项目
仍使用代码默认值，首次保存直接入库。数据中台的 CRM 全部运行数据项现均为数据库主存储。
账号目录属于平台共享服务，数据库连接参数属于启动配置，省市字典与报告模板属于代码静态资源；
这些不是本次 CRM 运行数据迁移项。Neo4j 图谱和 Redis 缓存仍是可重建的派生存储。

## 架构要点（backend/crm_store.py）

- 开关：`user_data/_datacenter/crm_db.json`（600 权限，`scripts/crm_db_setup.py`
  生成）`enabled=true` 走库；false/缺失回落文件模式（单元测试即此模式）。
- `configuration_enabled=true` 同时启用配置和审计切库；数据库错误直接报错，
  不退回读取旧权限文件。地图安全密钥在中台浏览时脱敏。
- 角色：`crm_app`，仅 crm schema 业务表的增删改查，15s 语句超时。
- 读：进程内整表缓存（按 owner 存 JSON 串，loads 出独立副本），用
  `crm.live_state` 全局版本号失效——替代原先每次快照近千次文件 stat；
  跨进程（celery）写入可见延迟 ≤0.8s，本进程写后立即可见。
- 写：整集合替换语义（与文件一致），差量 upsert/delete + pos 顺序维护 +
  历史行 + 版本自增，单事务。**顺序**（文件时代的 JSON 键序）由 pos 列与
  json 类型 blob 保留，切换前后接口响应逐字节一致。
- 大 blob 与经营分析版本列表带 updated_at/count 校验缓存。

## 联动调整

- 每日同步（datacenter_db.py）：`crm_live_mode` 下跳过 crm 业务表与员工目录
  （已是线上数据，不再从冻结文件镜像）；`audit.crm_events` 从 `crm.security_events`
  同步，避免继续把冻结的 audit.jsonl 当作最新审计。
- celery（图谱同步、每日衰减扫描）走同一存储层；compose 已给
  personal-work-celery 挂 `vendor/pgdeps`（**重建容器勿删**）。
- 数据接口 `/api/datacenter/data` 的 crm.* 数据集因直接读 live 表而变实时。
- 旧文件（`user_data/*/crm/`、`_crm_staff_directory.json` 等）已冻结为
  切换前快照，保留不动作回滚保险。

## 验收结果（2026-09-30）

- 功能等价：切换前后 14 个接口 × 2 账号 = 28 份响应**逐字节一致**。
- 存储后端 27 项 DB 测试通过（往返/顺序/历史/迁移/导出回滚/跨进程可见性）；
  文件模式全量 CRM 单测失败集合与切换前完全相同（21 项均为历史遗留）。
- 迁移核对：4586 条集合记录、12,790 条历史、2 个共享 JSON 全部行数一致。
- CRUD + 历史 + celery 图谱同步端到端通过；手动同步确认 live 表不被覆盖。
- 延迟（同环境中位数）：9 个热点接口合计 **2915ms → 1012ms（-65%）**；
  导入完善任务 1919→70ms（顺带修了每行重读 config.json 的热点），
  units -33%、people -27%、商机 -26%、总览 -19%。

## 回滚

1. `crm_db.json` 置 `enabled=false`，重启 personal-work-site 与 celery →
   立即回到文件模式（数据为冻结快照，丢失切换后的增量）。
2. 如需带增量回滚：容器内调 `crmdb_export_to_files(目标目录)` 导出全量，
   包含新增配置与审计；核对后覆盖 user_data 对应文件再关开关。

新增迁移脚本 `scripts/crm_configuration_migrate.py` 只在配置开关未开启时执行，
停止主服务与后台写入后运行。先备份原文件到 `_datacenter/crm-configuration-backups/`，
再事务导入并逐条核对，成功后原子切换配置；已切换时拒绝重导冻结文件。
