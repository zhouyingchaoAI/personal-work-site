# 联指经营助手子工程

本目录是联指经营助手业务源码的唯一维护位置。采用同仓库、共享平台基础设施的子工程模式，页面和业务功能不变；不是独立部署的微服务。

## 目录

```text
joint-command/
  frontend/              Vue页面、业务算法、图表、样式、驾驶舱图片
    index.vue            联指助手入口
    MonthlyBattle.vue    月度任务令
    BusinessAnalysis.vue 经营分析
    command/             全屏驾驶舱
    dashboard/           地图与经营面板
  backend/               CRM、经营导入、权限、图谱、月度任务令等Python实现
  scripts/               前后端测试入口
  package.json           开发、构建、类型检查和测试命令
  tsconfig.json          子工程类型检查范围
  migration-manifest.json 拆分时的188个文件及摘要，供一次性迁移审计
```

## 日常开发

在主前端目录使用现有锁文件安装依赖，子工程直接复用主工程 node_modules，不需要再次安装。

```sh
cd ai-office-assistant-web/packages/joint-command
npm run dev
npm run typecheck
npm test
npm run test:backend
npm run build
```

`dev` 通过宿主Vite打开 `/workspace/crm`，仍需正常登录及助手权限；开发API代理沿用宿主环境配置。`build` 执行完整宿主生产构建，输出仍为 `ai-office-assistant-web/dist`，防止与其他助手集成后才发现错误。后端测试需先安装仓库根目录的 Python requirements。

## 集成边界

- 原 `src/views/CrmAssistantView/index.vue` 和 `InternalOrganizationEntry.vue` 仅保留兼容入口。新业务代码不得写回旧目录。
- 原 `backend/crm*.py` 是兼容加载入口，统一调用 `backend/joint_command_loader.py`，真实实现位于本工程 `backend/`。
- `backend/runtime.py` 的加载顺序、共享命名空间和 `__file__=app.py` 的路径语义不变，兼容原有调用、测试mock及Celery任务。
- Python直接导入（例如 `backend.crm_region_identity`）仍通过原模块名工作。
- HTTP路由继续由宿主 `backend/server.py` 分发，API客户端与类型继续使用宿主 `src/services/personalWorkApi.ts`；不复制会话、权限入口、附件及公共服务。
- 组织目录JSON、共享图片、公共组件等仍由平台提供，跨工程引用使用显式相对路径。修改通用API契约需同时检查宿主调用方。
- 测试保留在宿主测试目录，`npm test` 自动运行引用本工程的前端套件；`test:backend` 汇总CRM、月度任务令与拆分兼容测试。

## 数据与部署

没有迁移任何生产数据，数据库、用户目录、配置、历史版本、权限名单和附件路径完全沿用原位置。

Docker镜像仍由仓库根Dockerfile构建。Compose为Web服务和Celery新增本子工程只读挂载；首次切换需重建这两个容器以应用挂载，不重建数据库或删除数据卷：

```sh
docker compose -f docker-compose.personal.yml up -d --no-deps personal-work-site personal-work-celery
```

之后前端更改执行构建，后端更改按原流程重启相关服务。不要只拷贝旧的 `backend/` 部署，必须同时包含本子工程。

## 迁移验证基线

迁移前CRM后端测试250项中已有3项失败、6项跳过：区域地图旧省份断言、区域配置清空、跨区域省份保存。此次拆分不更改区域划分规则，不把这些历史问题作为迁移修复范围。

迁移清单记录文件原始摘要与仅重定位外部引用后的摘要；这是拆分时的审计快照，不应作为后续正常修改业务代码的限制。
