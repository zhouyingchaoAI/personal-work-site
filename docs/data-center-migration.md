# 从数据库迁移办公平台文件

2026-09-29。此流程适用于办公平台代码目录及 user_data 的完整数据副本。2026-09-30 起各助手业务数据已经统一存储层切换到 office-postgres 的 app.* 表（见 office-store-cutover.md），user_data 下原目录是切换前快照；pg_dump 排除 app.cache_documents / app.cache_blobs（邮件可重建缓存）的数据。

2026-09-30 起，外部系统也可通过 `scripts/datacenter_migration_bundle.py` 汇集为同一个迁移目录：办公库、FastGPT、Dify、Foundry、RAGFlow 的原生数据库导出，以及三套对象存储卷快照会放进 `/srv/office-backups/migrations/platform-<时间>/`，并附 `manifest.json` 和 `SHA256SUMS`。它们仍保持各自的原生格式，避免把不同产品的表结构强行混入办公库。

```bash
python3 scripts/datacenter_migration_bundle.py --dry-run
python3 scripts/datacenter_migration_bundle.py
cd /srv/office-backups/migrations/platform-<时间> && sha256sum -c SHA256SUMS
```

该工具不自动停业务。日常包可在线生成；正式切换前暂停各系统写入后再生成一份最终包，保证对象存储卷与数据库导出处于同一迁移窗口。Redis、Qdrant、Neo4j 在清单中明确列为可重建/需专用导出，绝不会被误报为已完整迁移。

## 已纳入

整个项目目录的普通文件、空目录及链接元数据，包括 user_data 所有文件本体（附件、图片、邮件缓存、SQLite、隐藏密钥等）、系统配置及历史配置、`.env`、代码旁模板/数字人资源/业务文档，并附带代码和依赖清单。用户目录不会因文件扩展名或缓存级别被排除。

仅排除开发可重建目录：`.git`、`.worktrees`、`node_modules`、虚拟环境、Python/pytest 缓存、前端 dist/dist.bak；以及运行时 PID 与 SQLite journal/WAL/SHM（SQLite 本体用 backup API 生成一致性副本）。源码目录下已有的外部服务物理数据文件只算文件副本，不代表该外部服务的应用级一致性备份。

文件保存在 `archive.entries`，内容为 `archive.chunks` 中按 SHA-256 去重的 1 MiB 块。`archive.runs` 只将完整成功版本提供给恢复工具；失败版本不会替代之前成功版本。每个文件读取前后检测变化，SQLite 单独一致性快照；在线运行时不同文件之间不是全系统同一时点快照。正式停机迁移需暂停业务写入，再手动执行最后一轮同步并等待对应数据库备份完成。

## 备份包

每次成功同步完成后，`datacenter-pg-backup` 自动运行 `pg_dump -Fc --no-owner --no-acl`。产物位于 `/srv/office-backups/postgres/`：

- `office-pg-<时间>-<版本>.dump`：数据库原生备份，包含关系表、原始文档及文件本体块。
- 同名 `.dump.sha256`：备份校验值。
- 同名 `.dump.restore-tools.tar.gz` 及校验值：恢复脚本、纯 Python PostgreSQL 驱动和本说明，不包含业务密钥。

备份目录权限 0700，备份文件 0600，最近 14 份成功导出自动保留。备份包含完整敏感配置，请通过受控传输搬迁，勿放入公开仓库或普通附件下载。页面显示备份成功表示 pg_dump 成功、归档目录可读取；不等于每一份都已做真实恢复演练。本次上线另外完成独立数据库与全量文件恢复验证。

## 新环境恢复步骤

1. 复制一个已完成的 dump、校验文件与对应恢复工具包到新主机的受限目录。运行 `sha256sum -c <文件>.sha256` 校验两个包。
2. 新环境准备 PostgreSQL 15 或兼容的新版本、一个空数据库与受控账号，设置 `PGHOST`、`PGPORT`、`PGUSER`、`PGDATABASE`、`PGPASSWORD`。不要将密码直接写入命令行或共享日志。
3. 导入数据库：`pg_restore --exit-on-error --single-transaction --no-owner --no-acl --dbname="$PGDATABASE" <文件>.dump`。必须使用空数据库，不能对现网库执行覆盖恢复。
4. 解压恢复工具包，在解压目录中设置 `OFFICE_PG_HOST`、`OFFICE_PG_PORT`、`OFFICE_PG_USER`、`OFFICE_PG_DB`、`OFFICE_PG_PASSWORD` 指向刚恢复的数据库。
5. 执行 `python3 scripts/datacenter_restore.py /secure/new-platform`。目标目录必须不存在；默认选择最新完整快照，也可用 `--run-id` 指定版本。程序逐块、逐文件校验后恢复到 `/secure/new-platform/project/`，保留权限和修改时间。绝对或越界符号链接拒绝恢复，部分失败会生成 `RESTORE_FAILED`，禁止使用该目录上线。
6. 核对恢复目录中的 config.json 账号数量、user_data/app.db 的 `PRAGMA integrity_check`，以及关键附件。配置中存在旧主机地址、外部服务连接及密钥，按新环境调整，勿直接复用未核对的配置。
7. 从恢复代码和锁文件重建前端/依赖。按实际环境准备 Compose 的宿主机路径、外部 Docker 网络，以及独立服务数据库。先在隔离环境启动验收，通过后再安排正式切换。

还原工具只写新目录，数据库恢复只操作新建空库。数据中台网页保持脱敏浏览，不开放包含密钥的整包下载。

## 调度与容量

每日 02:30 及手动同步均先完成数据镜像/文件快照，再触发对应 PostgreSQL 备份。重复内容复用已有块，文件版本清单保留历史；目前不会自动清理 archive 中历史内容块，需结合容量增长制定保留策略。数据库 dump 已自动保留 14 份。当前备份仍在本机系统盘，异机/异地副本尚未配置。

## 结构化查询层补充

数据中台目前还包含 STORED 类型列、pg_trgm 索引和 meta.dc_number/meta.dc_date 转换函数，均随 PostgreSQL 原生 dump 迁移。恢复时需要 PostgreSQL 15 镜像自带的 pg_trgm 扩展。应用只读连接的 OFFICE_QUERY_PASSWORD 位于 .env；pg_dump 不导出集群角色，恢复后启动 datacenter-backup 会按环境配置重建/授权 datacenter_reader。它只读业务查询表，不得访问账号密钥或完整文件归档。先完成入库进程初始化，再验证 `source=database` 查询。
