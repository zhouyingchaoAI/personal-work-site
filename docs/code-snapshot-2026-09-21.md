# 2026-09-21 代码快照

本次保存当前应用源码、测试和设计文档，包括客户经营助手及关联办公模块。属于开发进度备份，不代表所有模块完成验收。

未纳入本次更新：本机 docker-compose.personal.yml 的部署改动、config.json 及其备份、用户数据、构建产物、截图、业务报告、第三方 vendor 工作目录和软著材料。

上传版本移除了部分代码中的固定凭据回退值，改为读取环境变量；本机运行文件保持原样，因此提交后这些文件仍显示本地修改。部署时应提供相应的 SSO、FastGPT、Neo4j 等环境变量；FASTGPT_KB_BRIDGE_SECRET 应在办公应用与 fastgpt-sso 配置为同一值，API 文件库脚本的 APIDATASET_TOKEN 应与之对应。该处理不表示历史提交已经完成凭据清理。

当前历史回归仍有已知缺口，详见 crm-optimization-progress.md。本次上传不执行生产部署或业务数据迁移。
