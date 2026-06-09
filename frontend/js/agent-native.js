// Agent Native Experience: persistent sidebar, ui_patches-driven rendering, session recovery, task timeline.
// This module replaces the legacy floating-agent behavior with an AI-native sidebar mode.
// It coexists with legacy agent code; when agent-native is enabled, it takes over rendering.

(function() {
  'use strict';

  // ---------------------------------------------------------------------------
  // State
  // ---------------------------------------------------------------------------
  const NATIVE = {
    enabled: true,
    collapsed: false,
    sessionId: null,
    kind: 'dashboard',
    messages: [],
    stage: 0,
    timeline: [], // { id, title, status, progress, timestamp }
    pendingConfirm: null,
  };

  // ---------------------------------------------------------------------------
  // Helpers
  // ---------------------------------------------------------------------------
  function $id(id) { return document.getElementById(id); }
  function $sel(sel, root) { return (root || document).querySelector(sel); }
  function $selAll(sel, root) { return (root || document).querySelectorAll(sel); }
  function esc(s) {
    if (s == null) return '';
    return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
  }
  function resourceUrl(path) {
    const base = (window.APP_RELATIVE_PATH || window.PERSONAL_OFFICE_ASSISTANT_CONFIG?.appBasePath || '');
    if (path.startsWith('/')) return base + path;
    return base + '/' + path;
  }
  function apiUrl(path) {
    const base = (window.APP_RELATIVE_PATH || window.PERSONAL_OFFICE_ASSISTANT_CONFIG?.appBasePath || '');
    if (path.startsWith('/')) return base + path;
    return base + '/' + path;
  }

  // ---------------------------------------------------------------------------
  // API
  // ---------------------------------------------------------------------------
  async function apiAgentChat(payload) {
    const res = await fetch(apiUrl('/api/agent/chat'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const text = await res.text();
      throw new Error(text || ('HTTP ' + res.status));
    }
    return res.json();
  }

  async function apiSessions(payload) {
    const res = await fetch(apiUrl('/api/agent/sessions'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error('HTTP ' + res.status);
    return res.json();
  }

  async function apiWorkflows(payload) {
    const res = await fetch(apiUrl('/api/workflows'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error('HTTP ' + res.status);
    return res.json();
  }

  // ---------------------------------------------------------------------------
  // Session recovery
  // ---------------------------------------------------------------------------
  async function recoverSession() {
    try {
      const saved = localStorage.getItem('agent_native_session');
      if (saved) {
        const parsed = JSON.parse(saved);
        if (parsed.sessionId) {
          const result = await apiSessions({ action: 'get', session_id: parsed.sessionId, limit: 50 });
          if (result.ok && result.session && result.session.status === 'active') {
            NATIVE.sessionId = parsed.sessionId;
            NATIVE.kind = parsed.kind || 'dashboard';
            if (result.messages && result.messages.length) {
              NATIVE.messages = result.messages.map(m => ({
                role: m.role,
                content: m.content,
                type: (m.metadata && m.metadata.type) || null,
                metadata: m.metadata || {},
              }));
            }
            renderSidebar();
            renderMessages();
            return;
          }
        }
      }
    } catch (e) { /* ignore */ }
    // No recoverable session: start fresh
    startNewSession('dashboard');
  }

  function saveSessionState() {
    try {
      localStorage.setItem('agent_native_session', JSON.stringify({
        sessionId: NATIVE.sessionId,
        kind: NATIVE.kind,
        updatedAt: Date.now(),
      }));
    } catch (e) { /* ignore */ }
  }

  async function startNewSession(kind, title) {
    NATIVE.kind = kind || 'dashboard';
    NATIVE.messages = [];
    NATIVE.stage = 0;
    NATIVE.timeline = [];
    NATIVE.pendingConfirm = null;
    try {
      const result = await apiSessions({ action: 'create', kind: NATIVE.kind, title: title || '' });
      if (result.ok && result.session) {
        NATIVE.sessionId = result.session.id;
      }
    } catch (e) {
      NATIVE.sessionId = 'local_' + Date.now();
    }
    saveSessionState();
    renderSidebar();
    renderMessages();
    appendIntro(kind);
  }

  // ---------------------------------------------------------------------------
  // UI Patches engine (frontend no longer parses skill names)
  // ---------------------------------------------------------------------------
  function applyUiPatches(patches) {
    if (!Array.isArray(patches)) return;
    for (const p of patches) {
      if (!p || !p.op) continue;
      switch (p.op) {
        case 'set_field':
          applySetField(p);
          break;
        case 'show_card':
          applyShowCard(p);
          break;
        case 'navigate':
          applyNavigate(p);
          break;
        case 'append_message':
          applyAppendMessage(p);
          break;
        case 'show_timeline':
          applyShowTimeline(p);
          break;
        case 'request_confirm':
          applyRequestConfirm(p);
          break;
        case 'update_timeline':
          applyUpdateTimeline(p);
          break;
        case 'clear_timeline':
          NATIVE.timeline = [];
          renderTimeline();
          break;
        default:
          console.warn('[ui_patches] unknown op:', p.op);
      }
    }
  }

  function applySetField(p) {
    const el = $sel(p.selector);
    if (!el) return;
    if (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA' || el.tagName === 'SELECT') {
      el.value = p.value || '';
    } else {
      el.innerHTML = p.value || '';
    }
    // Highlight briefly
    el.style.transition = 'box-shadow .4s ease';
    el.style.boxShadow = '0 0 0 2px rgba(59,130,246,.35)';
    setTimeout(() => { el.style.boxShadow = ''; }, 900);
  }

  function applyShowCard(p) {
    const cardType = p.card_type || 'info';
    const data = p.data || {};
    let html = '';
    if (cardType === 'preview') {
      html = `<div class="native-card native-card-preview">
        <div class="native-card-title">预览已生成</div>
        ${data.preview_image_url ? `<img src="${esc(resourceUrl(data.preview_image_url))}" style="max-width:100%;border-radius:8px;cursor:zoom-in;" onclick="window.openAgentLightbox&&openAgentLightbox('${esc(resourceUrl(data.preview_image_url))}')" />` : ''}
        ${data.file ? `<div class="native-card-meta">文件：${esc(data.file)}</div>` : ''}
        ${data.mail_draft && data.mail_draft.subject ? `<div class="native-card-meta">主题：${esc(data.mail_draft.subject)}</div>` : ''}
      </div>`;
    } else if (cardType === 'success') {
      html = `<div class="native-card native-card-success">
        <div class="native-card-title">${esc(data.title || '操作成功')}</div>
        <div class="native-card-body">${esc(data.message || '')}</div>
      </div>`;
    } else if (cardType === 'info') {
      html = `<div class="native-card native-card-info">
        <div class="native-card-title">${esc(data.title || '提示')}</div>
        <div class="native-card-body">${esc(data.message || '')}</div>
      </div>`;
    } else {
      html = `<div class="native-card"><div class="native-card-body">${esc(JSON.stringify(data))}</div></div>`;
    }
    pushNativeMessage({ role: 'assistant', type: 'html', html });
  }

  function applyNavigate(p) {
    const task = p.task;
    if (task && window.navigateTo) {
      window.navigateTo(task, p.sub || 'edit');
    }
  }

  function applyAppendMessage(p) {
    pushNativeMessage({ role: p.role || 'assistant', content: p.content || '' });
  }

  function applyShowTimeline(p) {
    const items = p.items || [];
    NATIVE.timeline = items.map((it, idx) => ({
      id: it.id || ('tl_' + idx),
      title: it.title || '步骤',
      status: it.status || 'pending',
      progress: it.progress || 0,
      timestamp: it.timestamp || Date.now(),
    }));
    renderTimeline();
  }

  function applyUpdateTimeline(p) {
    const id = p.id;
    const item = NATIVE.timeline.find(t => t.id === id);
    if (!item) return;
    if (p.status) item.status = p.status;
    if (p.progress != null) item.progress = p.progress;
    if (p.title) item.title = p.title;
    renderTimeline();
  }

  function applyRequestConfirm(p) {
    NATIVE.pendingConfirm = p;
    const ctx = p.confirmation_context || {};
    const html = `<div class="native-confirm">
      <div class="native-confirm-title">${esc(ctx.title || '确认执行')}</div>
      <div class="native-confirm-body">${esc(ctx.description || '该操作需要确认后才能继续。')}</div>
      ${ctx.diff ? `<pre class="native-confirm-diff">${esc(ctx.diff)}</pre>` : ''}
      <div class="native-confirm-actions">
        <button class="native-btn secondary" data-confirm="cancel">取消</button>
        <button class="native-btn warn" data-confirm="ok">确认执行</button>
      </div>
    </div>`;
    pushNativeMessage({ role: 'assistant', type: 'html', html });
    // Bind confirm buttons
    setTimeout(() => {
      $selAll('.native-confirm-actions button').forEach(btn => {
        btn.onclick = () => handleConfirm(btn.dataset.confirm === 'ok');
      });
    }, 0);
  }

  async function handleConfirm(approved) {
    if (!NATIVE.pendingConfirm) return;
    const ctx = NATIVE.pendingConfirm.confirmation_context || {};
    NATIVE.pendingConfirm = null;
    if (!approved) {
      pushNativeMessage({ role: 'assistant', content: '操作已取消。' });
      return;
    }
    // Resume workflow or skill
    try {
      const result = await apiWorkflows({
        action: 'confirm_and_resume',
        instance_id: ctx.instance_id,
        approved: true,
      });
      if (result.ok) {
        pushNativeMessage({ role: 'assistant', content: result.reply || '操作已确认并继续执行。' });
        if (result.ui_patches) applyUiPatches(result.ui_patches);
      } else {
        pushNativeMessage({ role: 'assistant', content: '确认后执行失败：' + (result.error || '未知错误') });
      }
    } catch (err) {
      pushNativeMessage({ role: 'assistant', content: '确认请求出错：' + err.message });
    }
  }

  // ---------------------------------------------------------------------------
  // Message management
  // ---------------------------------------------------------------------------
  function pushNativeMessage(msg) {
    NATIVE.messages.push(msg);
    renderMessages();
  }

  function appendIntro(kind) {
    const titles = {
      weekly: '周报助手', trip: '出差报告助手', diary: '日记助手',
      forum: '论坛助手', news: '资讯助手', mailassistant: '智能邮件助手',
      dashboard: 'AI 办公总助手',
    };
    const copies = {
      weekly: '直接把本周做过的事、重点项目、下周计划发给我，我会自动整理成周报草稿。',
      trip: '告诉我出差的时间、地点、目的和行程，我帮你整理出差报告。',
      diary: '记录今天的工作内容、明日计划和想法，我可以帮你智能总结。',
      forum: '浏览话题、发起讨论，或让我帮你生成金点子话题。',
      news: '查看每日轨交资讯，或配置资讯来源。',
      mailassistant: '我可以帮你总结邮件、起草回复、润色正文。',
      dashboard: '选择一个工作场景，或直接说你要处理的事。',
    };
    pushNativeMessage({
      role: 'assistant',
      type: 'intro',
      title: titles[kind] || '犇犇',
      copy: copies[kind] || '告诉我你要完成的目标，我会结合当前页面内容帮你整理、填写或生成。',
    });
  }

  // ---------------------------------------------------------------------------
  // Rendering
  // ---------------------------------------------------------------------------
  function renderSidebar() {
    let root = $id('agentNativeSidebar');
    if (!root) {
      root = document.createElement('aside');
      root.id = 'agentNativeSidebar';
      root.className = 'agent-native-sidebar';
      document.body.appendChild(root);
    }
    const collapsedClass = NATIVE.collapsed ? ' collapsed' : '';
    root.className = 'agent-native-sidebar' + collapsedClass;

    root.innerHTML = `
      <div class="native-sidebar-header">
        <div class="native-sidebar-brand">
          <img class="native-sidebar-avatar" src="${resourceUrl('/assets/ai-assistant-avatar.png')}" alt="" />
          <span class="native-sidebar-title">犇犇助手</span>
        </div>
        <button class="native-sidebar-toggle" id="nativeSidebarToggle" title="收起/展开">◀</button>
      </div>
      <div class="native-sidebar-body">
        <div class="native-kind-bar">
          <button class="native-kind-btn ${NATIVE.kind==='dashboard'?'active':''}" data-kind="dashboard" title="总助手">🏠</button>
          <button class="native-kind-btn ${NATIVE.kind==='weekly'?'active':''}" data-kind="weekly" title="周报">📊</button>
          <button class="native-kind-btn ${NATIVE.kind==='trip'?'active':''}" data-kind="trip" title="出差">✈️</button>
          <button class="native-kind-btn ${NATIVE.kind==='diary'?'active':''}" data-kind="diary" title="日记">📝</button>
          <button class="native-kind-btn ${NATIVE.kind==='mailassistant'?'active':''}" data-kind="mailassistant" title="邮件">📧</button>
          <button class="native-kind-btn ${NATIVE.kind==='forum'?'active':''}" data-kind="forum" title="论坛">💬</button>
          <button class="native-kind-btn ${NATIVE.kind==='news'?'active':''}" data-kind="news" title="资讯">📰</button>
        </div>
        <div class="native-timeline" id="nativeTimeline"></div>
        <div class="native-messages" id="nativeMessages"></div>
        <div class="native-input-area">
          <textarea id="nativeInput" placeholder="输入消息…（Ctrl+Enter 发送）"></textarea>
          <button id="nativeSend">发送</button>
        </div>
      </div>
    `;

    // Bind events
    $id('nativeSidebarToggle').onclick = () => {
      NATIVE.collapsed = !NATIVE.collapsed;
      renderSidebar();
    };
    $selAll('.native-kind-btn', root).forEach(btn => {
      btn.onclick = () => {
        const kind = btn.dataset.kind;
        if (kind !== NATIVE.kind) {
          startNewSession(kind);
        }
      };
    });
    $id('nativeSend').onclick = () => sendNativeMessage();
    $id('nativeInput').addEventListener('keydown', e => {
      if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
        e.preventDefault();
        sendNativeMessage();
      }
    });

    renderTimeline();
    renderMessages();
  }

  function renderTimeline() {
    const box = $id('nativeTimeline');
    if (!box) return;
    if (!NATIVE.timeline.length) {
      box.innerHTML = '';
      box.style.display = 'none';
      return;
    }
    box.style.display = 'block';
    box.innerHTML = NATIVE.timeline.map(t => {
      const statusClass = t.status; // pending | running | completed | failed
      const pct = Math.max(0, Math.min(100, Math.round(t.progress || 0)));
      return `<div class="native-tl-item ${esc(statusClass)}">
        <div class="native-tl-dot"></div>
        <div class="native-tl-content">
          <div class="native-tl-title">${esc(t.title)}</div>
          <div class="native-tl-bar"><div class="native-tl-fill" style="width:${pct}%"></div></div>
        </div>
      </div>`;
    }).join('');
  }

  function renderMessages() {
    const box = $id('nativeMessages');
    if (!box) return;
    box.innerHTML = NATIVE.messages.map(m => renderMessageHtml(m)).join('');
    box.scrollTop = box.scrollHeight;
  }

  function renderMessageHtml(m) {
    if (m.type === 'intro') {
      return `<div class="native-msg native-msg-intro">
        <div class="native-msg-intro-title">${esc(m.title)}</div>
        <div class="native-msg-intro-copy">${esc(m.copy)}</div>
      </div>`;
    }
    if (m.type === 'html') {
      return `<div class="native-msg native-msg-assistant">${m.html}</div>`;
    }
    const roleClass = m.role === 'user' ? 'native-msg-user' : 'native-msg-assistant';
    const content = esc(m.content || '');
    return `<div class="native-msg ${roleClass}">${content}</div>`;
  }

  // ---------------------------------------------------------------------------
  // Chat send
  // ---------------------------------------------------------------------------
  async function sendNativeMessage() {
    const input = $id('nativeInput');
    const text = (input.value || '').trim();
    if (!text) return;
    pushNativeMessage({ role: 'user', content: text });
    input.value = '';
    const btn = $id('nativeSend');
    btn.disabled = true;
    btn.textContent = '思考中…';

    try {
      // Gather current page context
      const context = gatherPageContext();
      const payload = {
        session_id: NATIVE.sessionId,
        kind: NATIVE.kind,
        messages: [{ role: 'user', content: text }],
        create_if_missing: !NATIVE.sessionId,
      };
      if (context && Object.keys(context).length) {
        payload.context = context;
      }
      const result = await apiAgentChat(payload);
      if (!result.ok) {
        pushNativeMessage({ role: 'assistant', content: '出错：' + (result.error || '未知错误') });
        return;
      }
      // Update session id if new
      if (result.session_id && result.session_id !== NATIVE.sessionId) {
        NATIVE.sessionId = result.session_id;
        saveSessionState();
      }
      // Append assistant reply
      if (result.reply) {
        pushNativeMessage({ role: 'assistant', content: result.reply });
      }
      // Apply ui_patches
      if (result.ui_patches && result.ui_patches.length) {
        applyUiPatches(result.ui_patches);
      }
      // Handle confirmation
      if (result.requires_confirmation && result.confirmation_context) {
        applyRequestConfirm({ confirmation_context: result.confirmation_context });
      }
      // Auto-remember memory updates (client-side hint)
      if (result.memory_updates && result.memory_updates.length) {
        console.log('[memory_updates]', result.memory_updates);
      }
      // Skill call cards
      if (result.skill_calls && result.skill_calls.length) {
        for (const call of result.skill_calls) {
          const name = call.name || '';
          const data = call.result || {};
          if (name === 'weekly.compose' && data.draft) {
            pushNativeMessage({
              role: 'assistant',
              type: 'html',
              html: `<div class="native-card native-card-success">
                <div class="native-card-title">周报草稿已生成</div>
                <div class="native-card-body">工作总结 ${data.draft.weekly_summary?.length || 0} 项 · 重点跟进 ${data.draft.weekly_follow?.length || 0} 项 · 下周计划 ${data.draft.weekly_next?.length || 0} 项</div>
              </div>`,
            });
          } else if (name === 'weekly.preview' && data.preview_image_url) {
            pushNativeMessage({
              role: 'assistant',
              type: 'html',
              html: `<div class="native-card native-card-preview">
                <div class="native-card-title">周报预览</div>
                <img src="${esc(resourceUrl(data.preview_image_url))}" style="max-width:100%;border-radius:8px;cursor:zoom-in;" onclick="window.openAgentLightbox&&openAgentLightbox('${esc(resourceUrl(data.preview_image_url))}')" />
              </div>`,
            });
          }
        }
      }
    } catch (err) {
      pushNativeMessage({ role: 'assistant', content: '网络错误：' + err.message });
    } finally {
      btn.disabled = false;
      btn.textContent = '发送';
    }
  }

  function gatherPageContext() {
    // Lightweight page context for agent
    const task = (window.state && window.state.task) || 'dashboard';
    const ctx = { task };
    if (task === 'weekly') {
      if (window.collectWorkRows) {
        ctx.weekly_summary = collectWorkRows('summary');
        ctx.weekly_follow = collectWorkRows('follow');
        ctx.weekly_next = collectWorkRows('next');
      }
    } else if (task === 'trip') {
      const ids = ['tripReporter','tripDepartment','tripLocation','tripStart','tripEnd','tripPurpose','tripItinerary','tripDetails','tripWorkApproach','tripIssues','tripSuggestions'];
      ids.forEach(id => { const el = $id(id); if (el) ctx[id] = el.value; });
    } else if (task === 'diary') {
      const ids = ['diaryTodayWork','diaryTomorrowPlan','diaryThoughts'];
      ids.forEach(id => { const el = $id(id); if (el) ctx[id] = el.value; });
    } else if (task === 'mailassistant') {
      const ids = ['assistantMailTo','assistantMailCc','assistantMailSubject','assistantMailBody'];
      ids.forEach(id => { const el = $id(id); if (el) ctx[id] = el.value; });
    }
    return ctx;
  }

  // ---------------------------------------------------------------------------
  // Init
  // ---------------------------------------------------------------------------
  function init() {
    // Remove legacy floating agent if present (hide it, don't destroy)
    const legacyFloat = $id('agentFloat');
    if (legacyFloat) legacyFloat.classList.add('hidden');
    recoverSession();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  // Expose minimal globals for legacy integration
  window.agentNative = {
    startNewSession,
    sendNativeMessage,
    applyUiPatches,
    NATIVE,
  };
})();
