# 微信公众号资讯源 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让每日资讯将微信公众号作为明确的来源类型配置，而非把单篇文章伪装成资讯网页。

**Architecture:** 后端保留来源的 `kind` 字段，并对微信公众号要求账号名和一篇微信文章入口。采集时以该入口提取公众号正文；前端根据来源类型提供语义化字段和使用提示。

**Tech Stack:** Python 标准库后端、Vue 3、TypeScript、unittest。

## Global Constraints

- 网页来源的现有配置和采集行为必须兼容。
- 微信文章链接仅作采集入口与账号校验，不声称可无授权枚举公众号历史或未来文章。

---

### Task 1: 公众号来源后端模型与校验

**Files:**
- Modify: `backend/news.py`
- Test: `tests/unit/test_news_history.py`

- [ ] **Step 1: Write the failing test**

```python
sources = rt.clean_news_sources([{
    "kind": "wechat_account", "name": "新智元",
    "url": "https://mp.weixin.qq.com/s/example",
}])
self.assertEqual(sources[0]["kind"], "wechat_account")
with self.assertRaisesRegex(ValueError, "公众号入口"):
    rt.clean_news_sources([{"kind": "wechat_account", "name": "新智元", "url": "https://example.com"}])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.unit.test_news_history.NewsHistoryTests.test_clean_news_sources_preserves_wechat_account -v`
Expected: FAIL because `kind` is discarded and invalid WeChat URL is accepted.

- [ ] **Step 3: Write minimal implementation**

```python
kind = str(item.get("kind", "web") or "web").strip().lower()
if kind not in {"web", "wechat_account"}:
    kind = "web"
if kind == "wechat_account" and not re.match(r"^https?://mp\\.weixin\\.qq\\.com/s/", url, re.I):
    raise ValueError("公众号入口需要填写一篇 mp.weixin.qq.com/s/... 文章链接")
clean_sources.append({"name": name, "url": url, "kind": kind})
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.unit.test_news_history -v`
Expected: PASS.

### Task 2: 资讯配置界面

**Files:**
- Modify: `ai-office-assistant-web/src/services/personalWorkApi.ts`
- Modify: `ai-office-assistant-web/src/views/NewsView/index.vue`

- [ ] **Step 1: Extend `NewsSource` and preserve `kind` when loading/saving**
- [ ] **Step 2: Render a source-type selector and type-specific labels**
- [ ] **Step 3: Add an explicit WeChat collection limitation note**
- [ ] **Step 4: Build the frontend**

Run: `npm run build` in `ai-office-assistant-web`.
Expected: exit code 0.
