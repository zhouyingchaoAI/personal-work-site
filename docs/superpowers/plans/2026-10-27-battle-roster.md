# 联指经营三级作战名单 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 建立统一名单配置并驱动个人、区总、管理三级视图。

**Architecture:** 后端保存版本化作战名单并同步权限策略；月度任务令按精确作战单元裁剪数据；前端权限页提供统一矩阵编辑器。

**Tech Stack:** Python backend, Vue 3, Element Plus

**Spec:** `docs/superpowers/specs/2026-10-27-battle-roster-design.md`

## Global Constraints

- 保留现有权限与审计机制。
- 只有超级管理员可修改统一名单。
- 六个作战单元分别授权，东区三个办事处不互相穿透。

## Review Focus

- 非法账号不能保存。
- 非超级管理员不能修改。
- 重复岗位不重复授权。
- 管理层、负责人、个人范围正确。
- 旧区域权限继续兼容。

### Task 1: 后端名单与权限

**Files:** `backend/crm_security.py`, `backend/server.py`, `tests/unit/test_crm_battle_roster.py`

- [ ] 先写名单校验、保存和三级范围测试并确认失败。
- [ ] 实现名单读取保存、权限同步与路由。
- [ ] 运行单元测试确认通过。

### Task 2: 月度任务令精确单元范围

**Files:** `backend/crm_monthly_battle.py`, `tests/unit/test_monthly_battle.py`

- [ ] 先写东区办事处隔离测试并确认失败。
- [ ] 接入统一名单范围。
- [ ] 运行单元测试确认通过。

### Task 3: 统一配置界面

**Files:** `ai-office-assistant-web/src/views/CrmAssistantView/BattleRosterPanel.vue`, `SecurityPanel.vue`, `services/personalWorkApi.ts`

- [ ] 增加接口类型与名单矩阵组件。
- [ ] 接入权限配置页并构建。
- [ ] 截图核验三级名单配置与紧凑布局。
