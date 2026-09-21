# Cashflow Workbook Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let superadmins complete and export the supplied 19-sheet project cashflow workbook without leaving the assistant.

**Architecture:** Store one pristine reference workbook in shared application data and one compact per-user JSON overlay of edited cells. The API reads sheet geometry and formulas from the template, accepts only user-cell overlays, and exports a copied workbook with those overlays applied. The Vue workbench renders one sheet at a time with customer/region history guidance beside it.

**Tech Stack:** Python 3, openpyxl, existing HTTP server/runtime, Vue 3, Element Plus.

**Spec:** User-provided 金华轨道交通金义东线资金测算 workbook.

## Global Constraints

- Preserve all 19 source sheet names, formula cells, merged cells, and workbook structure in exports.
- Do not persist the supplied workbook password or any credential.
- Keep all data behind existing cashflow assistant permission checks.

---

### Task 1: Workbook storage and export API

**Files:**
- Create: `backend/cashflow_workbook.py`
- Modify: `backend/runtime.py`, `backend/server.py`
- Test: `tests/unit/test_cashflow.py`

- [ ] Add a failing test that saves cell `B3` to a generated workbook state and asserts the export retains the original formula cell and applies `B3`.
- [ ] Add template inspection, overlay validation, per-user state persistence, and export functions.
- [ ] Register authenticated read/save/export routes.
- [ ] Run `python3 -m unittest tests.unit.test_cashflow`.

### Task 2: Workbook workbench UI

**Files:**
- Modify: `ai-office-assistant-web/src/services/personalWorkApi.ts`, `ai-office-assistant-web/src/views/CashflowAssistantView/index.vue`
- Test: `tests/unit/test_cashflow.py`

- [ ] Add typed get/save/export client calls and an entry point from the cashflow assistant.
- [ ] Add staged sheet navigation, editable non-formula cells, save state, export action, and live customer/region history guidance.
- [ ] Build with `npm run build` and confirm the current history API remains available.
