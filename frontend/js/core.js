// Shared state, icons, API helpers, authentication, and profile actions.

    let agentKind = null;
    let agentMessages = [];
    let defaultAssistantPrompt = `请帮我优化下面的工作内容，要求：
1、拆分成1、2、3、4这样的编号要点，每点单独换行。
2、语言简洁明了，体现实际工作量和推进成果。
3、修正错别字、病句和不通顺表达。
4、不要编造不存在的事项，不要写空话套话。`;
    let state = { reports: [], selected: null, task: 'weekly', subTab: 'edit', user: null, mailSignature: '', weeklyPrefilled: false, tripPrefilled: false, modalSave: null, restoringDraft: false, assistantMailFiles: [], forumSelected: null, forumCommentPage: 1, currentSkill: null, agentStage: 0 };
    const FORM_DRAFT_PREFIX = 'personalWorkSite.formDraft.v2';
    const el = id => document.getElementById(id);
    const lucideIcons = {
      sparkles: '<path d="M9.94 14.5 8.5 18.06 7.06 14.5 3.5 13.06 7.06 11.62 8.5 8.06l1.44 3.56 3.56 1.44-3.56 1.44Z"/><path d="M18 8.5 17.2 10.7 15 11.5l2.2.8L18 14.5l.8-2.2 2.2-.8-2.2-.8L18 8.5Z"/><path d="M15 2l-.9 2.1L12 5l2.1.9L15 8l.9-2.1L18 5l-2.1-.9L15 2Z"/>',
      search: '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>',
      'layout-dashboard': '<rect width="7" height="9" x="3" y="3" rx="1"/><rect width="7" height="5" x="14" y="3" rx="1"/><rect width="7" height="9" x="14" y="12" rx="1"/><rect width="7" height="5" x="3" y="16" rx="1"/>',
      'file-spreadsheet': '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z"/><path d="M14 2v6h6"/><path d="M8 13h8"/><path d="M8 17h8"/><path d="M10 9v8"/><path d="M14 9v8"/>',
      'briefcase-business': '<path d="M12 12h.01"/><path d="M16 6V4a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v2"/><path d="M22 13a18.15 18.15 0 0 1-20 0"/><rect width="20" height="14" x="2" y="6" rx="2"/>',
      'mail-check': '<path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"/><path d="M22 12.5V6a2 2 0 0 0-2-2H4a2 2 0 0 0-2 2v12c0 1.1.9 2 2 2h8"/><path d="m16 19 2 2 4-4"/>',
      inbox: '<polyline points="22 12 16 12 14 15 10 15 8 12 2 12"/><path d="M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11Z"/>',
      paperclip: '<path d="m21.44 11.05-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"/>',
      'refresh-cw': '<path d="M3 12a9 9 0 0 1 15.1-6.6L21 8"/><path d="M21 3v5h-5"/><path d="M21 12a9 9 0 0 1-15.1 6.6L3 16"/><path d="M3 21v-5h5"/>',
      settings: '<path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.38a2 2 0 0 0-.73-2.73l-.15-.09a2 2 0 0 1-1-1.74v-.51a2 2 0 0 1 1-1.72l.15-.1a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2Z"/><circle cx="12" cy="12" r="3"/>',
      send: '<path d="m22 2-7 20-4-9-9-4Z"/><path d="M22 2 11 13"/>',
      'file-plus-2': '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z"/><path d="M14 2v6h6"/><path d="M12 18v-6"/><path d="M9 15h6"/>',
      bot: '<path d="M12 8V4H8"/><rect width="16" height="12" x="4" y="8" rx="2"/><path d="M2 14h2"/><path d="M20 14h2"/><path d="M15 13v2"/><path d="M9 13v2"/>',
      'bell-ring': '<path d="M10.27 21a2 2 0 0 0 3.46 0"/><path d="M4 8a8 8 0 0 1 16 0c0 7 3 7 3 9H1c0-2 3-2 3-9"/><path d="M18.75 3.2A10 10 0 0 1 22 8"/><path d="M1.99 8a10 10 0 0 1 3.26-4.8"/>',
      'file-text': '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z"/><path d="M14 2v6h6"/><path d="M16 13H8"/><path d="M16 17H8"/><path d="M10 9H8"/>',
      'messages-square': '<path d="M14 9a2 2 0 0 1-2 2H6l-4 4V5a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2Z"/><path d="M18 9h2a2 2 0 0 1 2 2v10l-4-4h-6a2 2 0 0 1-2-2v-1"/>',
      puzzle: '<path d="M19.4 13.5a1.8 1.8 0 0 0 0-3 1.8 1.8 0 0 0-2.4 1.7V9a2 2 0 0 0-2-2h-3.2a1.8 1.8 0 0 0-3.4-1.1A1.8 1.8 0 0 0 10.1 8H7a2 2 0 0 0-2 2v3.1a1.8 1.8 0 0 1 0 3.8V20a2 2 0 0 0 2 2h3.1a1.8 1.8 0 0 1 3.8 0H17a2 2 0 0 0 2-2v-3.1a1.8 1.8 0 0 0 .4-3.4Z"/>',
      'thumbs-up': '<path d="M7 10v12"/><path d="M15 5.88 14 10h5.83a2 2 0 0 1 1.92 2.56l-2.33 8A2 2 0 0 1 17.5 22H4a2 2 0 0 1-2-2v-8a2 2 0 0 1 2-2h3.28a2 2 0 0 0 1.7-.94L13 2a2.3 2.3 0 0 1 2 3.88Z"/>',
      newspaper: '<path d="M4 22h14a2 2 0 0 0 2-2V4H6a2 2 0 0 0-2 2v16Z"/><path d="M18 14h-8"/><path d="M15 18h-5"/><path d="M10 6h6v4h-6z"/><path d="M4 8H2v12a2 2 0 0 0 2 2"/>',
      mail: '<rect width="20" height="16" x="2" y="4" rx="2"/><path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"/>',
      'folder-clock': '<path d="M10 20H4a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2v1.5"/><circle cx="16" cy="16" r="5"/><path d="M16 13v3l2 1"/>',
      archive: '<rect width="20" height="5" x="2" y="3" rx="1"/><path d="M4 8v11a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8"/><path d="M10 12h4"/>',
      'calendar-check': '<path d="M8 2v4"/><path d="M16 2v4"/><rect width="18" height="18" x="3" y="4" rx="2"/><path d="M3 10h18"/><path d="m9 16 2 2 4-4"/>',
      'wand-sparkles': '<path d="m21.64 3.64-1.28-1.28a1.21 1.21 0 0 0-1.72 0L2.36 18.64a1.21 1.21 0 0 0 0 1.72l1.28 1.28a1.21 1.21 0 0 0 1.72 0L21.64 5.36a1.21 1.21 0 0 0 0-1.72Z"/><path d="m14 7 3 3"/><path d="M5 6v4"/><path d="M19 14v4"/><path d="M10 2v2"/><path d="M7 8H3"/><path d="M21 16h-4"/><path d="M11 3H9"/>',
      database: '<ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M3 5v14c0 1.66 4.03 3 9 3s9-1.34 9-3V5"/><path d="M3 12c0 1.66 4.03 3 9 3s9-1.34 9-3"/>',
      'clipboard-pen': '<rect width="8" height="4" x="8" y="2" rx="1"/><path d="M16 4h2a2 2 0 0 1 2 2v9"/><path d="M8 4H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h7"/><path d="M17.5 22 22 17.5 20.5 16 16 20.5V22Z"/>',
      'book-open': '<path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/>',
      'pen-line': '<path d="M12 20h9"/><path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z"/>',
      users: '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>',
      'library': '<path d="m16 6 4 14"/><path d="M12 6v14"/><path d="M8 8v12"/><path d="M4 4v16"/>',
      'chevron-right': '<path d="m9 18 6-6-6-6"/>',
      play: '<polygon points="6 3 20 12 6 21 6 3"/>',
      network: '<rect x="16" y="16" width="6" height="6" rx="1"/><rect x="2" y="16" width="6" height="6" rx="1"/><rect x="9" y="2" width="6" height="6" rx="1"/><path d="M5 16v-3a1 1 0 0 1 1-1h12a1 1 0 0 1 1 1v3"/><path d="M12 12V8"/>',
      copy: '<rect width="14" height="14" x="8" y="8" rx="2" ry="2"/><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/>'
    };

    function renderIcons(root = document) {
      root.querySelectorAll('[data-icon]').forEach(node => {
        const name = node.dataset.icon;
        if (!lucideIcons[name] || node.dataset.iconRendered === 'true') return;
        node.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${lucideIcons[name]}</svg>`;
        node.dataset.iconRendered = 'true';
      });
    }

    function appBasePath() {
      const config = window.PERSONAL_OFFICE_ASSISTANT_CONFIG || {};
      return String(config.appBasePath || '').replace(/\/$/, '');
    }

    function resourceUrl(path) {
      const value = String(path || '');
      if (!value || /^(https?:|data:|blob:)/i.test(value)) return value;
      const basePath = appBasePath();
      if (!basePath || !value.startsWith('/')) return value;
      if (value === basePath || value.startsWith(basePath + '/')) return value;
      return basePath + value;
    }

    function apiUrl(path) {
      const config = window.PERSONAL_OFFICE_ASSISTANT_CONFIG || {};
      const explicitBaseUrl = String(config.apiBaseUrl || '').replace(/\/$/, '');
      const baseUrl = explicitBaseUrl || appBasePath();
      if (/^https?:/i.test(path)) return path;
      if (!baseUrl || !path.startsWith('/')) return path;
      if (path === baseUrl || path.startsWith(baseUrl + '/')) return path;
      return baseUrl + path;
    }

    function responseErrorMessage(res, data, rawText) {
      if (data && data.error) return data.error;
      const text = String(rawText || '').replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim();
      if (text && !/^<!doctype html>/i.test(String(rawText || '').trim())) return text.slice(0, 120);
      return `请求失败（${res.status}）`;
    }

    async function readApiResponse(res) {
      const rawText = await res.text();
      let data = null;
      if (rawText) {
        try {
          data = JSON.parse(rawText);
        } catch (err) {
          if (res.ok) throw new Error('接口返回了非 JSON 数据');
        }
      }
      if (!res.ok) throw new Error(responseErrorMessage(res, data, rawText));
      return data || {};
    }

    async function api(path, options) {
      const res = await fetch(apiUrl(path), options);
      return readApiResponse(res);
    }
    async function apiPost(path, body) {
      const res = await fetch(apiUrl(path), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body || {})
      });
      return readApiResponse(res);
    }

    function applyUser(user) {
      state.user = user;
      const authed = !!user;
      el('authPanel').classList.toggle('hidden', authed);
      el('appMain').classList.toggle('hidden', !authed);
      el('userbar').style.display = authed ? 'flex' : 'none';
      if (el('agentFloat')) el('agentFloat').classList.toggle('hidden', !authed);
      if (authed) {
        const roleText = user.role === 'superadmin' ? '超级管理员' : user.role === 'admin' ? '管理员' : '成员';
        el('userInfo').textContent = `${user.name || user.username} · ${roleText}`;
        el('userAvatar').src = resourceUrl(user.avatar_url || '/assets/ai-assistant-avatar.png');
        if (el('tripReporter') && !el('tripReporter').value.trim()) {
          el('tripReporter').value = user.name || user.username || '';
        }
      }
      if (!authed) state.mailSignature = '';
      document.querySelectorAll('.admin-only').forEach(node => {
        node.classList.toggle('hidden', !user?.is_admin);
      });
      document.querySelectorAll('.superadmin-only').forEach(node => {
        node.classList.toggle('hidden', !user?.is_superadmin);
      });
      el('newsLayout')?.classList.toggle('reader', !user?.is_superadmin);
    }

    function readFileAsBase64(file) {
      return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(String(reader.result || '').split(',')[1] || '');
        reader.onerror = () => reject(reader.error || new Error('读取文件失败'));
        reader.readAsDataURL(file);
      });
    }

    function openProfileModal() {
      const user = state.user || {};
      el('profileName').value = user.name || user.username || '';
      el('profileBio').value = user.bio || '';
      el('profileHobbies').value = user.hobbies || '';
      el('profileAvatarPreview').src = resourceUrl(user.avatar_url || '/assets/ai-assistant-avatar.png');
      el('profileAvatarFile').value = '';
      el('profileStatus').textContent = '';
      el('profileStatus').className = 'status';
      el('profileModal').classList.remove('hidden');
    }

    function closeProfileModal() {
      el('profileModal').classList.add('hidden');
    }

    async function saveProfile(avatarPreset = '') {
      try {
        el('profileStatus').textContent = '保存中...';
        el('profileStatus').className = 'status';
        const file = el('profileAvatarFile').files[0];
        const avatarData = file ? await readFileAsBase64(file) : '';
        const result = await apiPost('/api/profile', {
          name: el('profileName').value,
          bio: el('profileBio').value,
          hobbies: el('profileHobbies').value,
          avatar_data: avatarData,
          avatar_preset: avatarPreset
        });
        applyUser(result.user);
        el('profileAvatarPreview').src = resourceUrl(result.user.avatar_url || '/assets/ai-assistant-avatar.png');
        el('profileAvatarFile').value = '';
        el('profileStatus').textContent = '个人资料已保存';
        el('profileStatus').className = 'status ok';
      } catch (err) {
        el('profileStatus').textContent = err.message;
        el('profileStatus').className = 'status err';
      }
    }
