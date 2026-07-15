# Hierarchical Knowledge Base Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add unlimited nested enterprise and personal knowledge bases without disrupting RAGFlow datasets, documents, or chat selections.

**Architecture:** Persist parent/root/owner metadata in the existing knowledge mapping directory, keyed by RAGFlow dataset ID. Enrich the dataset APIs with that metadata and render it as an expandable Vue tree.

**Tech Stack:** Python 3.10, RAGFlow HTTP API, Vue 3/TypeScript/Element Plus, unittest, Vite.

## Global Constraints

- Enterprise nodes: admin managed, authenticated users readable.
- Personal nodes: creator-only visibility and management.
- Existing shared/default-personal datasets are immutable roots; legacy personal datasets become personal-root children.
- Preserve existing dataset IDs and chat-selected knowledge-base IDs.
- Builtin provider retains two read-only roots.

---

### Task 1: Backend hierarchy and authorization

**Files:**
- Modify: `backend/knowledge.py:452-528`
- Modify: `tests/unit/test_knowledge_kb_selection.py`

**Interfaces:** `kb_datasets(username)` returns `parent_id`, `root_type`, `can_manage`, `is_root`; `kb_dataset_manage(payload, username)` accepts `parent_id`.

- [ ] **Step 1: Write failing tests**

```python
def test_legacy_personal_dataset_is_child_of_personal_root(self):
    result = rt.kb_datasets("alice")
    by_id = {item["id"]: item for item in result["kbs"]}
    self.assertEqual(by_id["legacy"]["parent_id"], "personal")

def test_enterprise_child_requires_admin(self):
    with self.assertRaisesRegex(ValueError, "管理员"):
        rt.kb_dataset_manage({"action": "create", "name": "制度", "parent_id": "shared"}, "member")

def test_delete_rejects_root_and_node_with_children(self):
    with self.assertRaises(ValueError):
        rt.kb_dataset_manage({"action": "delete", "id": "personal"}, "alice")
```

- [ ] **Step 2: Verify the test fails**

Run: `python3 -m unittest tests.unit.test_knowledge_kb_selection.KnowledgeKbSelectionTests -v`

Expected: FAIL because tree metadata and parent-aware operations do not exist.

- [ ] **Step 3: Implement minimally**

Add `ragflow_kb_tree.json` helpers alongside `_kb_mapping`. On list, synthesize root metadata and persist missing legacy personal children. On create, resolve the parent’s root type, require `_kb_is_admin` for enterprise and owner equality for personal, call the corresponding RAGFlow tenant, then save metadata. On delete, reject root or a node with a child, enforce the same manager check, delete in RAGFlow, and remove metadata.

- [ ] **Step 4: Verify the focused tests pass**

Run: `python3 -m unittest tests.unit.test_knowledge_kb_selection.KnowledgeKbSelectionTests -v`

Expected: PASS.

- [ ] **Step 5: Commit**

Run: `git add backend/knowledge.py tests/unit/test_knowledge_kb_selection.py && git commit -m "feat: add hierarchical knowledge base metadata"`

### Task 2: Typed tree sidebar

**Files:**
- Modify: `ai-office-assistant-web/src/services/personalWorkApi.ts:1254-1280`
- Modify: `ai-office-assistant-web/src/views/KnowledgeBaseView/index.vue:41-50,675-730,1140-1170`
- Modify: `ai-office-assistant-web/src/views/KnowledgeBaseView/index.scss`
- Modify: `tests/unit/test_knowledge_citations_frontend.py`

**Interfaces:** `KnowledgeKb` adds `parent_id`, `root_type`, `can_manage`, `is_root`; create call sends `parent_id`.

- [ ] **Step 1: Write failing static tests**

```python
def test_knowledge_sidebar_builds_a_tree_and_creates_under_current_node(self):
    self.assertIn("const kbTree = computed", self.source)
    self.assertIn("parent_id: currentKbId.value", self.source)

def test_only_manageable_non_root_nodes_can_be_deleted(self):
    self.assertIn("kb.can_manage && !kb.is_root", self.source)
```

- [ ] **Step 2: Verify failure**

Run: `python3 -m unittest tests.unit.test_knowledge_citations_frontend.KnowledgeCitationFrontendTests -v`

Expected: FAIL because the view uses flat `v-for="kb in kbs"` rendering.

- [ ] **Step 3: Implement minimally**

Extend `KnowledgeKb` and `manageKnowledgeKb` payload types. Add a computed tree that groups entries by `parent_id`, expansion state, indentation/chevrons, and a recursive template or local recursive component. Keep `selectKb` and `scopeParam` unchanged. Put the selected node’s ID in creation requests; hide creation/deletion unless `can_manage`, and never allow root deletion.

- [ ] **Step 4: Verify tests and production build**

Run: `python3 -m unittest tests.unit.test_knowledge_citations_frontend.KnowledgeCitationFrontendTests -v && cd ai-office-assistant-web && pnpm build`

Expected: PASS and successful Vite build.

- [ ] **Step 5: Commit**

Run: `git add ai-office-assistant-web/src/services/personalWorkApi.ts ai-office-assistant-web/src/views/KnowledgeBaseView/index.vue ai-office-assistant-web/src/views/KnowledgeBaseView/index.scss tests/unit/test_knowledge_citations_frontend.py && git commit -m "feat: display knowledge bases as permissioned tree"`

### Task 3: Full verification and Docker deployment

**Files:** Modify only task files if a verification defect is found.

- [ ] **Step 1: Run all tests**

Run: `./scripts/run_tests.sh`

Expected: PASS.

- [ ] **Step 2: Build and deploy**

Run: `cd ai-office-assistant-web && pnpm build && cd .. && docker compose -f docker-compose.personal.yml up -d --build personal-work-site`

Expected: the Docker service builds and runs.

- [ ] **Step 3: Check service**

Run: `docker compose -f docker-compose.personal.yml ps personal-work-site && curl -fsS http://127.0.0.1:8765/api/knowledge/kbs`

Expected: running service and JSON response (or expected unauthenticated response).
