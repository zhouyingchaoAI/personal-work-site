# CRM Change Approval Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让客户经理提交的既有资料变更经客户经营管理员审批后才写入正式 CRM 档案。

**Architecture:** `crm_security.py` 定义客户经理能力；`crm.py` 保存待审变更并在审批后受控应用；Excel 与信息收集调用同一提交入口；权限页展示待审队列并调用审批接口。

**Tech Stack:** Python 标准库 JSON 存储、现有 HTTP Handler、Vue 3、Element Plus。

**Spec:** `docs/superpowers/specs/2026-09-10-crm-change-approval-design.md`

## Global Constraints

- 客户经理不可直接覆盖既有正式字段。
- 审批仅允许客户经营管理员或超级管理员执行。
- 既有编辑/导入角色与历史版本机制保持兼容。

---

### Task 1: 审批数据与服务端权限

**Files:**
- Modify: `backend/crm_security.py`, `backend/crm.py`, `backend/server.py`
- Test: `tests/unit/test_crm_security.py`

**Interfaces:**
- Produces `crm_change_request_submit(payload, username)`, `crm_change_requests(user)`, `crm_change_request_decide(payload, user)`。

- [ ] 写出客户经理提交冲突资料不会改正式记录、管理员审批后才改动的失败测试。
- [ ] 运行该测试并确认失败。
- [ ] 实现客户经理角色、待审 JSON 集合、申请读取与审批/驳回接口；审批写入前保留既有版本。
- [ ] 运行测试并确认通过。

### Task 2: 上传与信息收集接入

**Files:**
- Modify: `backend/crm_excel.py`, `backend/server.py`
- Test: `tests/unit/test_crm_business_excel.py`

**Interfaces:**
- Consumes `crm_change_request_submit`。
- Produces上传结果的 `pending` 计数与信息收集的 `pending_approval` 状态。

- [ ] 写出客户经理对现有档案上传不同字段生成待审而不覆盖的失败测试。
- [ ] 运行该测试并确认失败。
- [ ] 在 Excel/页面收集路径检查客户经理冲突并创建申请，新增资料仍正常创建。
- [ ] 运行 CRM 导入测试并确认通过。

### Task 3: 管理员审批界面

**Files:**
- Modify: `ai-office-assistant-web/src/services/personalWorkApi.ts`, `ai-office-assistant-web/src/views/CrmAssistantView/SecurityPanel.vue`, `ai-office-assistant-web/src/views/CrmAssistantView/ExcelImport.vue`
- Test: `tests/unit/test_crm_mobile_frontend.py`

**Interfaces:**
- Consumes审批列表、审批决定 API。
- Produces管理员待审列表、上传结果的待审批反馈。

- [ ] 写出界面包含审批队列、审批/驳回操作和待审批提示的失败静态测试。
- [ ] 运行测试并确认失败。
- [ ] 实现 API 客户端、管理员审批队列及上传结果提示。
- [ ] 运行前端测试和生产构建并确认通过。

### Task 4: 交付验证

- [ ] 运行 CRM 与权限全套单元测试。
- [ ] 重启 Web 服务并确认入口 HTTP 200。
