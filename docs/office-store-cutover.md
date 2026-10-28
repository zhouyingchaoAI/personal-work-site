# 办公平台本地文件全部切换为数据库模式（2026-09-30）

联指经营助手之外的 15 个助手与平台资料原本直接读写 `user_data` 下的 JSON / 二进制文件。本次通过统一存储层把它们全部切换到 office-postgres，原文件保留为切换前快照，不再参与业务读写。

## 统一存储层

- 代码：`backend/office_store.py`（runtime MODULES 中紧随 db.py 加载）。调用方仍传原来的文件路径，路径相对 `user_data` 的 posix 形式即数据库里的键。
- 表：`app.documents`（JSON，`json` 列保键序）、`app.blobs`（bytea + size + sha256 + content_type）、`app.events`（追加型日志，seq 自增）、`app.cache_documents` / `app.cache_blobs`（可重建缓存，仅邮件 IMAP 快照与附件分片；`scripts/datacenter_pg_backup.sh` 的 pg_dump 用 `--exclude-table-data` 排除其数据）。主键 (module, key)。
- 角色：`office_app`（仅 app schema 读写），配置与开关 `user_data/_datacenter/office_db.json`（600 权限；`modules.<模块>=true` 才走数据库；运行中的服务按文件 mtime 即时感知）。`scripts/office_db_setup.py` 建表、建角色、写配置；`--test-db office_test` 另建一次性测试库。
- 接口：`office_doc_read/write/delete/exists/list`、`office_blob_write/read/exists/stat/delete/list/delete_tree`、`office_blob_local`（临时落盘给只认路径的库）、`office_event_append/recent/count`、`office_store_import_tree/verify_tree/export_tree/counts`。`cache=True` 走 cache 表。`user_data` 之外的旧共享目录（代码旁 周报/、generated/、drafts/）始终按文件处理。
- 模块 id：与助手 id 一致，周报与出差报告共用 `reports`（`office_store_module()` 映射），`OFFICE_STORE_LAYOUT` 登记各模块的原文件布局，迁移脚本与数据中台“存储对应”共用。

## 各助手切换情况

| 模块 | 键前缀（原文件） | 说明 |
|---|---|---|
| ledger | `<用户>/operating_ledger.json`、`contract_documents/` | 台账记录、合同 record.json、原件与生成单据 |
| cashflow | `<用户>/cashflow_*.json`、`cashflow_exports/` | 导出改为返回 (文件名, 字节) 并入库；`_cashflow/` 模板为部署资源不入库 |
| project | `projects/projects.json`、`projects/<id>/files/` | 删除项目按键前缀清理附件 |
| diary | `<用户>/diary/*.json` | |
| workorder | `_tickets/tickets.json` | 历史论坛拆分逻辑同样走存储层 |
| forum | `_forum/topics.json`、`_forum/attachments/` | `forum_attachment_content()` 供路由取附件 |
| meeting | `<用户>/meetings/*.json` | |
| writing | `<用户>/writing/{uploads,history,templates,exports}` | 导出全部在内存生成后入库 |
| news | `_news/`、`<用户>/news/` | 收藏统计重建按数据库 owner 列表 |
| reports | `<用户>/reports/`、`generated/`、`drafts/`、`templates/` | 周报/出差报告：模板、生成、预览图、邮件草稿 .eml、项目关联报告；预览/正文解析经 `office_blob_local` |
| reimbursement | `<用户>/reimbursement/{searches,cache,ofd_preview,output}` | 发票解析、OFD 渲染、合并需要真实路径：`_cache_path_for_key` 把库内文件落到 `/tmp/office-reimbursement/<用户>/` 工作副本，数据库为准 |
| mailassistant | `<用户>/mail_cache/sent.json`、`_mcp_mail_attachment_links/`（业务表）；其余 mail_cache（cache 表） | `get_mail_part_content()` 供路由与技能取附件 |
| knowledge | `knowledge/*.json` | RAGFlow 账号/会话映射与内置知识库文档记录 |
| datacenter | `_datacenter/access_log.jsonl`、`db_alerts.jsonl` → `app.events` | 库不可用时留痕/告警落回文件；`_datacenter/*.json`（状态、连接注册、开关）必须留在文件 |
| platform | `<用户>/profile/avatar.png`、`nav_prefs.json` | config.json、登录会话 SQLite 不在范围 |

## 迁移流程

`python3 scripts/office_store_migrate.py <模块…> --switch`（宿主机运行，直连容器 IP）：按 `OFFICE_STORE_LAYOUT` 逐文件导入（增量：sha256 / 内容相同则跳过）→ 逐项核对 → 翻开关 → 切换窗口补写并再核对。业务文件必须逐项一致；命中 cache 谓词的缓存文件在校验窗口内被在线服务刷新时重新导入一次不阻断。每次迁移在 `app.events`（module=datacenter, stream=store_migration）留记录。回退：把开关改回 false 即回到文件模式；`office_store_export_tree()` 可把库内内容还原成目录。

## 数据中台联动

- `backend/datacenter_db.py` 的镜像同步：已切库模块从 `app.documents` 取数据构建 `cashflow.*`、`ledger.items`、`collab.*` 等镜像表，`raw.documents` / `files.catalog` 排除切换前快照目录并补上库内在线记录；`audit.datacenter_access` 从 `app.events` 取。备份容器改动后需 `docker restart datacenter-backup`。
- `data_center_storage.py` 存储对应、`data_center_dataflow.py` 拓扑与“相关数据表”按开关实时显示；`DATACENTER_MIGRATION` 第 4、5 步已标 done。

## 测试

`tests/unit/officedb_testing.py` 的 `db_variant(TestCase)` 让同一测试类在数据库模式再跑一遍（需要 `OFFICE_STORE_TEST_CONFIG` 指向一次性测试库，`scripts/office_db_setup.py --test-db office_test` 生成 `/tmp/office_store_test_office_test.json`）。各助手测试均已加 DbMode 变体；新增 test_office_store、test_ledger、test_forum_attachments、test_meeting_storage、test_reimbursement_storage、test_mail_storage、test_platform_storage、test_datacenter_events、test_knowledge_storage。
