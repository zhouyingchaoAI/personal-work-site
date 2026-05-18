    let agentKind = null;
    let agentMessages = [];
    let defaultAssistantPrompt = `请帮我优化下面的工作内容，要求：
1、拆分成1、2、3、4这样的编号要点，每点单独换行。
2、语言简洁明了，体现实际工作量和推进成果。
3、修正错别字、病句和不通顺表达。
4、不要编造不存在的事项，不要写空话套话。`;
    let state = { reports: [], selected: null, task: 'weekly', subTab: 'edit', user: null, weeklyPrefilled: false, tripPrefilled: false, modalSave: null, restoringDraft: false, assistantMailFiles: [], forumSelected: null, forumCommentPage: 1, currentSkill: null, agentStage: 0 };
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
      play: '<polygon points="6 3 20 12 6 21 6 3"/>'
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

    async function api(path, options) {
      const res = await fetch(apiUrl(path), options);
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || '请求失败');
      return data;
    }
    async function apiPost(path, body) {
      const res = await fetch(apiUrl(path), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body || {})
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || '请求失败');
      return data;
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
      }
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

    function renderReports() {
      const kind = el('mailKind').value;
      const list = state.reports.filter(r => r.kind === kind);
      el('reports').innerHTML = list.map(r => `
        <div class="report ${state.selected === r.name ? 'active' : ''}" data-name="${encodeURIComponent(r.name)}">
          <div class="report-head">
            <div>
              <div class="name">${escapeHtml(r.name)}</div>
              <div class="meta">${r.generated ? '新生成' : (r.kind === 'weekly' ? '周报模板' : '出差报告模板')} · ${new Date(r.mtime * 1000).toLocaleString()}</div>
            </div>
            <div class="report-actions">
              ${r.deletable ? `<button class="mini danger delete-report-file" type="button">删除</button>` : ''}
            </div>
          </div>
        </div>
      `).join('');
      document.querySelectorAll('.report').forEach(node => {
        node.addEventListener('click', () => loadDraft(kind, decodeURIComponent(node.dataset.name)));
      });
      el('reports').querySelectorAll('.delete-report-file').forEach(button => {
        button.addEventListener('click', event => {
          event.stopPropagation();
          deleteReportFile(kind, decodeURIComponent(button.closest('.report').dataset.name));
        });
      });
    }

    function clearMailDraft() {
      ['to', 'cc', 'subject', 'body', 'attachment'].forEach(id => {
        if (el(id)) el(id).value = '';
      });
      state.bodyHtml = '';
      renderBodyPreview();
      el('downloadLink')?.classList.add('hidden');
      if (el('preview')) el('preview').innerHTML = '暂无可预览内容';
      clearSendReview();
    }

    async function deleteReportFile(kind, name) {
      if (!confirm('确定删除这个报告文件吗？\n' + name)) return;
      const wasSelected = state.selected === name;
      try {
        const result = await api('/api/delete-report', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ name })
        });
        el('status').textContent = '已删除报告文件：' + result.deleted;
        el('status').className = 'status ok';
        if (wasSelected) state.selected = '';
        await loadReports({ preserveSelection: true });
        if (wasSelected) {
          const next = state.reports.find(r => r.kind === kind)?.name || '';
          state.selected = next;
          renderReports();
          if (next) await loadDraft(kind, next);
          else clearMailDraft();
        }
      } catch (err) {
        el('status').textContent = err.message;
        el('status').className = 'status err';
      }
    }

    function reportKindName(kind) {
      return kind === 'weekly' ? '周报' : '出差报告';
    }

    function renderRecentDocs() {
      const list = state.reports.slice(0, 6);
      const box = el('recentDocsList');
      if (!box) return;
      box.innerHTML = list.length ? list.map(r => `
        <div class="doc-item">
          <div>
            <div class="doc-name">${escapeHtml(r.name)}</div>
            <div class="doc-meta">${r.kind === 'weekly' ? '周报' : '出差报告'} · ${new Date(r.mtime * 1000).toLocaleDateString()}</div>
          </div>
          <a class="download-link" style="padding:6px 12px;font-size:12px;" href="${resourceUrl('/download?file=' + encodeURIComponent(r.name))}" target="_blank">查看</a>
        </div>
      `).join('') : '<div class="doc-item"><span class="doc-name">暂无最近文档</span></div>';
    }

    function renderHistoryReports() {
      const kind = el('historyKind')?.value || 'all';
      const list = state.reports.filter(r => !r.generated && (kind === 'all' || r.kind === kind));
      el('historyList').innerHTML = list.length ? list.map(r => `
        <div class="history-item" data-name="${encodeURIComponent(r.name)}">
          <div>
            <div class="history-name">${escapeHtml(r.name)}</div>
            <div class="history-meta">${reportKindName(r.kind)} · ${new Date(r.mtime * 1000).toLocaleString()}</div>
          </div>
          <div class="history-actions">
            <a class="download-link" href="${resourceUrl('/download?file=' + encodeURIComponent(r.name))}" target="_blank">下载</a>
            <button class="mini danger delete-history" type="button">删除</button>
          </div>
        </div>
      `).join('') : '<div class="upload-item">暂无历史报告。</div>';
      el('historyList').querySelectorAll('.delete-history').forEach(button => {
        button.addEventListener('click', async () => {
          const name = decodeURIComponent(button.closest('.history-item').dataset.name);
          if (!confirm('确定删除这个历史报告吗？\n' + name)) return;
          try {
            const result = await api('/api/delete-history', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ name })
            });
            el('status').textContent = '已删除历史报告：' + result.deleted;
            el('status').className = 'status ok';
            await loadReports({ preserveSelection: true });
          } catch (err) {
            el('status').textContent = err.message;
            el('status').className = 'status err';
          }
        });
      });
    }

    function setSubTab(sub) {
      state.subTab = sub;
      document.querySelectorAll('.sub-tab').forEach(tab => {
        tab.classList.toggle('active', tab.dataset.sub === sub);
      });
      const task = state.task;
      const isAssistant = task === 'weekly' || task === 'trip';
      const isWeekly = task === 'weekly';
      const isEdit = sub === 'edit';
      const isMail = sub === 'mail';
      const isHistory = sub === 'history';
      el('weeklyPanel').classList.toggle('hidden', !isAssistant || !isWeekly || !isEdit);
      el('tripPanel').classList.toggle('hidden', !isAssistant || isWeekly || !isEdit);
      el('generateToolbar').classList.toggle('hidden', !isAssistant || !isEdit);
      el('mailPanel').classList.toggle('hidden', !isAssistant || !isMail);
      el('uploadPanel').classList.toggle('hidden', !isAssistant || !isHistory);
      if (isMail) renderReports();
      if (isHistory) renderHistoryReports();
      el('status').textContent = '';
      el('status').className = 'status';
    }

    function navigateTo(task, sub) {
      state.subTab = sub || 'edit';
      setTask(task);
    }

    function setTask(task) {
      state.task = task;
      document.querySelectorAll('.task-card').forEach(card => {
        card.classList.toggle('active', card.dataset.task === task);
      });
      const isDashboard = task === 'dashboard';
      const isAssistant = task === 'weekly' || task === 'trip';
      el('dashboardPanel').classList.toggle('hidden', !isDashboard);
      el('pageHeader').classList.toggle('hidden', isDashboard);
      el('subTabs').classList.toggle('hidden', !isAssistant);
      el('weeklyPanel').classList.add('hidden');
      el('tripPanel').classList.add('hidden');
      el('mailPanel').classList.add('hidden');
      el('uploadPanel').classList.add('hidden');
      el('mailAssistantPanel').classList.toggle('hidden', task !== 'mailassistant');
      el('diaryPanel').classList.toggle('hidden', task !== 'diary');
      el('forumPanel').classList.toggle('hidden', task !== 'forum');
      el('newsPanel').classList.toggle('hidden', task !== 'news');
      el('generateToolbar').classList.add('hidden');
      el('configPanel').classList.toggle('hidden', task !== 'config');
      el('mailConfigPanel').classList.toggle('hidden', task !== 'mailconfig');
      el('skillsPanel').classList.toggle('hidden', task !== 'skills');
      el('userManagePanel').classList.toggle('hidden', task !== 'usermanage');
      if (!isAssistant) {
        state.subTab = 'edit';
        document.querySelectorAll('.sub-tab').forEach(tab => tab.classList.toggle('active', tab.dataset.sub === 'edit'));
      }
      const titles = { dashboard: '工作台', weekly: '周报助手', trip: '出差报告助手', diary: '工作日记', forum: '金点子论坛', news: '每日资讯', mailassistant: '邮件助手', config: '系统配置', mailconfig: '邮件配置', skills: '系统 Skill', usermanage: '用户管理' };
      const descs = {
        dashboard: '智能办公一站式工作台',
        weekly: '填写周报、发送邮件、管理历史周报',
        trip: '填写出差报告、发送邮件、管理历史出差报告',
        diary: '记录每日工作、查看历史日记，写周报时可智能总结',
        forum: '智能体或成员发起每日话题，大家围绕创意、改进和机会展开讨论',
        news: '收集轨道交通关键资讯，调用平台大模型生成每日简报',
        mailassistant: '查看收件箱、阅读邮件、发送普通邮件',
        config: '管理员配置 AI 接口和系统参数',
        mailconfig: '配置发件邮箱、收件人和抄送地址',
        skills: '查看已安装 Skill、能力说明、调用参数和示例',
        usermanage: '管理系统用户、角色权限和密码'
      };
      el('taskTitle').textContent = titles[task] || '';
      el('taskDesc').textContent = descs[task] || '';
      syncAgentToTask(task);
      if (isDashboard) {
        renderRecentDocs();
        const u = state.user;
        el('dashUserName').textContent = u ? (u.name || u.username) : '';
      }
      if (isAssistant) {
        el('kind').value = task;
        el('mailKind').value = task;
        el('uploadKind').value = task;
        el('historyKind').value = task;
        const hideEl = (sel) => { if (sel) sel.style.display = 'none'; };
        const hidePrevLabel = (sel) => { const lab = sel?.previousElementSibling; if (lab && lab.tagName === 'LABEL') lab.style.display = 'none'; };
        hideEl(el('mailKind')); hidePrevLabel(el('mailKind'));
        hideEl(el('uploadKind')); hidePrevLabel(el('uploadKind'));
        const historyTools = el('historyKind')?.closest('.history-tools');
        if (historyTools) historyTools.style.display = 'none';
        setSubTab(state.subTab || 'edit');
      }
      if (task === 'mailconfig') {
        loadMailConfig();
      }
      if (task === 'skills') {
        loadSkills();
      }
      if (task === 'mailassistant') {
        loadMailbox();
      }
      if (task === 'diary') {
        initDiaryPanel();
      }
      if (task === 'forum') {
        loadForumTopics();
      }
      if (task === 'news') {
        loadNews();
      }
    }

    function workFields(section) {
      const isNext = section === 'next';
      return isNext
        ? [
            ['category', '工作分类'],
            ['content', '工作内容'],
            ['difficulty', '困难与求助']
          ]
        : [
            ['category', '工作分类'],
            ['content', '工作内容'],
            [section === 'summary' ? 'status' : 'progress', section === 'summary' ? '完成情况' : '当前进展'],
            [section === 'summary' ? 'plan' : 'difficulty', section === 'summary' ? '后续计划' : '困难与求助']
          ];
    }

    function sectionName(section) {
      return { summary: '本周工作总结', follow: '重点工作跟进', next: '下周工作计划' }[section] || '工作内容';
    }

    function sectionTarget(section) {
      return section === 'summary' ? el('summaryRows') : section === 'follow' ? el('followRows') : el('nextRows');
    }

    function updateWeeklyCounts() {
      [['summary', 'summaryCount'], ['follow', 'followCount'], ['next', 'nextCount']].forEach(([section, id]) => {
        const count = collectWorkRows(section).length;
        if (el(id)) el(id).textContent = count;
      });
    }

    function rowPreview(row) {
      const parts = [row.category, row.content, row.status, row.progress, row.plan, row.difficulty]
        .map(value => String(value || '').trim())
        .filter(Boolean);
      return parts.join('\n') || '点击填写任务内容';
    }

    function rowTemplate(section, row, index) {
      const fields = workFields(section);
      const title = row.category || `${sectionName(section)} ${index + 1}`;
      return `
        <div class="work-block" data-section="${section}" data-index="${index}">
          <div class="work-head">
            <div class="work-title">${escapeHtml(title)}</div>
            <button class="mini danger remove-row" type="button">删除</button>
          </div>
          <div class="work-summary">${escapeHtml(rowPreview(row))}</div>
          <div class="field-store">
            ${fields.map(([key, label]) => `
              <textarea data-key="${key}" data-label="${label}">${escapeHtml(row[key] || '')}</textarea>
            `).join('')}
          </div>
        </div>`;
    }

    function escapeHtml(value) {
      return String(value ?? '').replace(/[&<>"']/g, ch => ({
        '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
      }[ch]));
    }

    function renderWorkRows(section, rows) {
      const target = sectionTarget(section);
      target.innerHTML = (rows && rows.length ? rows : [{}]).map((row, index) => rowTemplate(section, row, index)).join('');
      attachWorkEvents(target);
      updateWeeklyCounts();
    }

    function attachWorkEvents(target) {
      target.querySelectorAll('.remove-row').forEach(button => {
        button.addEventListener('click', event => {
          event.stopPropagation();
          button.closest('.work-block').remove();
          renumberRows(target);
          updateWeeklyCounts();
        });
      });
      target.querySelectorAll('.work-block').forEach(block => {
        block.addEventListener('click', () => openWorkModal(block));
      });
    }

    function renumberRows(container) {
      container.querySelectorAll('.work-block').forEach((block, index) => {
        block.dataset.index = index;
        refreshWorkCard(block);
      });
    }

    function addWorkRow(section, row = {}) {
      const target = sectionTarget(section);
      if (target.children.length === 1 && !target.querySelector('textarea')?.value.trim()) {
        target.innerHTML = '';
      }
      const wrapper = document.createElement('div');
      wrapper.innerHTML = rowTemplate(section, row, target.children.length).trim();
      const block = wrapper.firstElementChild;
      target.appendChild(block);
      attachWorkEvents(target);
      updateWeeklyCounts();
      openWorkModal(block);
    }

    function collectWorkRows(section) {
      const target = sectionTarget(section);
      return [...target.querySelectorAll('.work-block')].map(block => {
        const row = {};
        block.querySelectorAll('textarea[data-key]').forEach(input => {
          row[input.dataset.key] = input.value.trim();
        });
        return row;
      }).filter(row => Object.values(row).some(Boolean));
    }

    function refreshWorkCard(block) {
      const row = {};
      block.querySelectorAll('textarea[data-key]').forEach(input => {
        row[input.dataset.key] = input.value.trim();
      });
      const section = block.dataset.section;
      const index = Number(block.dataset.index || 0);
      block.querySelector('.work-title').textContent = row.category || `${sectionName(section)} ${index + 1}`;
      block.querySelector('.work-summary').textContent = rowPreview(row);
      updateWeeklyCounts();
      saveFormDraft();
    }

    function openModal(title, fields, onSave) {
      el('modalTitle').textContent = title;
      el('modalFields').innerHTML = fields.map(field => {
        const wide = field.multiline ? ' wide' : '';
        const control = field.multiline
          ? `<textarea data-modal-key="${field.key}" placeholder="${field.label}">${escapeHtml(field.value || '')}</textarea>`
          : `<input data-modal-key="${field.key}" type="${field.type || 'text'}" placeholder="${field.label}" value="${escapeHtml(field.value || '')}" />`;
        const assist = field.multiline ? `
          <div class="field-assist">
            <div class="field-assist-head">
              <details>
                <summary>展开/修改提示词</summary>
                <textarea class="field-assist-prompt">${escapeHtml(defaultAssistantPrompt)}</textarea>
              </details>
              <button class="warn assist-optimize" type="button">辅助优化</button>
            </div>
            <div class="assist-status">待优化</div>
          </div>` : '';
        return `
          <div class="${wide}">
            <label>${field.label}</label>
            ${assist}
            ${control}
          </div>`;
      }).join('');
      state.modalSave = onSave;
      el('editModal').classList.remove('hidden');
      const first = el('modalFields').querySelector('input, textarea');
      if (first) first.focus();
    }

    function closeModal() {
      el('editModal').classList.add('hidden');
      state.modalSave = null;
    }

    function saveAndCloseModal() {
      saveCurrentModal();
      closeModal();
    }

    function modalValues() {
      const values = {};
      el('modalFields').querySelectorAll('[data-modal-key]').forEach(input => {
        values[input.dataset.modalKey] = input.value.trim();
      });
      return values;
    }

    function draftStorageKey() {
      return state.user?.username ? `${FORM_DRAFT_PREFIX}:${state.user.username}` : '';
    }

    function tripFormPayload() {
      return {
        reporter: el('tripReporter').value,
        department: el('tripDepartment').value,
        location: el('tripLocation').value,
        trip_start: el('tripStart').value,
        trip_end: el('tripEnd').value,
        purpose: el('tripPurpose').value,
        itinerary: el('tripItinerary').value,
        details: el('tripDetails').value,
        issues: el('tripIssues').value,
        suggestions: el('tripSuggestions').value
      };
    }

    function saveFormDraft() {
      const key = draftStorageKey();
      if (!key || state.restoringDraft) return;
      try {
        const draft = {
          updatedAt: Date.now(),
          weekly: {
            start: el('weeklyStart').value,
            end: el('weeklyEnd').value,
            period: el('weeklyPeriod').value,
            summary: collectWorkRows('summary'),
            follow: collectWorkRows('follow'),
            next: collectWorkRows('next')
          },
          trip: tripFormPayload()
        };
        localStorage.setItem(key, JSON.stringify(draft));
      } catch (err) {
        console.warn('保存本地草稿失败', err);
      }
    }

    function restoreSavedFormDraft(kind) {
      const key = draftStorageKey();
      if (!key) return false;
      let draft = null;
      try {
        draft = JSON.parse(localStorage.getItem(key) || 'null');
      } catch (err) {
        return false;
      }
      if (!draft) return false;
      state.restoringDraft = true;
      try {
        if (kind === 'weekly' && draft.weekly) {
          if (draft.weekly.start) el('weeklyStart').value = draft.weekly.start;
          if (draft.weekly.end) el('weeklyEnd').value = draft.weekly.end;
          syncWeeklyPeriod();
          if ((draft.weekly.summary || []).length || (draft.weekly.follow || []).length || (draft.weekly.next || []).length) {
            renderWorkRows('summary', draft.weekly.summary || []);
            renderWorkRows('follow', draft.weekly.follow || []);
            renderWorkRows('next', draft.weekly.next || []);
            state.weeklyPrefilled = true;
            return true;
          }
        }
        if (kind === 'trip' && draft.trip) {
          Object.entries({
            tripReporter: draft.trip.reporter,
            tripDepartment: draft.trip.department,
            tripLocation: draft.trip.location,
            tripStart: draft.trip.trip_start,
            tripEnd: draft.trip.trip_end,
            tripPurpose: draft.trip.purpose,
            tripItinerary: draft.trip.itinerary,
            tripDetails: draft.trip.details,
            tripIssues: draft.trip.issues,
            tripSuggestions: draft.trip.suggestions
          }).forEach(([id, value]) => {
            if (value !== undefined && value !== null) el(id).value = value;
          });
          renderTripCards();
          state.tripPrefilled = true;
          return true;
        }
      } finally {
        state.restoringDraft = false;
      }
      return false;
    }

    function clearSavedFormDraft(kind) {
      const key = draftStorageKey();
      if (!key) return;
      try {
        const draft = JSON.parse(localStorage.getItem(key) || '{}');
        if (kind === 'weekly') delete draft.weekly;
        if (kind === 'trip') delete draft.trip;
        localStorage.setItem(key, JSON.stringify({ ...draft, updatedAt: Date.now() }));
      } catch (err) {
        localStorage.removeItem(key);
      }
    }

    function saveCurrentModal() {
      if (state.modalSave) {
        state.modalSave(modalValues());
        saveFormDraft();
      }
    }

    function openWorkModal(block) {
      const section = block.dataset.section;
      const index = Number(block.dataset.index || 0) + 1;
      const fields = workFields(section).map(([key, label]) => {
        const input = block.querySelector(`[data-key="${key}"]`);
        return { key, label, value: input?.value || '', multiline: key !== 'category' };
      });
      openModal(`${sectionName(section)} ${index}`, fields, values => {
        fields.forEach(field => {
          const input = block.querySelector(`[data-key="${field.key}"]`);
          if (input) input.value = values[field.key] || '';
        });
        refreshWorkCard(block);
      });
    }

    const tripGroups = [
      {
        key: 'base',
        title: '基础信息',
        fields: [
          ['tripReporter', '报告人', false],
          ['tripDepartment', '部门', false],
          ['tripLocation', '出差地点', false],
          ['tripStart', '开始日期', false, 'date'],
          ['tripEnd', '结束日期', false, 'date']
        ]
      },
      { key: 'purpose', title: '出差目的', fields: [['tripPurpose', '出差目的', true]] },
      { key: 'itinerary', title: '行程概览', fields: [['tripItinerary', '行程概览', true]] },
      { key: 'details', title: '工作详情', fields: [['tripDetails', '工作详情', true]] },
      { key: 'issues', title: '问题与反馈', fields: [['tripIssues', '问题与反馈', true]] },
      { key: 'suggestions', title: '总结与建议', fields: [['tripSuggestions', '总结与建议', true]] }
    ];

    function tripPreview(group) {
      const values = group.fields.map(([id, label]) => {
        const value = el(id).value.trim();
        return value ? (group.key === 'base' ? `${label}：${value}` : value) : '';
      }).filter(Boolean);
      return values.join('\n') || '点击填写内容';
    }

    function formatPeriodDate(value) {
      if (!value) return '';
      const [year, month, day] = value.split('-').map(Number);
      if (!year || !month || !day) return value;
      return `${year}.${month}.${day}`;
    }

    function toDateInputValue(date) {
      const year = date.getFullYear();
      const month = String(date.getMonth() + 1).padStart(2, '0');
      const day = String(date.getDate()).padStart(2, '0');
      return `${year}-${month}-${day}`;
    }

    function setDefaultWeeklyDates(force = false) {
      if (!force && (el('weeklyStart').value || el('weeklyEnd').value)) {
        syncWeeklyPeriod();
        return;
      }
      const today = new Date();
      const day = today.getDay() || 7;
      const thisMonday = new Date(today);
      thisMonday.setHours(0, 0, 0, 0);
      thisMonday.setDate(today.getDate() - day + 1);
      const thisFriday = new Date(thisMonday);
      thisFriday.setDate(thisMonday.getDate() + 4);
      el('weeklyStart').value = toDateInputValue(thisMonday);
      el('weeklyEnd').value = toDateInputValue(thisFriday);
      el('diarySumStart').value = toDateInputValue(thisMonday);
      el('diarySumEnd').value = toDateInputValue(thisFriday);
      syncWeeklyPeriod();
    }

    function syncWeeklyPeriod() {
      const start = formatPeriodDate(el('weeklyStart').value);
      const end = formatPeriodDate(el('weeklyEnd').value);
      el('weeklyPeriod').value = start && end ? `${start}-${end}` : (start || end);
      if (el('weeklyPeriodText')) {
        el('weeklyPeriodText').textContent = el('weeklyPeriod').value || '未选择时段';
      }
      saveFormDraft();
    }

    function renderTripCards() {
      el('tripCards').innerHTML = tripGroups.map(group => `
        <div class="edit-card" data-trip-group="${group.key}">
          <div class="edit-card-title">${group.title}</div>
          <div class="edit-card-preview">${escapeHtml(tripPreview(group))}</div>
        </div>
      `).join('');
      el('tripCards').querySelectorAll('.edit-card').forEach(card => {
        card.addEventListener('click', () => openTripModal(card.dataset.tripGroup));
      });
    }

    function openTripModal(groupKey) {
      const group = tripGroups.find(item => item.key === groupKey);
      if (!group) return;
      const fields = group.fields.map(([id, label, multiline, type]) => ({
        key: id,
        label,
        multiline,
        type,
        value: el(id).value
      }));
      openModal(group.title, fields, values => {
        fields.forEach(field => {
          el(field.key).value = values[field.key] || '';
        });
        renderTripCards();
        saveFormDraft();
      });
    }

    function sampleSkillCall(skill) {
      const args = {};
      Object.keys(skill.parameters || {}).forEach(key => {
        const desc = String(skill.parameters[key] || '');
        if (desc.includes('YYYY-MM-DD')) args[key] = '2026-05-14';
        else if (desc.includes('数组')) args[key] = [];
        else if (key === 'kind') args[key] = 'weekly';
        else if (key === 'limit') args[key] = 20;
        else args[key] = desc.replace(/，可选/g, '') || '';
      });
      return JSON.stringify({
        reply: `准备调用 ${skill.title}`,
        skill_call: { name: skill.name, arguments: args }
      }, null, 2);
    }

    function skillFallback(name) {
      const module = name.split('.')[0] || '其他';
      return {
        name,
        module: module === 'weekly' ? '周报' : module,
        title: name,
        description: '系统 Skill 测试',
        parameters: {},
        safe: !/send|preview|generate|save|create|comment/.test(name)
      };
    }

    function skillDefaultArguments(skill) {
      const example = skill?.detail?.call_example?.skill_call?.arguments;
      if (example && typeof example === 'object') return example;
      const args = {};
      Object.keys(skill?.parameters || {}).forEach(key => {
        const desc = String(skill.parameters[key] || '');
        if (desc.includes('YYYY-MM-DD')) args[key] = '2026-05-14';
        else if (desc.includes('数组')) args[key] = [];
        else if (key === 'kind') args[key] = 'weekly';
        else if (key === 'limit') args[key] = 20;
        else if (key === 'uid') args[key] = '';
        else args[key] = desc.includes('可选') ? '' : desc;
      });
      return args;
    }

    function openSkillTest(name) {
      const skill = (state.skills || []).find(item => item.name === name) || skillFallback(name);
      state.currentSkill = skill;
      el('skillTestTitle').textContent = `${skill.name} 测试`;
      el('skillTestMeta').textContent = `${skill.module || '其他'} Skill · ${skill.title || ''} · ${skill.safe ? '查询/预览类' : '写入/外部动作类'}`;
      el('skillTestArgs').value = JSON.stringify(skillDefaultArguments(skill), null, 2);
      el('skillTestInstruction').value = '';
      el('skillConfirmUnsafe').checked = false;
      el('skillConfirmWrap').classList.toggle('hidden', !!skill.safe);
      el('skillTestStatus').textContent = '';
      el('skillTestResult').textContent = '点击“运行测试”后，这里会显示 Skill 返回结果。';
      el('skillTestLinks').innerHTML = '';
      el('skillTestModal').classList.remove('hidden');
      renderIcons(el('skillTestModal'));
    }

    function closeSkillTest() {
      el('skillTestModal').classList.add('hidden');
      state.currentSkill = null;
    }

    function attachSkillCardTests(root = document) {
      root.querySelectorAll('.skill-card[data-skill-name]').forEach(card => {
        if (card.dataset.testBound === 'true') return;
        card.dataset.testBound = 'true';
        card.addEventListener('click', () => openSkillTest(card.dataset.skillName));
      });
    }

    function renderSkillTestArtifacts(result) {
      const data = result?.result || {};
      const links = [];
      if (data.download_url) {
        links.push(`<a class="secondary" href="${escapeHtml(resourceUrl(data.download_url))}" target="_blank">打开生成文件</a>`);
      }
      if (data.preview_image_url) {
        links.push(`<img class="skill-preview-image" src="${escapeHtml(resourceUrl(data.preview_image_url))}" alt="Skill 预览图片" />`);
      }
      el('skillTestLinks').innerHTML = links.join('');
    }

    async function runSkillTest() {
      const skill = state.currentSkill;
      if (!skill) return;
      let args = {};
      try {
        args = JSON.parse(el('skillTestArgs').value || '{}');
      } catch (err) {
        el('skillTestStatus').textContent = '调用参数不是有效 JSON。';
        return;
      }
      el('skillRunTest').disabled = true;
      el('skillTestStatus').textContent = el('skillTestInstruction').value.trim() ? '正在调用平台配置的大模型 API 生成参数并执行 Skill...' : '正在执行 Skill 测试...';
      el('skillTestResult').textContent = '测试运行中...';
      el('skillTestLinks').innerHTML = '';
      try {
        const result = await api('/api/skill-test', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            name: skill.name,
            arguments: args,
            instruction: el('skillTestInstruction').value.trim(),
            confirm_unsafe: el('skillConfirmUnsafe').checked
          })
        });
        el('skillTestStatus').textContent = result.model ? `测试完成，已使用模型：${result.model}` : '测试完成。';
        el('skillTestResult').textContent = JSON.stringify(result, null, 2);
        renderSkillTestArtifacts(result);
      } catch (err) {
        el('skillTestStatus').textContent = err.message;
        el('skillTestResult').textContent = JSON.stringify({ ok: false, error: err.message }, null, 2);
      } finally {
        el('skillRunTest').disabled = false;
      }
    }

    function renderSkills(skills) {
      const moduleOrder = ['周报', '出差报告', '工作日记', '金点子论坛', '邮件', '资讯', '报告', '通用'];
      const moduleLabels = {
        周报: '周报 Skill',
        出差报告: '出差报告 Skill',
        工作日记: '日记 Skill',
        金点子论坛: '金点子论坛 Skill',
        邮件: '邮件 Skill',
        资讯: '资讯 Skill',
        报告: '报告 Skill',
        通用: '通用 Skill'
      };
      const foundModules = [...new Set((skills || []).map(item => item.module || '其他'))];
      const orderedModules = [
        ...moduleOrder.filter(module => foundModules.includes(module)),
        ...foundModules.filter(module => !moduleOrder.includes(module))
      ];
      const modules = ['all', ...orderedModules];
      const filter = el('skillModuleFilter');
      const previous = filter.value || 'all';
      filter.innerHTML = modules.map(module => `<option value="${escapeHtml(module)}">${module === 'all' ? '全部模块' : escapeHtml(module)}</option>`).join('');
      filter.value = modules.includes(previous) ? previous : 'all';
      const keyword = (el('skillSearch').value || '').trim().toLowerCase();
      const moduleName = filter.value || 'all';
      const counts = {};
      (skills || []).forEach(skill => {
        const module = skill.module || '其他';
        counts[module] = (counts[module] || 0) + 1;
      });
      el('skillModuleSummary').innerHTML = orderedModules.map(module => `
        <div class="skill-module-card ${moduleName === module ? 'active' : ''}" data-module="${escapeHtml(module)}">
          <div class="skill-module-name">${escapeHtml(moduleLabels[module] || (module + ' Skill'))}</div>
          <div class="skill-module-count">已安装 ${counts[module] || 0} 个能力，点击查看</div>
        </div>
      `).join('');
      el('skillModuleSummary').querySelectorAll('.skill-module-card').forEach(card => {
        card.addEventListener('click', () => {
          el('skillModuleFilter').value = card.dataset.module;
          renderSkills(state.skills || []);
        });
      });
      el('skillTotalCount').textContent = `共 ${(skills || []).length} 个 Skill`;
      const list = (skills || []).filter(skill => {
        const text = `${skill.name} ${skill.title} ${skill.module} ${skill.description}`.toLowerCase();
        return (moduleName === 'all' || skill.module === moduleName) && (!keyword || text.includes(keyword));
      });
      const summaryText = (text, max = 72) => {
        const compact = String(text || '').replace(/\s+/g, ' ').trim();
        return compact.length > max ? compact.slice(0, max) + '...' : compact;
      };
      el('skillList').innerHTML = list.length ? list.map(skill => `
        <div class="skill-card compact" data-skill-name="${escapeHtml(skill.name)}">
          <div class="skill-card-head">
            <div>
              <div class="skill-name">${escapeHtml(skill.name)}</div>
              <div class="skill-title">${escapeHtml(skill.module || '其他')} Skill · ${escapeHtml(skill.title || '')}</div>
            </div>
            <div class="skill-card-actions">
              <span class="skill-badge ${skill.safe ? '' : 'warn'}">${skill.safe ? '查询/预览' : '写入/外部动作'}</span>
              <button type="button" class="skill-help-btn" data-help="${escapeHtml(skill.name)}" aria-expanded="false">详情</button>
            </div>
          </div>
          <div class="skill-desc">${escapeHtml(summaryText(skill.description || '点击详情查看适用场景、参数和调用示例。'))}</div>
          <div class="skill-detail" id="skill-detail-${escapeHtml(skill.name)}">
            <div class="meta-label">说明</div>
            <div>${escapeHtml(skill.description || '')}</div>
            ${skill.detail && skill.detail.when_to_use && skill.detail.when_to_use.length ? `
              <div class="meta-label">适用场景</div>
              <div>${(skill.detail.when_to_use || []).map(item => `· ${escapeHtml(item)}`).join('<br>')}</div>
            ` : ''}
            <div class="meta-label">参数</div>
            <pre>${escapeHtml(JSON.stringify((skill.detail && skill.detail.input_schema) || skill.parameters || {}, null, 2))}</pre>
            ${skill.detail && skill.detail.output_schema ? `
              <div class="meta-label">输出结构</div>
              <pre>${escapeHtml(JSON.stringify(skill.detail.output_schema || {}, null, 2))}</pre>
            ` : ''}
            <div class="meta-label">调用示例</div>
            <pre>${escapeHtml(JSON.stringify((skill.detail && skill.detail.call_example) || {
              reply: `准备调用 ${skill.title}`,
              skill_call: { name: skill.name, arguments: {} }
            }, null, 2))}</pre>
          </div>
        </div>
      `).join('') : '<div class="upload-item">没有匹配的 Skill。</div>';
      attachSkillCardTests(el('skillList'));
      el('skillList').querySelectorAll('.skill-help-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
          e.stopPropagation();
          const detail = el(`skill-detail-${btn.dataset.help}`);
          if (!detail) return;
          const open = detail.classList.toggle('open');
          btn.setAttribute('aria-expanded', open ? 'true' : 'false');
          btn.textContent = open ? '收起' : '详情';
        });
      });
    }

    async function loadSkills() {
      if (!state.user?.is_superadmin) return;
      el('skillList').innerHTML = '<div class="upload-item">正在读取系统 Skill...</div>';
      try {
        const data = await api('/api/skills');
        state.skills = data.skills || [];
        renderSkills(state.skills);
      } catch (err) {
        el('skillList').innerHTML = `<div class="upload-item">${escapeHtml(err.message)}</div>`;
      }
    }

    async function loadReports(options = {}) {
      const data = await api('/api/reports');
      state.reports = data.reports;
      window.latestWeekly = data.latest_weekly;
      window.latestTrip = data.latest_trip;
      const task = state.task || 'weekly';
      if (!options.preserveSelection) {
        state.selected = task === 'weekly' ? data.latest_weekly : data.latest_trip;
        el('mailKind').value = task;
      }
      setTask(task);
      renderReports();
      renderHistoryReports();
      if (!options.preserveSelection && state.selected) {
        await loadDraft(task, state.selected);
      }
    }

    async function loadAdminConfig() {
      if (!state.user?.is_admin) return;
      const data = await api('/api/admin-config');
      el('configApiUrl').value = data.assistant_api_url || '';
      el('configModel').value = data.assistant_model || 'MiniMax-M2.7';
      renderModelOptions([data.assistant_model || 'MiniMax-M2.7'], data.assistant_model || 'MiniMax-M2.7');
      el('configPrompt').value = data.assistant_prompt || defaultAssistantPrompt;
      el('configApiKey').value = '';
      el('configKeyHint').textContent = 'API Key 状态：' + (data.assistant_api_key_masked || '未配置');
      el('configSmtpHost').value = data.smtp_host || 'smtp.263.net';
      el('configSmtpPort').value = data.smtp_port || 465;
      el('configSmtpTls').checked = !!data.smtp_tls;
      el('configSmtpSsl').checked = !!data.smtp_ssl;
      el('configImapHost').value = data.imap_host || 'imap.263.net';
      el('configImapPort').value = data.imap_port || 993;
      el('configImapSsl').checked = !!data.imap_ssl;
    }
    async function loadUserManage() {
      console.log('loadUserManage called, is_superadmin:', state.user?.is_superadmin);
      if (!state.user?.is_superadmin) { console.log('loadUserManage skipped: not superadmin'); return; }
      el('newUserRoleBox').style.display = 'grid';
      await loadUserList();
    }
    async function loadUserList() {
      if (!state.user?.is_admin) { console.log('loadUserList skipped: not admin'); return; }
      try {
        const data = await api('/api/admin-users-list');
        console.log('loadUserList success, users count:', (data.users || []).length);
        renderUsers(data.users || []);
      } catch (err) {
        console.error('loadUserList error:', err);
        el('userList').innerHTML = '<div class="upload-item">加载用户列表失败: ' + escapeHtml(err.message) + '</div>';
      }
    }

    async function loadMailConfig() {
      const data = await api('/api/mail-config');
      const ref = data.reference || {};
      const setVal = (id, val, refVal) => {
        const node = el(id);
        if (!node) return;
        node.value = val || '';
        node.placeholder = refVal || '';
      };
      setVal('mailUserEmail', data.user_email, ref.user_email);
      setVal('mailSmtpFrom', data.smtp_from, ref.smtp_from);
      setVal('mailSmtpUser', data.smtp_user, ref.smtp_user);
      el('mailSmtpPassword').value = '';
      el('mailPasswordHint').textContent = 'SMTP 密码/授权码状态：' + (data.smtp_password_masked || '未配置');
      setVal('mailImapUser', data.imap_user, ref.imap_user);
      el('mailImapPassword').value = '';
      el('mailImapPasswordHint').textContent = 'IMAP 密码/授权码状态：' + (data.imap_password_masked || '未配置');
      setVal('mailWeeklyTo', data.weekly_to, ref.weekly_to);
      setVal('mailWeeklyCc', data.weekly_cc, ref.weekly_cc);
      setVal('mailTripTo', data.trip_to, ref.trip_to);
      setVal('mailTripCc', data.trip_cc, ref.trip_cc);
      el('mailEmailSignature').value = data.email_signature || '';
      // 显示全局服务器配置
      el('mailSmtpHostDisplay').textContent = data.smtp_host || 'smtp.263.net';
      el('mailSmtpPortDisplay').textContent = (data.smtp_port || 465) + ' / ' + (data.smtp_ssl ? 'SSL' : 'TLS');
      el('mailImapHostDisplay').textContent = data.imap_host || 'imap.263.net';
      el('mailImapPortDisplay').textContent = (data.imap_port || 993) + ' / ' + (data.imap_ssl ? 'SSL' : 'TLS');
    }

    function mailConfigPayload() {
      const userEmail = el('mailUserEmail').value.trim();
      const smtpUser = el('mailSmtpUser').value.trim() || userEmail;
      return {
        user_email: userEmail,
        smtp_from: el('mailSmtpFrom').value.trim() || userEmail,
        smtp_user: smtpUser,
        smtp_password: el('mailSmtpPassword').value,
        imap_user: el('mailImapUser').value.trim() || smtpUser,
        imap_password: el('mailImapPassword').value,
        weekly_to: el('mailWeeklyTo').value,
        weekly_cc: el('mailWeeklyCc').value,
        trip_to: el('mailTripTo').value,
        trip_cc: el('mailTripCc').value,
        email_signature: el('mailEmailSignature').value
      };
    }

    function explainMailLoginError(message) {
      const text = String(message || '邮箱测试失败');
      if (text.includes('SMTP 用户名')) return text + ' 请填写完整邮箱地址；留空保存时系统会自动使用“本人邮箱”。';
      if (text.includes('SMTP 授权码') || text.includes('SMTP 密码')) return text + ' 请填写邮箱后台生成的 SMTP 授权码，不是网页登录密码。';
      if (text.includes('IMAP 用户名')) return text + ' 如需读取收件箱，IMAP 用户名通常与 SMTP 用户名相同。';
      if (text.includes('IMAP 授权码') || text.includes('IMAP 密码')) return text + ' 如需读取收件箱，可复用邮箱授权码或单独生成 IMAP 授权码。';
      if (text.includes('timed out') || text.includes('超时')) return text + ' 请检查服务器、端口和 SSL 设置是否匹配。263 邮箱通常是 SMTP 465/SSL。';
      return text;
    }

    function textToHtml(text) {
      return escapeHtml(text || '').split('\n').join('<br>');
    }

    function renderBodyPreview() {
      if (state.bodyHtml) {
        el('bodyPreview').innerHTML = state.bodyHtml;
      } else {
        el('bodyPreview').innerHTML = textToHtml(el('body').value || '暂无正文内容');
      }
    }

    function renderModelOptions(models, selected) {
      const unique = [...new Set((models || []).filter(Boolean))];
      if (!unique.includes(selected) && selected) unique.unshift(selected);
      el('configModelSelect').innerHTML = unique.map(model => `
        <option value="${escapeHtml(model)}" ${model === selected ? 'selected' : ''}>${escapeHtml(model)}</option>
      `).join('');
    }

    function renderUsers(users) {
      const roleLabel = (role) => {
        if (role === 'superadmin') return '超级管理员';
        if (role === 'admin') return '管理员';
        return '普通成员';
      };
      const isSuper = state.user?.is_superadmin;
      const isAdmin = state.user?.is_admin;
      console.log('renderUsers called, isSuper:', isSuper, 'users count:', (users || []).length);
      el('userList').innerHTML = (users || []).map((user, idx) => {
        const canEdit = isSuper;
        const canDelete = isSuper && user.username !== state.user?.username;
        const roleSelect = canEdit
          ? `<select class="user-role-select mini" data-user="${escapeHtml(user.username)}" style="margin-right:8px;">
              <option value="member" ${user.role === 'member' ? 'selected' : ''}>普通成员</option>
              <option value="admin" ${user.role === 'admin' ? 'selected' : ''}>管理员</option>
              <option value="superadmin" ${user.role === 'superadmin' ? 'selected' : ''}>超级管理员</option>
            </select>`
          : `<span class="mini" style="margin-right:8px;color:var(--muted);">${roleLabel(user.role)}</span>`;
        const editBtn = canEdit
          ? `<button class="mini secondary edit-user-toggle" data-user="${escapeHtml(user.username)}" data-idx="${idx}" type="button" style="margin-right:8px;">编辑</button>`
          : '';
        const deleteBtn = canDelete
          ? `<button class="mini danger delete-user" data-user="${escapeHtml(user.username)}" type="button">删除</button>`
          : '';
        const editForm = canEdit ? `
          <div class="user-edit-form hidden" id="userEdit_${idx}" style="grid-column:1/-1;margin-top:8px;padding-top:10px;border-top:1px solid var(--line);">
            <div class="config-grid">
              <div>
                <label style="margin-top:0;">显示名称</label>
                <input class="edit-name" data-user="${escapeHtml(user.username)}" value="${escapeHtml(user.name || '')}" placeholder="${escapeHtml(user.username)}" />
              </div>
              <div>
                <label style="margin-top:0;">重置密码（留空则不修改）</label>
                <input class="edit-password" data-user="${escapeHtml(user.username)}" type="password" placeholder="不修改则留空" />
              </div>
            </div>
            <div class="toolbar" style="margin-top:10px;">
              <button class="mini save-user-edit" data-user="${escapeHtml(user.username)}" data-idx="${idx}" type="button">保存修改</button>
              <button class="mini secondary cancel-user-edit" data-idx="${idx}" type="button">取消</button>
            </div>
          </div>
        ` : '';
        return `
        <div class="user-item" style="display:grid;grid-template-columns:minmax(0,1fr) auto auto;gap:10px;align-items:center;" data-idx="${idx}">
          <div>
            <strong>${escapeHtml(user.name || user.username)}</strong>
            <div class="history-meta">${escapeHtml(user.username)} · ${roleLabel(user.role)}</div>
          </div>
          <div style="display:flex;align-items:center;">${roleSelect}${editBtn}${deleteBtn}</div>
          ${editForm}
        </div>
      `}).join('') || '<div class="upload-item">暂无用户。</div>';
      // 绑定删除按钮
      el('userList').querySelectorAll('.delete-user').forEach(btn => {
        btn.addEventListener('click', async () => {
          const username = btn.dataset.user;
          if (!confirm(`确定删除用户 ${username} 吗？`)) return;
          try {
            const result = await apiPost('/api/admin-users-delete', { username });
            renderUsers(result.users || []);
            el('userManageStatus').textContent = '用户已删除';
            el('userManageStatus').className = 'status ok';
          } catch (err) {
            el('userManageStatus').textContent = err.message;
            el('userManageStatus').className = 'status err';
          }
        });
      });
      // 绑定角色修改
      if (isSuper) {
        el('userList').querySelectorAll('.user-role-select').forEach(sel => {
          sel.addEventListener('change', async () => {
            const username = sel.dataset.user;
            const newRole = sel.value;
            try {
              const result = await apiPost('/api/admin-users-update', { username, role: newRole });
              renderUsers(result.users || []);
              el('userManageStatus').textContent = '权限已更新';
              el('userManageStatus').className = 'status ok';
            } catch (err) {
              el('userManageStatus').textContent = err.message;
              el('userManageStatus').className = 'status err';
              await loadUserList();
            }
          });
        });
      }
      // 绑定编辑展开/收起
      el('userList').querySelectorAll('.edit-user-toggle').forEach(btn => {
        btn.addEventListener('click', () => {
          const idx = btn.dataset.idx;
          const form = el('userEdit_' + idx);
          if (form) {
            const wasHidden = form.classList.contains('hidden');
            // 先关闭所有编辑表单
            el('userList').querySelectorAll('.user-edit-form').forEach(f => f.classList.add('hidden'));
            el('userList').querySelectorAll('.edit-user-toggle').forEach(b => b.textContent = '编辑');
            if (wasHidden) {
              form.classList.remove('hidden');
              btn.textContent = '收起';
            }
          }
        });
      });
      // 绑定取消编辑
      el('userList').querySelectorAll('.cancel-user-edit').forEach(btn => {
        btn.addEventListener('click', () => {
          const idx = btn.dataset.idx;
          const form = el('userEdit_' + idx);
          if (form) {
            form.classList.add('hidden');
            const toggle = el('userList').querySelector(`.edit-user-toggle[data-idx="${idx}"]`);
            if (toggle) toggle.textContent = '编辑';
          }
        });
      });
      // 绑定保存编辑
      el('userList').querySelectorAll('.save-user-edit').forEach(btn => {
        btn.addEventListener('click', async () => {
          const username = btn.dataset.user;
          const idx = btn.dataset.idx;
          const row = el('userList').querySelector(`.user-item[data-idx="${idx}"]`);
          const name = row?.querySelector('.edit-name')?.value?.trim() || '';
          const password = row?.querySelector('.edit-password')?.value?.trim() || '';
          const payload = { username };
          if (name) payload.name = name;
          if (password) payload.password = password;
          try {
            const result = await apiPost('/api/admin-users-update', payload);
            renderUsers(result.users || []);
            el('userManageStatus').textContent = '用户信息已更新';
            el('userManageStatus').className = 'status ok';
          } catch (err) {
            el('userManageStatus').textContent = err.message;
            el('userManageStatus').className = 'status err';
          }
        });
      });
    }

    function renderMailbox(messages) {
      const box = el('mailboxList');
      box.innerHTML = (messages || []).length ? messages.map(item => `
        <div class="mailbox-item" data-uid="${escapeHtml(item.uid)}">
          <div class="mailbox-subject">${escapeHtml(item.subject || '无主题')}</div>
          <div class="mailbox-meta">${escapeHtml(item.from || '未知发件人')}</div>
          <div class="mailbox-meta">${escapeHtml(item.date || '')}</div>
          ${(item.attachments || []).length ? `<div class="mailbox-meta">${(item.attachments || []).length} 个附件</div>` : ''}
          <div class="mailbox-preview">${escapeHtml(item.preview || '暂无正文预览')}</div>
        </div>
      `).join('') : '<div class="upload-item">暂无邮件，或当前邮箱没有可读取的收件箱邮件。</div>';
      box.querySelectorAll('.mailbox-item').forEach(item => {
        item.addEventListener('click', () => loadMailDetail(item.dataset.uid));
      });
    }

    async function loadMailbox(forceRefresh = false) {
      if (!el('mailboxList')) return;
      el('mailboxList').innerHTML = `<div class="upload-item">${forceRefresh ? '正在刷新收件箱...' : '正在读取收件箱缓存...'}</div>`;
      el('mailDetail').textContent = '请选择左侧邮件查看详情。';
      try {
        const query = new URLSearchParams({ limit: el('mailboxLimit').value || '20' });
        if (forceRefresh) query.set('refresh', '1');
        const data = await api('/api/mailbox?' + query.toString());
        renderMailbox(data.messages || []);
        if (data.cached) {
          el('mailDetail').textContent = '已从本地缓存加载。需要最新邮件时点击“刷新”。';
        }
      } catch (err) {
        el('mailboxList').innerHTML = `<div class="upload-item">${escapeHtml(err.message)}</div>`;
      }
    }

    async function loadMailDetail(uid) {
      if (!uid) return;
      document.querySelectorAll('.mailbox-item').forEach(item => item.classList.toggle('active', item.dataset.uid === uid));
      el('mailDetail').textContent = '正在读取邮件详情...';
      try {
        const query = new URLSearchParams({ uid });
        const data = await api('/api/mailbox-detail?' + query.toString());
        const msg = data.message || {};
        const attachments = msg.attachments || [];
        const bodyHtml = msg.body_html
          ? `<div class="mail-detail-body">${msg.body_html}</div>`
          : `<div class="mail-detail-body plain">${escapeHtml(msg.body || msg.preview || '暂无可读取的文本正文')}</div>`;
        el('mailDetail').innerHTML = `
          <div class="mail-detail-head">
            <div class="mailbox-subject">${escapeHtml(msg.subject || '无主题')}</div>
            <div class="mailbox-meta">发件人：${escapeHtml(msg.from || '')}</div>
            <div class="mailbox-meta">收件人：${escapeHtml(msg.to || '')}</div>
            <div class="mailbox-meta">时间：${escapeHtml(msg.date || '')}</div>
            <div class="mail-attachment-list">
              ${attachments.length ? attachments.map(file => `
                <span class="mail-attachment">
                  <span class="icon" data-icon="paperclip"></span>
                  ${escapeHtml(file.name || '附件')}
                  ${file.size ? ` · ${formatFileSize(file.size)}` : ''}
                </span>
              `).join('') : '<span class="mailbox-meta">无附件</span>'}
            </div>
          </div>
          ${bodyHtml}
        `;
        renderIcons(el('mailDetail'));
      } catch (err) {
        el('mailDetail').textContent = err.message;
      }
    }

    function formatFileSize(bytes) {
      const size = Number(bytes || 0);
      if (size < 1024) return size + ' B';
      if (size < 1024 * 1024) return (size / 1024).toFixed(1) + ' KB';
      return (size / 1024 / 1024).toFixed(1) + ' MB';
    }

    function renderAssistantMailFiles() {
      const box = el('assistantMailFileList');
      box.innerHTML = state.assistantMailFiles.length ? state.assistantMailFiles.map((file, index) => `
        <div class="mail-file-item">
          <span>${escapeHtml(file.name)} · ${formatFileSize(file.size)}</span>
          <button class="mini secondary remove-assistant-file" type="button" data-index="${index}">移除</button>
        </div>
      `).join('') : '<div class="mailbox-meta">未添加附件</div>';
      box.querySelectorAll('.remove-assistant-file').forEach(button => {
        button.addEventListener('click', () => {
          state.assistantMailFiles.splice(Number(button.dataset.index), 1);
          renderAssistantMailFiles();
        });
      });
    }

    function renderAssistantMailPreview() {
      el('assistantMailPreview').innerHTML = textToHtml(el('assistantMailBody').value || '暂无正文内容');
    }

    function clearAssistantMail() {
      el('assistantMailTo').value = '';
      el('assistantMailCc').value = '';
      el('assistantMailSubject').value = '';
      el('assistantMailBody').value = '';
      el('assistantMailFiles').value = '';
      state.assistantMailFiles = [];
      renderAssistantMailFiles();
      renderAssistantMailPreview();
      el('assistantMailStatus').textContent = '';
      el('assistantMailStatus').className = 'status';
    }

    function adminConfigPayload() {
      return {
        assistant_api_url: el('configApiUrl').value,
        assistant_api_key: el('configApiKey').value,
        assistant_model: el('configModel').value || el('configModelSelect').value,
        assistant_prompt: el('configPrompt').value,
      };
    }

    async function boot() {
      renderIcons();
      try {
        const session = await api('/api/session');
        defaultAssistantPrompt = session.assistant_prompt || defaultAssistantPrompt;
        if (session.authenticated) {
          applyUser(session.user);
          await loadReports();
        } else {
          applyUser(null);
        }
      } catch (err) {
        applyUser(null);
        el('loginStatus').textContent = err.message;
        el('loginStatus').className = 'status err';
      }
    }

    async function loadDraft(kind, name) {
      state.selected = name;
      renderReports();
      const query = new URLSearchParams({ kind, file: name || '' });
      const draft = await api('/api/draft?' + query.toString());
      el('to').value = draft.to || '';
      el('cc').value = draft.cc || '';
      el('subject').value = draft.subject || '';
      el('body').value = draft.body || '';
      state.bodyHtml = draft.body_html || '';
      renderBodyPreview();
      el('attachment').value = draft.attachment || '';
      if (draft.download_url) {
        el('downloadLink').href = resourceUrl(draft.download_url);
        el('downloadLink').classList.remove('hidden');
      } else {
        el('downloadLink').classList.add('hidden');
      }
      el('preview').innerHTML = draft.preview_html || textToHtml(draft.preview || '暂无可预览内容');
      el('status').textContent = '';
      el('status').className = 'status';
      if (kind === 'weekly' && !state.weeklyPrefilled) {
        await loadWeeklyPrefill();
      }
      if (kind === 'trip' && !state.tripPrefilled) {
        await loadTripPrefill();
      }
    }

    async function loadWeeklyPrefill(force = false) {
      if (!force && state.weeklyPrefilled) return;
      if (force) clearSavedFormDraft('weekly');
      setDefaultWeeklyDates();
      const prefill = await api('/api/weekly-prefill');
      renderWorkRows('summary', prefill.summary_rows || []);
      renderWorkRows('follow', prefill.follow_rows || []);
      renderWorkRows('next', prefill.next_rows || []);
      state.weeklyPrefilled = true;
      const restored = force ? false : restoreSavedFormDraft('weekly');
      if (prefill.source) {
        el('status').textContent = restored ? '已恢复上次未生成的周报草稿。' : `已获取最新历史周报：${prefill.source}。上次“下周计划”已写入本次“本周工作内容”，重点工作已复制，下周计划保持为空。`;
        el('status').className = 'status ok';
      } else {
        el('status').textContent = '没有找到可用于预填的历史周报。';
        el('status').className = 'status err';
      }
      saveFormDraft();
    }

    async function loadTripPrefill(force = false) {
      if (!force && state.tripPrefilled) return;
      if (force) clearSavedFormDraft('trip');
      const prefill = await api('/api/trip-prefill');
      const today = new Date();
      const fmt = d => d.getFullYear() + '-' + String(d.getMonth()+1).padStart(2,'0') + '-' + String(d.getDate()).padStart(2,'0');
      const defaultStart = fmt(today);
      const defaultEnd = fmt(new Date(today.getTime() + 2*24*60*60*1000));
      el('tripReporter').value = prefill.reporter || '周颖超';
      el('tripDepartment').value = prefill.department || '场景研究院';
      el('tripLocation').value = prefill.location || '';
      el('tripStart').value = prefill.trip_start || defaultStart;
      el('tripEnd').value = prefill.trip_end || defaultEnd;
      el('tripPurpose').value = prefill.purpose || '';
      el('tripItinerary').value = prefill.itinerary || '';
      el('tripDetails').value = prefill.details || '';
      el('tripIssues').value = prefill.issues || '';
      el('tripSuggestions').value = prefill.suggestions || '';
      renderTripCards();
      state.tripPrefilled = true;
      const restored = force ? false : restoreSavedFormDraft('trip');
      if (prefill.source) {
        el('status').textContent = restored ? '已恢复上次未生成的出差报告草稿。' : `已获取最新历史出差报告：${prefill.source}，并自动填入当前模板。`;
        el('status').className = 'status ok';
      } else {
        el('status').textContent = '没有找到可用于预填的历史出差报告。';
        el('status').className = 'status err';
      }
      saveFormDraft();
    }

    el('mailKind').addEventListener('change', async () => {
      const kind = el('mailKind').value;
      const generated = state.reports.find(r => r.kind === kind && r.generated);
      const latest = generated?.name || (kind === 'weekly' ? window.latestWeekly : window.latestTrip);
      await loadDraft(kind, latest || '');
    });

    async function loadAgentOrchestration() {
      const panel = el('agentOrchestrationPanel');
      const content = el('agentOrchestrationContent');
      if (!panel.classList.contains('hidden')) {
        panel.classList.add('hidden');
        return;
      }
      content.innerHTML = '<div class="upload-item">正在加载编排逻辑...</div>';
      panel.classList.remove('hidden');
      try {
        const data = await api('/api/agent-orchestration');
        if (!data.ok) throw new Error(data.error || '加载失败');
        const agents = data.agents || {};
        const workflows = data.workflows || {};
        const skills = data.skills || [];
        let html = '';
        html += '<div class="orchestration-section"><div class="orchestration-section-title">🧠 犇犇角色定义与系统提示词</div>';
        Object.entries(agents).forEach(([key, val]) => {
          const label = { weekly: '周报助手', trip: '出差报告助手', diary: '日记助手', mailassistant: '邮件助手', news: '资讯助手', forum: '论坛助手', dashboard: '总助手' }[key] || key;
          html += `<div style="margin-bottom:8px;font-size:12px;font-weight:700;color:#475569;">${label}</div><pre>${escapeHtml(val)}</pre>`;
        });
        html += '</div>';
        html += `<div class="orchestration-section"><div class="orchestration-section-title">🔄 Skill 模式追加提示词</div><pre>${escapeHtml(data.skill_mode_suffix || '')}</pre></div>`;
        html += '<div class="orchestration-section"><div class="orchestration-section-title">📋 工作流编排</div>';
        Object.entries(workflows).forEach(([key, val]) => {
          const label = { weekly: '周报', trip: '出差报告', diary: '工作日记', mailassistant: '邮件', news: '资讯', forum: '金点子论坛' }[key] || key;
          html += `<div style="margin-bottom:6px;font-size:12px;"><strong>${label}：</strong>${escapeHtml(val)}</div>`;
        });
        html += '</div>';
        html += `<div class="orchestration-section"><div class="orchestration-section-title">🛠 可用 Skill 列表</div><pre>${escapeHtml(JSON.stringify(skills.map(s => ({ name: s.name, module: s.module, title: s.title, safe: s.safe })), null, 2))}</pre></div>`;
        content.innerHTML = html;
      } catch (err) {
        content.innerHTML = `<div class="upload-item">${escapeHtml(err.message)}</div>`;
      }
    }
    let agentConfigData = {};
    function openAgentConfigModal() {
      el('agentConfigModal').classList.remove('hidden');
      loadAgentConfigEditor();
    }
    function closeAgentConfigModal() {
      el('agentConfigModal').classList.add('hidden');
    }
    async function loadAgentConfigEditor() {
      el('agentConfigStatus').textContent = '正在加载...';
      try {
        const data = await api('/api/agent-config');
        if (!data.ok) throw new Error(data.error || '加载失败');
        agentConfigData = data.config || {};
        const prompts = agentConfigData.prompts || {};
        const workflows = agentConfigData.workflows || {};
        const labels = { weekly: '周报助手', trip: '出差报告助手', diary: '日记助手', mailassistant: '邮件助手', news: '资讯助手', forum: '论坛助手', dashboard: '总助手' };
        let pHtml = '';
        Object.entries(labels).forEach(([key, label]) => {
          pHtml += `<div style="margin-bottom:10px;"><label style="font-size:12px;font-weight:700;color:#475569;">${label}</label><textarea id="agentPrompt-${key}" rows="6" spellcheck="false" style="width:100%;margin-top:4px;font-size:12px;">${escapeHtml(prompts[key] || '')}</textarea></div>`;
        });
        el('agentConfigPrompts').innerHTML = pHtml;
        let wHtml = '';
        Object.entries(labels).forEach(([key, label]) => {
          if (key === 'dashboard') return;
          wHtml += `<div style="margin-bottom:10px;"><label style="font-size:12px;font-weight:700;color:#475569;">${label}</label><textarea id="agentWorkflow-${key}" rows="3" spellcheck="false" style="width:100%;margin-top:4px;font-size:12px;">${escapeHtml(workflows[key] || '')}</textarea></div>`;
        });
        el('agentConfigWorkflows').innerHTML = wHtml;
        el('agentConfigStatus').textContent = '';
      } catch (err) {
        el('agentConfigStatus').textContent = err.message;
      }
    }
    async function saveAgentConfig() {
      el('agentConfigStatus').textContent = '保存中...';
      const prompts = {};
      const workflows = {};
      const keys = ['weekly','trip','diary','mailassistant','news','forum','dashboard'];
      keys.forEach(key => {
        const ta = el(`agentPrompt-${key}`);
        if (ta && ta.value.trim()) prompts[key] = ta.value.trim();
      });
      ['weekly','trip','diary','mailassistant','news','forum'].forEach(key => {
        const ta = el(`agentWorkflow-${key}`);
        if (ta && ta.value.trim()) workflows[key] = ta.value.trim();
      });
      try {
        const result = await api('/api/agent-config', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ prompts, workflows })
        });
        if (!result.ok) throw new Error(result.error || '保存失败');
        el('agentConfigStatus').textContent = result.message || '保存成功';
      } catch (err) {
        el('agentConfigStatus').textContent = err.message;
      }
    }
    if (el('openAgentOrchestration')) el('openAgentOrchestration').addEventListener('click', loadAgentOrchestration);
    if (el('openAgentConfig')) el('openAgentConfig').addEventListener('click', openAgentConfigModal);
    if (el('agentConfigClose')) el('agentConfigClose').addEventListener('click', closeAgentConfigModal);
    if (el('agentConfigModal')) el('agentConfigModal').addEventListener('click', event => { if (event.target === el('agentConfigModal')) closeAgentConfigModal(); });
    if (el('agentConfigSave')) el('agentConfigSave').addEventListener('click', saveAgentConfig);
    document.querySelectorAll('.agent-config-tab').forEach(tab => {
      tab.addEventListener('click', () => {
        document.querySelectorAll('.agent-config-tab').forEach(t => t.classList.remove('active'));
        tab.classList.add('active');
        const name = tab.dataset.tab;
        el('agentConfigPrompts').classList.toggle('hidden', name !== 'prompts');
        el('agentConfigWorkflows').classList.toggle('hidden', name !== 'workflows');
      });
    });
    el('openSkillDocs').addEventListener('click', () => window.open('/skill-docs', '_blank'));
    el('downloadSkillDocs').addEventListener('click', () => window.open(resourceUrl('/download-skill-doc'), '_blank'));
    el('skillSearch').addEventListener('input', () => renderSkills(state.skills || []));
    el('skillModuleFilter').addEventListener('change', () => renderSkills(state.skills || []));
    el('skillTestClose').addEventListener('click', closeSkillTest);
    el('skillRunTest').addEventListener('click', runSkillTest);
    el('skillTestModal').addEventListener('click', event => {
      if (event.target === el('skillTestModal')) closeSkillTest();
    });
    attachSkillCardTests(el('skillsPanel'));

    el('refreshMailbox').addEventListener('click', () => loadMailbox(true));
    el('mailboxLimit').addEventListener('change', loadMailbox);
    el('assistantMailBody').addEventListener('input', renderAssistantMailPreview);
    el('assistantMailFiles').addEventListener('change', () => {
      state.assistantMailFiles = [...el('assistantMailFiles').files].map(file => ({
        file,
        name: file.name,
        size: file.size,
        type: file.type || 'application/octet-stream'
      }));
      renderAssistantMailFiles();
    });
    el('clearAssistantMail').addEventListener('click', clearAssistantMail);
    el('sendAssistantMail').addEventListener('click', async () => {
      el('assistantMailStatus').textContent = '正在发送邮件...';
      el('assistantMailStatus').className = 'status';
      try {
        const attachments = [];
        for (const item of state.assistantMailFiles) {
          attachments.push({
            name: item.name,
            type: item.type,
            content: await readFileAsBase64(item.file)
          });
        }
        const result = await api('/api/mail-send', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            to: el('assistantMailTo').value,
            cc: el('assistantMailCc').value,
            subject: el('assistantMailSubject').value,
            body: el('assistantMailBody').value,
            attachments
          })
        });
        el('assistantMailStatus').textContent = result.message || '邮件已发送。';
        el('assistantMailStatus').className = 'status ok';
      } catch (err) {
        el('assistantMailStatus').textContent = err.message;
        el('assistantMailStatus').className = 'status err';
      }
    });

    el('generate').addEventListener('click', async () => {
      const kind = el('kind').value;
      if (!['weekly', 'trip'].includes(kind) || !['weekly', 'trip'].includes(state.task)) {
        el('generateToolbar').classList.add('hidden');
        return;
      }
      syncWeeklyPeriod();
      el('status').textContent = '正在按模板生成文件...';
      el('status').className = 'status';
      const payload = kind === 'weekly' ? {
        kind,
        period: el('weeklyPeriod').value,
        weekly_summary: collectWorkRows('summary'),
        weekly_follow: collectWorkRows('follow'),
        weekly_next: collectWorkRows('next')
      } : {
        kind,
        reporter: el('tripReporter').value,
        department: el('tripDepartment').value,
        location: el('tripLocation').value,
        trip_start: el('tripStart').value,
        trip_end: el('tripEnd').value,
        purpose: el('tripPurpose').value,
        itinerary: el('tripItinerary').value,
        details: el('tripDetails').value,
        issues: el('tripIssues').value,
        suggestions: el('tripSuggestions').value
      };
      try {
        const result = await api('/api/generate', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        clearSavedFormDraft(kind);
        await loadReports();
        el('kind').value = kind;
        await loadDraft(kind, result.file);
        el('status').textContent = '已生成标准文件，并设为当前邮件附件：' + result.file;
        el('status').className = 'status ok';
      } catch (err) {
        el('status').textContent = err.message;
        el('status').className = 'status err';
      }
    });

    document.querySelectorAll('.task-card').forEach(card => {
      card.addEventListener('click', async () => {
        const task = card.dataset.task;
        state.subTab = 'edit';
        setTask(task);
        if (task === 'weekly') {
          await loadWeeklyPrefill();
          const generated = state.reports.find(r => r.kind === 'weekly' && r.generated);
          const latest = generated?.name || window.latestWeekly;
          await loadDraft('weekly', latest || '');
        } else if (task === 'trip') {
          await loadTripPrefill();
          const generated = state.reports.find(r => r.kind === 'trip' && r.generated);
          const latest = generated?.name || window.latestTrip;
          await loadDraft('trip', latest || '');
        } else if (task === 'mailconfig') {
          loadMailConfig();
        } else if (task === 'mailassistant') {
          loadMailbox();
        } else if (task === 'config') {
          await loadAdminConfig();
        } else if (task === 'skills') {
          await loadSkills();
        } else if (task === 'usermanage') {
          await loadUserManage();
        }
      });
    });

    document.querySelectorAll('.sub-tab').forEach(tab => {
      tab.addEventListener('click', () => {
        setSubTab(tab.dataset.sub);
      });
    });

    el('loginButton').addEventListener('click', async () => {
      el('loginStatus').textContent = '正在登录...';
      el('loginStatus').className = 'status';
      try {
        const result = await api('/api/login', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ username: el('loginUser').value, password: el('loginPass').value })
        });
        defaultAssistantPrompt = result.assistant_prompt || defaultAssistantPrompt;
        applyUser(result.user);
        await loadReports();
      } catch (err) {
        el('loginStatus').textContent = err.message;
        el('loginStatus').className = 'status err';
      }
    });

    el('changePassButton').addEventListener('click', () => {
      el('passOld').value = '';
      el('passNew').value = '';
      el('passConfirm').value = '';
      el('passStatus').textContent = '';
      el('passModal').classList.remove('hidden');
    });
    el('passSave').addEventListener('click', async () => {
      const oldPass = el('passOld').value;
      const newPass = el('passNew').value;
      const confirm = el('passConfirm').value;
      if (!oldPass || !newPass) {
        el('passStatus').textContent = '请填写原密码和新密码';
        el('passStatus').className = 'status err';
        return;
      }
      if (newPass.length < 4) {
        el('passStatus').textContent = '新密码至少 4 位';
        el('passStatus').className = 'status err';
        return;
      }
      if (newPass !== confirm) {
        el('passStatus').textContent = '两次输入的新密码不一致';
        el('passStatus').className = 'status err';
        return;
      }
      try {
        await apiPost('/api/change-password', { old_password: oldPass, new_password: newPass });
        el('passStatus').textContent = '密码修改成功，请重新登录';
        el('passStatus').className = 'status ok';
        setTimeout(() => { el('passModal').classList.add('hidden'); }, 1500);
      } catch (err) {
        el('passStatus').textContent = err.message;
        el('passStatus').className = 'status err';
      }
    });
    el('logoutButton').addEventListener('click', async () => {
      await api('/api/logout', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' });
      applyUser(null);
    });

    el('saveConfig').addEventListener('click', async () => {
      el('status').textContent = '正在保存系统配置...';
      el('status').className = 'status';
      try {
        const result = await api('/api/admin-config', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(adminConfigPayload())
        });
        defaultAssistantPrompt = result.config.assistant_prompt || defaultAssistantPrompt;
        el('configApiKey').value = '';
        el('configKeyHint').textContent = 'API Key 状态：' + (result.config.assistant_api_key_masked || '未配置');
        el('status').textContent = '系统配置已保存。';
        el('status').className = 'status ok';
      } catch (err) {
        el('status').textContent = err.message;
        el('status').className = 'status err';
      }
    });

    el('saveServerConfig').addEventListener('click', async () => {
      el('configServerStatus').textContent = '正在保存邮件服务器配置...';
      el('configServerStatus').className = 'status';
      try {
        await apiPost('/api/server-config', {
          smtp_host: el('configSmtpHost').value,
          smtp_port: el('configSmtpPort').value,
          smtp_tls: el('configSmtpTls').checked,
          smtp_ssl: el('configSmtpSsl').checked,
          imap_host: el('configImapHost').value,
          imap_port: el('configImapPort').value,
          imap_ssl: el('configImapSsl').checked,
        });
        el('configServerStatus').textContent = '邮件服务器配置已保存（对所有用户生效）。';
        el('configServerStatus').className = 'status ok';
      } catch (err) {
        el('configServerStatus').textContent = err.message;
        el('configServerStatus').className = 'status err';
      }
    });

    el('saveMailConfig').addEventListener('click', async () => {
      el('mailConfigStatus').textContent = '正在保存邮件配置...';
      el('mailConfigStatus').className = 'status';
      try {
        const result = await api('/api/mail-config', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(mailConfigPayload())
        });
        el('mailSmtpPassword').value = '';
        el('mailImapPassword').value = '';
        el('mailPasswordHint').textContent = 'SMTP 密码/授权码状态：' + (result.mail_config.smtp_password_masked || '未配置');
        el('mailImapPasswordHint').textContent = 'IMAP 密码/授权码状态：' + (result.mail_config.imap_password_masked || '未配置');
        el('mailConfigStatus').textContent = '邮件配置已保存。';
        el('mailConfigStatus').className = 'status ok';
      } catch (err) {
        el('mailConfigStatus').textContent = explainMailLoginError(err.message);
        el('mailConfigStatus').className = 'status err';
      }
    });

    el('testMailConfig').addEventListener('click', async () => {
      el('mailConfigStatus').textContent = '正在测试邮箱配置...';
      el('mailConfigStatus').className = 'status';
      try {
        await api('/api/mail-config', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(mailConfigPayload())
        });
        const result = await api('/api/test-mail-config', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({})
        });
        el('mailSmtpPassword').value = '';
        el('mailImapPassword').value = '';
        el('mailConfigStatus').textContent = result.message || '邮箱配置测试成功。';
        el('mailConfigStatus').className = 'status ok';
        await loadMailConfig();
      } catch (err) {
        el('mailConfigStatus').textContent = err.message;
        el('mailConfigStatus').className = 'status err';
      }
    });

    el('configModelSelect').addEventListener('change', () => {
      el('configModel').value = el('configModelSelect').value;
    });

    el('loadModels').addEventListener('click', async () => {
      el('configTestStatus').textContent = '正在获取模型列表...';
      el('configTestStatus').className = 'status';
      try {
        const result = await api('/api/admin-models', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(adminConfigPayload())
        });
        renderModelOptions(result.models, el('configModel').value || result.models[0]);
        el('configModel').value = el('configModelSelect').value;
        el('configTestStatus').textContent = result.warning || `已获取 ${result.models.length} 个模型。`;
        el('configTestStatus').className = result.warning ? 'status err' : 'status ok';
      } catch (err) {
        el('configTestStatus').textContent = err.message;
        el('configTestStatus').className = 'status err';
      }
    });

    el('testModel').addEventListener('click', async () => {
      el('configTestStatus').textContent = '正在测试 API Key 和模型...';
      el('configTestStatus').className = 'status';
      try {
        const result = await api('/api/admin-test-model', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(adminConfigPayload())
        });
        el('configTestStatus').textContent = `测试成功：${result.model} 返回 ${result.message}`;
        el('configTestStatus').className = 'status ok';
      } catch (err) {
        el('configTestStatus').textContent = '测试失败：' + err.message;
        el('configTestStatus').className = 'status err';
      }
    });

    el('addUser').addEventListener('click', async () => {
      const isSuper = state.user?.is_superadmin;
      const statusEl = el('userManageStatus') || el('configTestStatus');
      statusEl.textContent = '正在新增用户...';
      statusEl.className = 'status';
      try {
        const payload = {
          username: el('newUserName').value,
          password: el('newUserPassword').value,
          name: el('newDisplayName').value
        };
        if (isSuper) payload.role = el('newUserRole').value;
        const result = await apiPost('/api/admin-users', payload);
        renderUsers(result.users || []);
        el('newUserName').value = '';
        el('newDisplayName').value = '';
        el('newUserPassword').value = '';
        statusEl.textContent = '用户已新增。';
        statusEl.className = 'status ok';
      } catch (err) {
        statusEl.textContent = err.message;
        statusEl.className = 'status err';
      }
    });

    el('addSummary').addEventListener('click', () => addWorkRow('summary'));
    el('addFollow').addEventListener('click', () => addWorkRow('follow'));
    el('addNext').addEventListener('click', () => addWorkRow('next'));
    el('loadLatestWeekly').addEventListener('click', () => loadWeeklyPrefill(true));
    el('loadLatestTrip').addEventListener('click', () => loadTripPrefill(true));
    el('weeklyStart').addEventListener('change', () => {
      syncWeeklyPeriod();
      el('diarySumStart').value = el('weeklyStart').value;
    });
    el('weeklyEnd').addEventListener('change', () => {
      syncWeeklyPeriod();
      el('diarySumEnd').value = el('weeklyEnd').value;
    });
    window.addEventListener('beforeunload', () => {
      saveCurrentModal();
      saveFormDraft();
    });
    el('historyKind').addEventListener('change', renderHistoryReports);
    if (el('profileButton')) el('profileButton').addEventListener('click', openProfileModal);
    if (el('profileClose')) el('profileClose').addEventListener('click', closeProfileModal);
    if (el('profileModal')) el('profileModal').addEventListener('click', event => {
      if (event.target === el('profileModal')) closeProfileModal();
    });
    if (el('profileAvatarFile')) el('profileAvatarFile').addEventListener('change', () => {
      const file = el('profileAvatarFile').files[0];
      if (file) el('profileAvatarPreview').src = URL.createObjectURL(file);
    });
    if (el('profileUseAssistantAvatar')) el('profileUseAssistantAvatar').addEventListener('click', () => saveProfile('assistant'));
    if (el('profileSave')) el('profileSave').addEventListener('click', () => saveProfile());

    el('uploadButton').addEventListener('click', async () => {
      const selected = [...el('uploadFiles').files];
      if (!selected.length) {
        el('status').textContent = '请先选择要上传的历史报告文件。';
        el('status').className = 'status err';
        return;
      }
      el('uploadButton').disabled = true;
      el('uploadButton').textContent = '上传中...';
      el('status').textContent = '正在读取并上传文件...';
      el('status').className = 'status';
      try {
        const files = [];
        for (const file of selected) {
          files.push({ name: file.name, data: await readFileAsBase64(file) });
        }
        const result = await api('/api/upload-history', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ kind: el('uploadKind').value, files })
        });
        el('uploadList').innerHTML = result.uploaded.map(item => `
          <div class="upload-item">已上传：${escapeHtml(item.name)}</div>
        `).join('');
        el('status').textContent = `上传完成，共 ${result.uploaded.length} 个文件。`;
        el('status').className = 'status ok';
        el('uploadFiles').value = '';
        await loadReports({ preserveSelection: true });
        if (state.task === 'weekly' || state.task === 'trip') {
          renderHistoryReports();
          renderReports();
        } else {
          setTask('weekly');
        }
      } catch (err) {
        el('status').textContent = err.message;
        el('status').className = 'status err';
      } finally {
        el('uploadButton').disabled = false;
        el('uploadButton').textContent = '上传到历史报告库';
      }
    });

    // ===== 工作日记 =====
    function initDiaryPanel() {
      const today = new Date().toISOString().split('T')[0];
      el('diaryDate').value = today;
      loadDiaryToForm(today);
      renderDiaryList();
    }
    function setDiaryTab(tab) {
      document.querySelectorAll('.diary-tab').forEach(t => t.classList.toggle('active', t.dataset.diarytab === tab));
      el('diaryWriteView').classList.toggle('hidden', tab !== 'write');
      el('diaryBrowseView').classList.toggle('hidden', tab !== 'browse');
      if (tab === 'browse') renderDiaryList();
    }
    async function loadDiaryToForm(dateStr) {
      try {
        const data = await api('/api/diary/get?date=' + encodeURIComponent(dateStr));
        const d = data.diary || {};
        el('diaryTodayWork').value = d.today_work || '';
        el('diaryTomorrowPlan').value = d.tomorrow_plan || '';
        el('diaryThoughts').value = d.thoughts || '';
      } catch (err) {
        el('diaryTodayWork').value = '';
        el('diaryTomorrowPlan').value = '';
        el('diaryThoughts').value = '';
      }
    }
    async function saveDiary() {
      const payload = {
        date: el('diaryDate').value,
        today_work: el('diaryTodayWork').value,
        tomorrow_plan: el('diaryTomorrowPlan').value,
        thoughts: el('diaryThoughts').value,
      };
      if (!payload.date) {
        el('diaryStatus').textContent = '请选择日期';
        el('diaryStatus').className = 'status err';
        return;
      }
      try {
        el('diaryStatus').textContent = '保存中...';
        el('diaryStatus').className = 'status';
        await apiPost('/api/diary/save', payload);
        el('diaryStatus').textContent = '保存成功';
        el('diaryStatus').className = 'status ok';
        setTimeout(() => { el('diaryStatus').textContent = ''; }, 2000);
      } catch (err) {
        el('diaryStatus').textContent = err.message;
        el('diaryStatus').className = 'status err';
      }
    }
    async function renderDiaryList() {
      const list = el('diaryList');
      list.innerHTML = '<div class="diary-empty">加载中...</div>';
      try {
        const data = await api('/api/diary/list?limit=100');
        const items = data.diaries || [];
        if (!items.length) {
          list.innerHTML = '<div class="diary-empty">暂无日记，去记录第一篇吧～</div>';
          return;
        }
        list.innerHTML = items.map(item => `
          <div class="diary-item" data-date="${escapeHtml(item.date)}">
            <div class="diary-item-date">${escapeHtml(item.date)}</div>
            <div class="diary-item-preview">${escapeHtml(item.today_work_preview || '无内容')}</div>
            <span class="icon" data-icon="chevron-right"></span>
          </div>
        `).join('');
        renderIcons(list);
        list.querySelectorAll('.diary-item').forEach(item => {
          item.addEventListener('click', () => openDiaryDetail(item.dataset.date));
        });
      } catch (err) {
        list.innerHTML = `<div class="diary-empty">加载失败：${escapeHtml(err.message)}</div>`;
      }
    }
    async function openDiaryDetail(dateStr) {
      try {
        const data = await api('/api/diary/get?date=' + encodeURIComponent(dateStr));
        const d = data.diary || {};
        el('diaryDetailDate').textContent = (d.date || dateStr) + ' 日记详情';
        el('diaryDetailToday').textContent = d.today_work || '（无内容）';
        el('diaryDetailTomorrow').textContent = d.tomorrow_plan || '（无内容）';
        el('diaryDetailThoughts').textContent = d.thoughts || '（无内容）';
        el('diaryDetailEdit').onclick = () => {
          el('diaryDetailModal').classList.add('hidden');
          setDiaryTab('write');
          el('diaryDate').value = dateStr;
          loadDiaryToForm(dateStr);
        };
        el('diaryDetailDelete').onclick = async () => {
          if (!confirm('确定删除 ' + dateStr + ' 的日记吗？')) return;
          try {
            await apiPost('/api/diary/delete', { date: dateStr });
            el('diaryDetailModal').classList.add('hidden');
            renderDiaryList();
          } catch (err) {
            alert('删除失败：' + err.message);
          }
        };
        el('diaryDetailModal').classList.remove('hidden');
      } catch (err) {
        alert('读取日记失败：' + err.message);
      }
    }

    // 日记事件绑定
    document.querySelectorAll('.diary-tab').forEach(tab => {
      tab.addEventListener('click', () => setDiaryTab(tab.dataset.diarytab));
    });
    el('diaryLoadToday').addEventListener('click', () => {
      const today = new Date().toISOString().split('T')[0];
      el('diaryDate').value = today;
      loadDiaryToForm(today);
    });
    el('diaryDate').addEventListener('change', () => loadDiaryToForm(el('diaryDate').value));
    el('diarySaveButton').addEventListener('click', saveDiary);
    el('diaryClearButton').addEventListener('click', () => {
      el('diaryTodayWork').value = '';
      el('diaryTomorrowPlan').value = '';
      el('diaryThoughts').value = '';
      el('diaryStatus').textContent = '';
    });
    function openDiaryEditor(fieldId, title) {
      const value = el(fieldId).value;
      openModal(title, [
        { key: 'content', label: title, multiline: true, value: value }
      ], (values) => {
        el(fieldId).value = values.content || '';
        saveDiary();
      });
    }
    el('diaryTodayWork').addEventListener('click', () => openDiaryEditor('diaryTodayWork', '今日工作内容'));
    el('diaryTomorrowPlan').addEventListener('click', () => openDiaryEditor('diaryTomorrowPlan', '明日工作计划'));
    el('diaryThoughts').addEventListener('click', () => openDiaryEditor('diaryThoughts', '思路与想法'));
    el('diaryAgentButton').addEventListener('click', () => startAgent('diary'));
    el('diaryRefreshList').addEventListener('click', renderDiaryList);

    // 工作日记智能总结 → 周报
    async function summarizeDiariesForWeekly() {
      const start = el('diarySumStart').value;
      const end = el('diarySumEnd').value;
      if (!start || !end) {
        el('status').textContent = '请选择日记日期范围';
        el('status').className = 'status err';
        return;
      }
      if (start > end) {
        el('status').textContent = '开始日期不能晚于结束日期';
        el('status').className = 'status err';
        return;
      }
      el('status').textContent = '正在总结工作日记，请稍候...';
      el('status').className = 'status';
      try {
        const data = await apiPost('/api/diary/summarize', { start_date: start, end_date: end });
        if (!data.ok) {
          el('status').textContent = data.error || '总结失败';
          el('status').className = 'status err';
          return;
        }
        if (data.mode === 'empty') {
          el('status').textContent = data.warning || '该范围内无日记';
          el('status').className = 'status err';
          return;
        }
        parseAndApplyDiarySummary(data.summary || '');
        el('status').textContent = '日记总结已应用到周报，请检查并调整';
        el('status').className = 'status ok';
      } catch (err) {
        el('status').textContent = err.message;
        el('status').className = 'status err';
      }
    }
    function parseAndApplyDiarySummary(summary) {
      // 解析 AI 返回的总结文本，按三个部分填充
      const sections = { '本周工作总结': [], '重点工作跟进': [], '下周工作计划': [] };
      let current = null;
      summary.split('\n').forEach(line => {
        const trimmed = line.trim();
        if (!trimmed) return;
        if (trimmed.includes('本周工作总结') || trimmed.includes('本周工作')) {
          current = '本周工作总结';
        } else if (trimmed.includes('重点工作跟进') || trimmed.includes('重点工作')) {
          current = '重点工作跟进';
        } else if (trimmed.includes('下周工作计划') || trimmed.includes('下周工作')) {
          current = '下周工作计划';
        } else if (current && /^[\d一二三四五六七八九十]+[.、.．\s]/.test(trimmed)) {
          const content = trimmed.replace(/^[\d一二三四五六七八九十]+[.、.．\s]+/, '').trim();
          if (content) sections[current].push(content);
        } else if (current && trimmed.startsWith('- ')) {
          const content = trimmed.replace(/^- /, '').trim();
          if (content) sections[current].push(content);
        } else if (current && trimmed.startsWith('* ')) {
          const content = trimmed.replace(/^\* /, '').trim();
          if (content) sections[current].push(content);
        }
      });
      // 填充到周报表单
      const map = {
        '本周工作总结': 'summary',
        '重点工作跟进': 'follow',
        '下周工作计划': 'next'
      };
      Object.entries(map).forEach(([title, key]) => {
        const items = sections[title] || [];
        // 清空现有
        state[`weekly_${key}`] = [];
        items.forEach(content => {
          state[`weekly_${key}`].push({
            category: '',
            content: content,
            ...(key === 'summary' ? { status: '已完成' } : key === 'follow' ? { progress: '推进中' } : { difficulty: '正常' })
          });
        });
        renderWeeklyRows(key);
      });
      saveFormDraft();
    }
    el('diarySummarizeBtn').addEventListener('click', summarizeDiariesForWeekly);

    // ===== 金点子论坛 =====
    function forumSourceName(source) {
      if (source === 'ai') return '智能体';
      return '成员发起';
    }
    async function loadForumTopics(selectFirst = false) {
      const list = el('forumTopicList');
      list.innerHTML = '<div class="forum-empty">加载话题中...</div>';
      try {
        const data = await api('/api/forum/topics');
        const topics = data.topics || [];
        el('forumTopicCount').textContent = `${topics.length} 个话题`;
        if (!topics.length) {
          list.innerHTML = '<div class="forum-empty">暂无话题，先发起一个金点子吧。</div>';
          el('forumTopicDetail').innerHTML = '<div class="forum-empty">选择一个话题查看详情和讨论。</div>';
          return;
        }
        list.innerHTML = topics.map(topic => `
          <div class="forum-topic-item ${state.forumSelected === topic.id ? 'active' : ''}" data-id="${escapeHtml(topic.id)}">
            <div class="forum-topic-title">${escapeHtml(topic.title)}</div>
            <div class="forum-topic-meta">${escapeHtml(forumSourceName(topic.source))} · ${escapeHtml(topic.author || '')} · ${escapeHtml(topic.created_at || '')}</div>
            <div class="forum-topic-stats">
              <span class="forum-stat">热度 ${topic.heat || 0}</span>
              <span class="forum-stat">赞 ${topic.like_count || 0}</span>
              <span class="forum-stat">评 ${topic.comment_count || 0}</span>
              <span class="forum-stat">看 ${topic.view_count || 0}</span>
            </div>
          </div>
        `).join('');
        list.querySelectorAll('.forum-topic-item').forEach(item => {
          item.addEventListener('click', () => openForumTopic(item.dataset.id));
        });
        if (selectFirst || !state.forumSelected) {
          openForumTopic(topics[0].id);
        }
      } catch (err) {
        list.innerHTML = `<div class="forum-empty">加载失败：${escapeHtml(err.message)}</div>`;
      }
    }
    async function openForumTopic(topicId) {
      state.forumSelected = topicId;
      state.forumCommentPage = 1;
      document.querySelectorAll('.forum-topic-item').forEach(item => {
        item.classList.toggle('active', item.dataset.id === topicId);
      });
      const detail = el('forumTopicDetail');
      detail.innerHTML = '<div class="forum-empty">读取话题中...</div>';
      try {
        const data = await api('/api/forum/topic?id=' + encodeURIComponent(topicId));
        renderForumTopic(data.topic);
      } catch (err) {
        detail.innerHTML = `<div class="forum-empty">读取失败：${escapeHtml(err.message)}</div>`;
      }
    }
    function forumCommentTree(comments) {
      const byParent = {};
      comments.forEach(comment => {
        const key = comment.parent_id || '';
        (byParent[key] ||= []).push(comment);
      });
      return byParent;
    }
    function forumCommentHtml(comment, children = []) {
      return `
        <div class="forum-comment ${comment.parent_id ? 'reply' : ''}" data-comment-id="${escapeHtml(comment.id || '')}" data-author="${escapeHtml(comment.author || '')}">
          <div class="forum-comment-meta">${escapeHtml(comment.author || '')} · ${escapeHtml(comment.created_at || '')}</div>
          <div class="forum-comment-body">${escapeHtml(comment.content || '')}</div>
          <div class="forum-comment-actions">
            <button class="mini secondary forum-reply-button" type="button">回复</button>
          </div>
        </div>
        ${children.map(child => forumCommentHtml(child, [])).join('')}`;
    }
    function renderForumTopic(topic) {
      const comments = topic.comments || [];
      const pageSize = 10;
      const tree = forumCommentTree(comments);
      const topComments = tree[''] || [];
      const totalPages = Math.max(1, Math.ceil(topComments.length / pageSize));
      state.forumCommentPage = Math.min(Math.max(1, state.forumCommentPage || 1), totalPages);
      const pageTopComments = topComments.slice((state.forumCommentPage - 1) * pageSize, state.forumCommentPage * pageSize);
      el('forumTopicDetail').innerHTML = `
        <div class="forum-topic-title" style="font-size:18px;">${escapeHtml(topic.title)}</div>
        <div class="forum-topic-meta">${escapeHtml(forumSourceName(topic.source))} · ${escapeHtml(topic.author || '')} · ${escapeHtml(topic.created_at || '')}</div>
        <div class="forum-topic-stats">
          <span class="forum-stat">热度 ${topic.heat || 0}</span>
          <span class="forum-stat">点赞 ${topic.like_count || 0}</span>
          <span class="forum-stat">评论 ${topic.comment_count || 0}</span>
          <span class="forum-stat">浏览 ${topic.view_count || 0}</span>
        </div>
        <div class="forum-topic-body" style="margin-top:12px;">${escapeHtml(topic.body)}</div>
        <div class="toolbar">
          <button type="button" id="forumLikeButton" class="secondary"><span class="icon" data-icon="thumbs-up"></span> 点赞</button>
        </div>
        <div class="forum-comments">
          ${pageTopComments.length ? pageTopComments.map(comment => forumCommentHtml(comment, tree[comment.id] || [])).join('') : '<div class="forum-empty">还没有讨论，来写第一条观点。</div>'}
        </div>
        <div class="forum-pagination">
          <button type="button" class="mini secondary" id="forumPrevPage" ${state.forumCommentPage <= 1 ? 'disabled' : ''}>上一页</button>
          <span>第 ${state.forumCommentPage} / ${totalPages} 页 · 共 ${comments.length} 条评论</span>
          <button type="button" class="mini secondary" id="forumNextPage" ${state.forumCommentPage >= totalPages ? 'disabled' : ''}>下一页</button>
        </div>
        <label>参与讨论</label>
        <textarea id="forumCommentInput" placeholder="写下你的观点、建议、风险提醒或下一步行动..."></textarea>
        <input id="forumCommentParent" type="hidden" value="" />
        <div class="toolbar">
          <button type="button" id="forumCommentButton">发布讨论</button>
          <button type="button" class="secondary" id="forumAiCommentButton"><span class="icon" data-icon="bot"></span> AI 潜水评论</button>
          <span id="forumCommentStatus" class="status"></span>
        </div>
      `;
      renderIcons(el('forumTopicDetail'));
      el('forumLikeButton').addEventListener('click', async () => {
        try {
          const result = await apiPost('/api/forum/like', { topic_id: topic.id });
          renderForumTopic(result.topic);
          loadForumTopics();
        } catch (err) {
          el('forumCommentStatus').textContent = err.message;
          el('forumCommentStatus').className = 'status err';
        }
      });
      el('forumPrevPage').addEventListener('click', () => {
        state.forumCommentPage -= 1;
        renderForumTopic(topic);
      });
      el('forumNextPage').addEventListener('click', () => {
        state.forumCommentPage += 1;
        renderForumTopic(topic);
      });
      document.querySelectorAll('.forum-reply-button').forEach(button => {
        button.addEventListener('click', () => {
          const item = button.closest('.forum-comment');
          el('forumCommentParent').value = item.dataset.commentId || '';
          el('forumCommentInput').value = `回复 ${item.dataset.author || '成员'}：`;
          el('forumCommentInput').focus();
        });
      });
      el('forumCommentButton').addEventListener('click', async () => {
        const content = el('forumCommentInput').value.trim();
        if (!content) {
          el('forumCommentStatus').textContent = '请先填写讨论内容';
          el('forumCommentStatus').className = 'status err';
          return;
        }
        try {
          el('forumCommentStatus').textContent = '发布中...';
          el('forumCommentStatus').className = 'status';
          const result = await apiPost('/api/forum/comment', { topic_id: topic.id, content, parent_id: el('forumCommentParent').value });
          renderForumTopic(result.topic);
          loadForumTopics();
        } catch (err) {
          el('forumCommentStatus').textContent = err.message;
          el('forumCommentStatus').className = 'status err';
        }
      });
      el('forumAiCommentButton').addEventListener('click', async () => {
        try {
          el('forumCommentStatus').textContent = 'AI 潜水员正在读帖...';
          el('forumCommentStatus').className = 'status';
          const result = await apiPost('/api/forum/ai-comment', { topic_id: topic.id });
          renderForumTopic(result.topic);
          loadForumTopics();
        } catch (err) {
          el('forumCommentStatus').textContent = err.message;
          el('forumCommentStatus').className = 'status err';
        }
      });
    }
    el('forumCreateButton').addEventListener('click', async () => {
      const payload = { title: el('forumTitle').value, body: el('forumBody').value };
      try {
        el('forumCreateStatus').textContent = '发布中...';
        el('forumCreateStatus').className = 'status';
        const result = await apiPost('/api/forum/create', payload);
        el('forumTitle').value = '';
        el('forumBody').value = '';
        el('forumCreateStatus').textContent = '话题已发布';
        el('forumCreateStatus').className = 'status ok';
        state.forumSelected = result.topic.id;
        await loadForumTopics();
        openForumTopic(result.topic.id);
      } catch (err) {
        el('forumCreateStatus').textContent = err.message;
        el('forumCreateStatus').className = 'status err';
      }
    });
    el('forumRefreshButton').addEventListener('click', () => loadForumTopics());
    el('forumToggleCreate').addEventListener('click', () => {
      const panel = el('forumCreatePanel');
      const hidden = panel.classList.toggle('hidden');
      el('forumToggleCreate').textContent = hidden ? '发起话题' : '收起发起';
    });
    el('forumAiButton').addEventListener('click', async () => {
      try {
        el('forumAiStatus').textContent = '智能体正在起题...';
        el('forumAiStatus').className = 'status';
        const files = [];
        for (const file of [...el('forumAiFiles').files]) {
          files.push({ name: file.name, data: await readFileAsBase64(file) });
        }
        const result = await apiPost('/api/forum/ai-topic', {
          seed: el('forumAiSeed').value,
          chat: el('forumAiChat').value,
          files
        });
        el('forumAiSeed').value = '';
        el('forumAiChat').value = '';
        el('forumAiFiles').value = '';
        el('forumAiStatus').textContent = '智能话题已发布';
        el('forumAiStatus').className = 'status ok';
        state.forumSelected = result.topic.id;
        await loadForumTopics();
        openForumTopic(result.topic.id);
      } catch (err) {
        el('forumAiStatus').textContent = err.message;
        el('forumAiStatus').className = 'status err';
      }
    });

    // ===== 每日资讯 =====
    function renderNewsSources(sources = []) {
      const box = el('newsSources');
      const rows = sources.length ? sources : [{ name: '', url: '' }];
      box.innerHTML = rows.map((source, index) => `
        <div class="news-source-row" data-index="${index}">
          <input class="news-source-name" placeholder="名称" value="${escapeHtml(source.name || '')}" />
          <input class="news-source-url" placeholder="https://example.com/news" value="${escapeHtml(source.url || '')}" />
          <button class="mini danger news-remove-source" type="button">删除</button>
        </div>
      `).join('');
      box.querySelectorAll('.news-remove-source').forEach(button => {
        button.addEventListener('click', () => {
          button.closest('.news-source-row').remove();
          if (!box.querySelector('.news-source-row')) renderNewsSources();
        });
      });
    }
    function collectNewsSources() {
      return [...document.querySelectorAll('.news-source-row')].map(row => ({
        name: row.querySelector('.news-source-name').value.trim(),
        url: row.querySelector('.news-source-url').value.trim()
      })).filter(item => item.url);
    }
    function renderNewsIssue(issue) {
      if (!issue) {
        el('newsTitle').textContent = '暂无每日资讯';
        el('newsMeta').textContent = state.user?.is_superadmin ? '配置资讯源后生成今日简报。' : '暂无今日简报，请稍后刷新。';
        el('newsSummary').textContent = '暂无摘要。';
        el('newsItems').innerHTML = '<div class="forum-empty">暂无资讯内容。</div>';
        el('newsKeywords').innerHTML = '';
        return;
      }
      el('newsTitle').textContent = issue.title || `${issue.date || ''} 轨道交通每日资讯`;
      el('newsMeta').textContent = `${issue.date || ''} · ${issue.generated_at || ''} · ${issue.generated_by || ''}`;
      el('newsSummary').textContent = issue.summary || '暂无摘要。';
      const items = issue.items || [];
      el('newsItems').innerHTML = items.length ? items.map(item => `
        <div class="news-item">
          <div class="news-item-title">${escapeHtml(item.title || '未命名资讯')}</div>
          <div class="news-item-meta">${escapeHtml(item.source || '')}${item.url ? ` · <a href="${escapeHtml(item.url)}" target="_blank">来源链接</a>` : ''}</div>
          <p><strong>影响/价值：</strong>${escapeHtml(item.impact || '')}</p>
          <p><strong>建议动作：</strong>${escapeHtml(item.action || '')}</p>
        </div>
      `).join('') : '<div class="forum-empty">暂无资讯条目。</div>';
      el('newsKeywords').innerHTML = (issue.keywords || []).map(k => `<span class="news-keyword">${escapeHtml(k)}</span>`).join('');
    }
    async function loadNews() {
      try {
        const data = await api('/api/news/latest');
        if (state.user?.is_superadmin) {
          const cfg = data.config || {};
          renderNewsSources(cfg.sources || []);
          el('newsSearchQuery').value = cfg.search_query || '';
          el('newsAutoSearch').checked = !!cfg.auto_search;
          el('newsAutoPush').checked = !!cfg.auto_push;
          el('newsPushTime').value = cfg.push_time || '08:30';
        }
        renderNewsIssue(data.issue);
      } catch (err) {
        el('newsConfigStatus').textContent = err.message;
        el('newsConfigStatus').className = 'status err';
      }
    }
    el('newsAddSource').addEventListener('click', () => {
      const current = collectNewsSources();
      current.push({ name: '', url: '' });
      renderNewsSources(current);
    });
    el('newsRefresh').addEventListener('click', loadNews);
    el('newsSaveConfig').addEventListener('click', async () => {
      try {
        el('newsConfigStatus').textContent = '保存中...';
        el('newsConfigStatus').className = 'status';
        await apiPost('/api/news/config', {
          sources: collectNewsSources(),
          search_query: el('newsSearchQuery').value,
          auto_search: el('newsAutoSearch').checked,
          auto_push: el('newsAutoPush').checked,
          push_time: el('newsPushTime').value
        });
        el('newsConfigStatus').textContent = '资讯配置已保存';
        el('newsConfigStatus').className = 'status ok';
      } catch (err) {
        el('newsConfigStatus').textContent = err.message;
        el('newsConfigStatus').className = 'status err';
      }
    });
    el('newsGenerateNow').addEventListener('click', async () => {
      try {
        el('newsConfigStatus').textContent = '正在抓取网页并调用大模型生成资讯...';
        el('newsConfigStatus').className = 'status';
        const result = await apiPost('/api/news/generate', {
          search_query: el('newsSearchQuery').value,
          auto_search: el('newsAutoSearch').checked
        });
        renderNewsIssue(result.issue);
        el('newsConfigStatus').textContent = '今日资讯已生成';
        el('newsConfigStatus').className = 'status ok';
      } catch (err) {
        el('newsConfigStatus').textContent = err.message;
        el('newsConfigStatus').className = 'status err';
      }
    });

    el('modalSave').addEventListener('click', saveAndCloseModal);
    el('modalCancel').addEventListener('click', saveAndCloseModal);
    el('modalClose').addEventListener('click', saveAndCloseModal);
    el('modalFields').addEventListener('input', event => {
      if (event.target.closest('[data-modal-key]')) {
        saveCurrentModal();
      }
    });
    el('editModal').addEventListener('click', event => {
      if (event.target === el('editModal')) saveAndCloseModal();
    });
    document.addEventListener('keydown', event => {
      if (event.key === 'Escape' && !el('editModal').classList.contains('hidden')) {
        saveAndCloseModal();
      }
    });
    el('dashboardAskButton').addEventListener('click', () => {
      const text = el('dashboardAsk').value.trim();
      agentKind = agentKindForTask();
      updateAgentChrome(agentKind);
      toggleAgent(true);
      if (!agentMessages.length) {
        agentMessages.push({ role: 'assistant', content: `你好，我是${agentTitle(agentKind)}。你可以直接把当前页面相关的问题交给我。` });
      }
      renderAgentMessages();
      if (text) sendAgentMessage(text);
    });
    el('dashboardAsk').addEventListener('keydown', event => {
      if (event.key === 'Enter') {
        event.preventDefault();
        el('dashboardAskButton').click();
      }
    });
    async function optimizeField(button) {
      const fieldWrap = button.closest('.wide');
      const input = fieldWrap?.querySelector('textarea[data-modal-key]');
      const promptInput = fieldWrap?.querySelector('.field-assist-prompt');
      const fieldStatus = fieldWrap?.querySelector('.assist-status');
      if (!input || !promptInput || !fieldStatus) return;
      const original = input.value.trim();
      if (!original) {
        fieldStatus.textContent = '请先填写需要优化的内容。';
        fieldStatus.className = 'assist-status err';
        return;
      }
      button.disabled = true;
      button.textContent = '优化中...';
      fieldStatus.textContent = '正在调用 MiniMax-M2.7 优化，请稍等...';
      fieldStatus.className = 'assist-status';
      try {
        const result = await api('/api/optimize', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            text: original,
            prompt: promptInput.value
          })
        });
        input.value = result.text || original;
        fieldStatus.textContent = result.warning || '优化完成，已写入当前输入框。';
        fieldStatus.className = result.warning ? 'assist-status err' : 'assist-status ok';
      } catch (err) {
        fieldStatus.textContent = '优化失败：' + err.message;
        fieldStatus.className = 'assist-status err';
      } finally {
        button.disabled = false;
        button.textContent = '辅助优化';
      }
    }

    el('modalFields').addEventListener('click', event => {
      const button = event.target.closest('.assist-optimize');
      if (button) optimizeField(button);
    });

    el('refresh').addEventListener('click', () => {
      const kind = state.task === 'mail' ? el('mailKind').value : el('kind').value;
      loadDraft(kind, state.selected);
    });
    el('copy').addEventListener('click', async () => {
      await navigator.clipboard.writeText(el('body').value);
      el('status').textContent = '正文已复制';
      el('status').className = 'status ok';
    });
    el('body').addEventListener('input', () => {
      state.bodyHtml = '';
      renderBodyPreview();
      clearSendReview();
    });
    ['to', 'cc', 'subject', 'attachment'].forEach(id => {
      el(id).addEventListener('input', clearSendReview);
      el(id).addEventListener('change', clearSendReview);
    });

    function sendPayload() {
      return {
        to: el('to').value.trim(),
        cc: el('cc').value.trim(),
        subject: el('subject').value.trim(),
        body: el('body').value,
        body_html: state.bodyHtml || '',
        attachment: el('attachment').value.trim()
      };
    }

    function sendBlockers(payload) {
      const blockers = [];
      if (!payload.to) blockers.push('收件人为空');
      if (!payload.subject) blockers.push('主题为空');
      if (!payload.attachment) blockers.push('未选择附件');
      const badWords = ['跟进内容', '计划内容', '很长内容', '总结5', '总结6'];
      const found = badWords.filter(word => payload.body.includes(word));
      if (found.length) blockers.push('正文疑似含测试残留：' + found.join('、'));
      return blockers;
    }

    function clearSendReview() {
      const box = el('sendReview');
      if (!box) return;
      box.classList.add('hidden');
      box.innerHTML = '';
    }

    function renderSendReview(payload, blockers = []) {
      const box = el('sendReview');
      if (!box) return;
      box.classList.remove('hidden');
      box.innerHTML = `
        <div class="send-review-title">发送前确认</div>
        <div class="send-review-grid">
          <div class="label">收件人</div><div>${escapeHtml(payload.to || '未填写')}</div>
          <div class="label">抄送</div><div>${escapeHtml(payload.cc || '无')}</div>
          <div class="label">主题</div><div>${escapeHtml(payload.subject || '未填写')}</div>
          <div class="label">附件</div><div>${escapeHtml(payload.attachment || '未选择')}</div>
        </div>
        ${blockers.length ? `<div class="send-review-warning">${escapeHtml(blockers.join('；'))}</div>` : ''}
        <div class="send-review-actions">
          <button type="button" class="secondary" id="cancelSendReview">取消</button>
          <button type="button" id="openMailConfigFromSend" class="secondary">邮件配置</button>
          <button type="button" class="warn" id="confirmSendReview" ${blockers.length ? 'disabled' : ''}>确认发送</button>
        </div>
      `;
      el('cancelSendReview').addEventListener('click', clearSendReview);
      el('openMailConfigFromSend').addEventListener('click', () => setTask('mailconfig'));
      el('confirmSendReview').addEventListener('click', () => doSendMail(payload));
    }

    function explainSendError(message) {
      const text = String(message || '发送失败');
      if (text.includes('SMTP 用户名')) return text + ' 建议在“邮件配置”中把 SMTP 用户名填写为发件邮箱。';
      if (text.includes('SMTP 密码')) return text + ' 请确认已填写邮箱授权码，不要使用网页登录密码。';
      if (text.includes('收件人')) return text + ' 请检查收件人邮箱，多个邮箱用分号分隔。';
      return text;
    }

    async function doSendMail(payload) {
      el('status').textContent = '处理中...';
      el('status').className = 'status';
      try {
        const result = await api('/api/send', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        el('status').textContent = result.message;
        el('status').className = 'status ok';
        clearSendReview();
      } catch (err) {
        el('status').textContent = explainSendError(err.message);
        el('status').className = 'status err';
        renderSendReview(payload, []);
      }
    }

    el('send').addEventListener('click', async () => {
      const payload = sendPayload();
      const blockers = sendBlockers(payload);
      renderSendReview(payload, blockers);
    });

    function agentKindForTask(task = state.task) {
      if (['weekly', 'trip', 'diary', 'forum', 'news', 'mailassistant'].includes(task)) return task;
      if (task === 'calendar') return 'diary';
      return 'dashboard';
    }

    function agentTitle(kind) {
      return {
        weekly: '周报助手',
        trip: '出差报告助手',
        diary: '日记助手',
        forum: '论坛助手',
        news: '资讯助手',
        mailassistant: '智能邮件助手',
        dashboard: 'AI 办公总助手'
      }[kind] || '犇犇';
    }

    function agentIcon(kind) {
      return {
        weekly: 'file-spreadsheet',
        trip: 'briefcase-business',
        diary: 'book-open',
        forum: 'messages-square',
        news: 'newspaper',
        mailassistant: 'inbox',
        dashboard: 'layout-dashboard'
      }[kind] || 'bot';
    }

    function agentIntro(kind, hasContent = false) {
      const intro = {
        weekly: {
          title: '周报助手怎么用',
          copy: hasContent ? '我看到当前周报页已有内容。你可以先让我检查问题，也可以直接给我本周工作素材重写。' : '直接把本周做过的事、重点项目、下周计划发给我，我会自动整理成周报草稿 → 生成预览 → 发送邮件。',
          tips: ['我会自动获取当前日期和本周周期', '先对话收集信息，再一键生成草稿', '确认预览后再发送，全程不用手动填表'],
          prompts: [
            ['帮我写本周周报', '帮我写本周周报。'],
            ['根据素材写周报', '请根据我接下来提供的工作素材，生成正式周报并填入表单。'],
            ['优化语言表达', '请优化当前周报表单里的表达，让内容更正式、具体、清晰。']
          ]
        },
        mailassistant: {
          title: '邮件助手怎么用',
          copy: '我可以帮你总结邮件、起草回复、润色正文。真正发送前，页面会让你确认收件人、主题和附件。',
          tips: ['SMTP 用于发送，IMAP 用于收件箱', 'SMTP 用户名通常就是发件邮箱', '授权码不是网页登录密码'],
          prompts: [
            ['检查邮件配置', '请告诉我当前邮件配置还缺什么，以及下一步怎么修。'],
            ['优化当前正文', '请帮我把当前邮件正文优化得更清晰、礼貌、适合发送。'],
            ['起草一封邮件', '请根据我的要求起草一封普通邮件。']
          ]
        },
        dashboard: {
          title: '犇犇可以做什么',
          copy: '选择一个工作场景，或直接说你要处理的事。我会尽量把结果写回页面，而不是只给建议。',
          tips: ['周报、出差报告、日记、邮件都可以处理', '复杂操作会先生成预览或确认卡', '发送、发布等外部动作会二次确认'],
          prompts: [
            ['写本周周报', '帮我写本周周报。', 'weekly'],
            ['处理邮件', '帮我处理一封邮件。', 'mailassistant'],
            ['记录工作日记', '帮我记录今天的工作日记。', 'diary']
          ]
        }
      };
      return intro[kind] || {
        title: `${agentTitle(kind)}怎么用`,
        copy: '告诉我你要完成的目标，我会结合当前页面内容帮你整理、填写或生成。',
        tips: ['先说明目标', '确认内容后再执行外部动作', '可以随时要求重写或优化'],
        prompts: [['分析当前页面', '请分析当前页面内容，并告诉我下一步怎么做。']]
      };
    }

    function updateAgentChrome(kind = agentKindForTask()) {
      const title = agentTitle(kind);
      const header = document.querySelector('#agentWindow .agent-header span');
      if (header) {
        header.innerHTML = `<img class="agent-avatar" src="${resourceUrl('/assets/ai-assistant-avatar.png')}" alt="" /> ${title}`;
      }
      el('agentToggle').title = title;
      el('agentActions').innerHTML = `
        <button class="agent-action agent-kind-action" type="button" data-agent-kind="${kind}"><span class="icon" data-icon="${agentIcon(kind)}"></span> 当前</button>
        <button class="agent-action agent-kind-action" type="button" data-agent-kind="weekly"><span class="icon" data-icon="file-spreadsheet"></span> 周报</button>
        <button class="agent-action agent-kind-action" type="button" data-agent-kind="mailassistant"><span class="icon" data-icon="inbox"></span> 邮件</button>
        <button class="agent-action" type="button" id="agentClear"><span class="icon" data-icon="rotate-ccw"></span> 清空</button>
      `;
      el('agentActions').querySelectorAll('.agent-kind-action').forEach(btn => {
        btn.addEventListener('click', () => startAgent(btn.dataset.agentKind, true));
      });
      el('agentClear')?.addEventListener('click', () => startAgent(agentKind, true));
      renderIcons(el('agentWindow'));
    }

    function syncAgentToTask(task = state.task) {
      const nextKind = agentKindForTask(task);
      const changed = agentKind !== nextKind;
      agentKind = nextKind;
      updateAgentChrome(nextKind);
      if (changed) {
        agentMessages = [];
        renderAgentMessages();
      }
      const win = el('agentWindow');
      if (changed && win && !win.classList.contains('hidden')) {
        startAgent(nextKind, true);
      }
    }

    function toggleAgent(show) {
      const win = el('agentWindow');
      const shouldOpen = show === true || (show === undefined && win.classList.contains('hidden'));
      if (show === true) win.classList.remove('hidden');
      else if (show === false) win.classList.add('hidden');
      else if (shouldOpen) win.classList.remove('hidden');
      bringAgentToFront();
    }

    function bringAgentToFront() {
      const agent = el('agentFloat');
      if (!agent) return;
      agent.style.zIndex = '3000';
    }

    function agentStageSteps(kind = agentKind) {
      if (kind === 'weekly') return ['分析', '生成', '预览', '发送'];
      if (kind === 'trip') return ['分析', '整理', '生成', '发送'];
      if (kind === 'mailassistant') return ['读取', '起草', '确认', '发送'];
      return ['理解', '处理', '确认', '完成'];
    }

    function setAgentStage(index = 0) {
      state.agentStage = index;
      const box = el('agentProgress');
      if (!box) return;
      const steps = agentStageSteps(agentKind);
      box.innerHTML = steps.map((step, idx) => `
        <div class="agent-step ${idx < index ? 'done' : idx === index ? 'active' : ''}">${escapeHtml(step)}</div>
      `).join('');
    }

    function compactAssistantText(content) {
      const text = String(content || '').trim();
      if (!text) return '';
      const raw = text.replace(/^```json\s*/i, '').replace(/```$/i, '').trim();
      if (raw.startsWith('{') && raw.endsWith('}')) {
        try {
          const data = JSON.parse(raw);
          return data.reply || '已完成当前步骤，页面内容已同步更新。';
        } catch (err) {
          return text;
        }
      }
      return text;
    }

    function renderMarkdown(text) {
      if (!text) return '';
      // Protect code blocks
      const codeBlocks = [];
      text = text.replace(/```([\s\S]*?)```/g, (match, code) => {
        codeBlocks.push(escapeHtml(code.replace(/^.*?\n/, '')));
        return '__CODEBLOCK_' + (codeBlocks.length - 1) + '__';
      });
      // Protect inline code
      const inlineCodes = [];
      text = text.replace(/`([^`]+)`/g, (match, code) => {
        inlineCodes.push(escapeHtml(code));
        return '__INLINECODE_' + (inlineCodes.length - 1) + '__';
      });
      // Escape remaining HTML
      text = escapeHtml(text);
      // Process blocks
      const rawLines = text.split('\n');
      const blocks = [];
      let currentBlock = [];
      const flushBlock = () => {
        if (currentBlock.length === 0) return;
        if (currentBlock[0].trim().startsWith('|')) {
          blocks.push(renderMarkdownTable(currentBlock));
        } else {
          blocks.push(renderMarkdownBlock(currentBlock.join('\n')));
        }
        currentBlock = [];
      };
      for (let line of rawLines) {
        if (line.trim() === '') {
          flushBlock();
        } else {
          currentBlock.push(line);
        }
      }
      flushBlock();
      text = blocks.join('\n');
      // Restore inline code
      text = text.replace(/__INLINECODE_(\d+)__/g, (match, idx) => {
        return '<code style="background:#0f172a;padding:2px 5px;border-radius:4px;font-size:13px;color:#7dd3fc;">' + inlineCodes[idx] + '</code>';
      });
      // Restore code blocks
      text = text.replace(/__CODEBLOCK_(\d+)__/g, (match, idx) => {
        return '<pre style="background:#0f172a;padding:12px;border-radius:8px;overflow-x:auto;font-size:13px;line-height:1.5;border:1px solid #1e293b;margin:8px 0;"><code>' + codeBlocks[idx] + '</code></pre>';
      });
      return text;
    }
    function renderMarkdownBlock(block) {
      if (block.startsWith('# ')) return '<h1 style="margin:14px 0 10px;font-size:20px;color:#e2e8f0;font-weight:700;">' + block.slice(2) + '</h1>';
      if (block.startsWith('## ')) return '<h2 style="margin:12px 0 8px;font-size:18px;color:#e2e8f0;font-weight:700;border-bottom:1px solid #334155;padding-bottom:4px;">' + block.slice(3) + '</h2>';
      if (block.startsWith('### ')) return '<h3 style="margin:10px 0 6px;font-size:16px;color:#e2e8f0;font-weight:600;">' + block.slice(4) + '</h3>';
      if (block.trim() === '---') return '<hr style="border:none;border-top:1px solid #334155;margin:10px 0;">';
      let html = block.replace(/\*\*(.*?)\*\*/g, '<strong style="color:#e2e8f0;">$1</strong>');
      const lines = html.split('\n');
      const isBullet = lines.every(l => l.trim().startsWith('- ') || l.trim().startsWith('* '));
      const isNumbered = lines.every(l => /^\s*\d+\./.test(l.trim()));
      if (isBullet) {
        const items = lines.map(l => '<li style="margin:4px 0;">' + l.trim().replace(/^[-*] /, '') + '</li>').join('');
        return '<ul style="margin:6px 0;padding-left:20px;">' + items + '</ul>';
      }
      if (isNumbered) {
        const items = lines.map(l => '<li style="margin:4px 0;">' + l.trim().replace(/^\d+\.\s*/, '') + '</li>').join('');
        return '<ol style="margin:6px 0;padding-left:20px;">' + items + '</ol>';
      }
      return '<p style="margin:6px 0;">' + html.replace(/\n/g, '<br>') + '</p>';
    }
    function renderMarkdownTable(lines) {
      const rows = lines.map(line => {
        const trimmed = line.trim();
        if (!trimmed.startsWith('|')) return null;
        return trimmed.slice(1).split('|').map(c => c.trim());
      }).filter(r => r !== null);
      if (rows.length < 2) return lines.join('<br>');
      const isSep = rows[1].every(c => /^:?-+:?$/.test(c));
      if (!isSep) return lines.join('<br>');
      let html = '<table style="width:100%;border-collapse:collapse;margin:8px 0;font-size:13px;">';
      html += '<thead><tr>';
      rows[0].forEach(cell => {
        html += '<th style="border:1px solid #334155;padding:8px 10px;background:#1e293b;color:#94a3b8;text-align:left;font-weight:600;">' + cell + '</th>';
      });
      html += '</tr></thead><tbody>';
      for (let i = 2; i < rows.length; i++) {
        html += '<tr>';
        rows[i].forEach((cell, idx) => {
          const sep = rows[1][idx] || '';
          let align = 'left';
          if (sep.startsWith(':') && sep.endsWith(':')) align = 'center';
          else if (sep.endsWith(':')) align = 'right';
          html += '<td style="border:1px solid #334155;padding:8px 10px;color:#cbd5e1;text-align:' + align + ';">' + cell + '</td>';
        });
        html += '</tr>';
      }
      html += '</tbody></table>';
      return html;
    }

    function agentMessageHtml(m) {
      if (m.type === 'intro') {
        return `
          <div class="agent-msg assistant">
            <div class="agent-intro">
              <div class="agent-intro-title">${escapeHtml(m.title)}</div>
              <div class="agent-intro-copy">${escapeHtml(m.copy)}</div>
              <div class="agent-quick-grid">
                ${(m.prompts || []).map(([label, prompt, targetKind]) => `<button type="button" class="agent-quick" data-agent-prompt="${escapeHtml(prompt)}" ${targetKind ? `data-agent-target-kind="${escapeHtml(targetKind)}"` : ''}>${escapeHtml(label)}</button>`).join('')}
              </div>
              ${(m.tips || []).length ? `<ul class="agent-help-list">${m.tips.map(tip => `<li>${escapeHtml(tip)}</li>`).join('')}</ul>` : ''}
            </div>
          </div>`;
      }
      if (m.type === 'skill') {
        return `
          <div class="agent-msg assistant">
            <div class="agent-card">
              <div class="agent-card-title">${escapeHtml(m.title || 'Skill 调用完成')}</div>
              ${m.metrics ? `<div class="agent-card-grid">${m.metrics.map(item => `
                <div class="agent-card-metric"><strong>${escapeHtml(item.value)}</strong><span>${escapeHtml(item.label)}</span></div>
              `).join('')}</div>` : ''}
              ${m.items && m.items.length ? `<ul class="agent-card-list">${m.items.map(item => `<li>${escapeHtml(item)}</li>`).join('')}</ul>` : ''}
              ${m.note ? `<div class="agent-card-note">${escapeHtml(m.note)}</div>` : ''}
              ${m.image_url ? `<div><img class="agent-img" src="${escapeHtml(resourceUrl(m.image_url))}" style="max-width:100%;border:1px solid #dbe5f1;border-radius:8px;background:#fff;cursor:zoom-in;" onclick="openAgentLightbox('${escapeHtml(resourceUrl(m.image_url))}')" /></div>` : ''}
            </div>
          </div>`;
      }
      const content = m.role === 'assistant' ? compactAssistantText(m.content) : m.content;
      const htmlContent = m.role === 'assistant' ? renderMarkdown(content) : escapeHtml(content);
      return `<div class="agent-msg ${m.role}">
        ${htmlContent}
        ${m.image_url ? `<div style="margin-top:10px"><img class="agent-img" src="${escapeHtml(resourceUrl(m.image_url))}" style="max-width:100%;border:1px solid #dbe5f1;border-radius:8px;background:#fff;cursor:zoom-in;" onclick="openAgentLightbox('${escapeHtml(resourceUrl(m.image_url))}')" /></div>` : ''}
      </div>`;
    }

    function renderAgentMessages() {
      const box = el('agentMessages');
      box.innerHTML = agentMessages.map(agentMessageHtml).join('');
      box.querySelectorAll('[data-agent-prompt]').forEach(btn => {
        btn.addEventListener('click', () => {
          const targetKind = btn.dataset.agentTargetKind;
          if (targetKind && targetKind !== agentKind) startAgent(targetKind, true);
          sendAgentMessage(btn.dataset.agentPrompt || '');
        });
      });
      box.scrollTop = box.scrollHeight;
      setAgentStage(state.agentStage || 0);
    }

    function agentPayloadMessages() {
      return agentMessages
        .filter(m => ['user', 'assistant'].includes(m.role) && m.content && !m.type)
        .map(m => ({ role: m.role, content: String(m.content || '') }));
    }

    function appendSkillResult(result) {
      if (!result) return;
      // 支持多次 Skill 调用（skill_calls 数组）和单次调用（skill_call 对象）
      const calls = result.skill_calls || (result.skill_call ? [{ name: result.skill_call.name, result: result.skill_result }] : []);
      if (!calls.length) return;
      calls.forEach(call => {
        const name = call.name || '';
        const data = call.result || {};
        if (name === 'weekly.compose' && data.draft) {
          if (hasRowContent(data.draft.weekly_summary)) renderWorkRows('summary', data.draft.weekly_summary);
          if (hasRowContent(data.draft.weekly_follow)) renderWorkRows('follow', data.draft.weekly_follow);
          if (hasRowContent(data.draft.weekly_next)) renderWorkRows('next', data.draft.weekly_next);
          agentMessages.push({
            role: 'assistant',
            type: 'skill',
            title: '周报草稿已生成并填入表单',
            metrics: [
              { label: '工作总结', value: (data.draft.weekly_summary || []).length },
              { label: '重点跟进', value: (data.draft.weekly_follow || []).length },
              { label: '下周计划', value: (data.draft.weekly_next || []).length }
            ],
            items: (data.draft.weekly_summary || []).slice(0, 3).map(item => `${item.category || '事项'}：${item.content || ''}`),
            note: '草稿已填入“填写报告”页面，你可以继续补充或告诉我直接生成预览。'
          });
          setAgentStage(2);
          renderAgentMessages();
          return;
        }
        if (name === 'weekly.preview') {
          agentMessages.push({
            role: 'assistant',
            type: 'skill',
            title: '周报预览已生成',
            metrics: [
              { label: '附件', value: data.file || '1' },
              { label: '周期', value: (data.mail_draft && data.mail_draft.period) || '' }
            ].filter(m => m.value),
            items: [
              data.file && `文件：${data.file}`,
              data.mail_draft && data.mail_draft.subject && `主题：${data.mail_draft.subject}`
            ].filter(Boolean),
            note: '预览图已生成，确认无误后告诉我“发送”即可。',
            image_url: data.preview_image_url || ''
          });
          setAgentStage(3);
          renderAgentMessages();
          return;
        }
        if (name === 'weekly.send_confirmed') {
          agentMessages.push({
            role: 'assistant',
            type: 'skill',
            title: '周报邮件已发送',
            metrics: data.mode ? [{ label: '状态', value: data.mode }] : null,
            items: [data.message].filter(Boolean),
            note: '本周周报已发送完成，如需继续处理其他工作随时告诉我。'
          });
          setAgentStage(4);
          renderAgentMessages();
          return;
        }
        if (name === 'utils.get_date') {
          // 日期获取不展示卡片，由大模型在回复中自然描述
          return;
        }
        agentMessages.push({
          role: 'assistant',
          type: 'skill',
          title: `${name} 已完成`,
          metrics: data.file ? [{ label: '附件', value: '1' }] : null,
          items: [data.file, data.message, data.mode ? `结果：${data.mode}` : ''].filter(Boolean),
          note: data.mail_draft ? '邮件草稿已生成，请确认收件人、主题、附件和正文后再发送。' : '',
          image_url: data.preview_image_url || ''
        });
        renderAgentMessages();
      });
    }

    async function sendAgentContext(contextData) {
      const btn = el('agentSend');
      btn.disabled = true;
      btn.textContent = '分析中...';
      try {
        const payloadMessages = agentPayloadMessages();
        payloadMessages.push({
          role: 'user',
          content: `[系统提示：当前智能体类型为 ${agentTitle(agentKind)}，以下是当前页面上下文。请严格按这个智能体的职责处理，不要沿用其他模块逻辑。]\n` + JSON.stringify(contextData, null, 2)
        });
        const result = await api('/api/agent', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ kind: agentKind, messages: payloadMessages })
        });
        agentMessages.push({ role: 'assistant', content: result.reply });
        appendSkillResult(result);
        renderAgentMessages();
        try {
          const json = JSON.parse(result.reply);
          applyAgentResult(json);
          if (json.done) {
            const doneMsg = agentKind === 'diary' ? '日记已根据对话内容自动填充并保存，你可以在页面上查看和修改。' : '已根据对话内容自动生成并填充到表单中，你可以切换到"填写报告"查看和修改。';
            agentMessages.push({ role: 'assistant', content: doneMsg });
            renderAgentMessages();
          }
        } catch (e) { /* 继续对话 */ }
      } catch (err) {
        agentMessages.push({ role: 'assistant', content: '出错：' + err.message });
        renderAgentMessages();
      } finally {
        btn.disabled = false;
        btn.textContent = '发送';
      }
    }

    function startCurrentAgent() {
      startAgent(agentKindForTask(), true);
    }

    function openAgentFromAvatar() {
      el('agentWindow')?.classList.remove('hidden');
      bringAgentToFront();
      startCurrentAgent();
    }

    function startAgent(kind, reset = true) {
      const previousKind = agentKind;
      agentKind = kind;
      state.agentStage = 0;
      updateAgentChrome(kind);
      if (reset || !agentMessages.length || previousKind !== kind) agentMessages = [];
      toggleAgent(true);
      const currentData = getCurrentFormData(kind);
      const hasContent = kind === 'weekly'
        ? [currentData.weekly_summary, currentData.weekly_follow, currentData.weekly_next].some(hasRowContent)
        : kind === 'forum'
        ? Object.values(currentData).some(v => typeof v === 'string' && v.trim())
        : kind === 'news'
        ? Object.values(currentData).some(v => typeof v === 'string' && v.trim())
        : kind === 'mailassistant'
        ? Object.values(currentData).some(v => typeof v === 'string' && v.trim())
        : Object.values(currentData).some(v => v && String(v).trim());
      const intro = agentIntro(kind, hasContent);
      agentMessages.push({ role: 'assistant', type: 'intro', ...intro });
      renderAgentMessages();
    }

    async function sendAgentMessage(text) {
      if (!text.trim()) return;
      agentMessages.push({ role: 'user', content: text.trim() });
      renderAgentMessages();
      el('agentInput').value = '';
      const btn = el('agentSend');
      btn.disabled = true;
      btn.textContent = '思考中...';
      try {
        const currentData = getCurrentFormData(agentKind);
        const payloadMessages = agentPayloadMessages();
        if (Object.values(currentData).some(v => Array.isArray(v) ? v.length : v)) {
          payloadMessages.push({
            role: 'user',
            content: `[系统提示：当前智能体类型为 ${agentTitle(agentKind)}，以下是当前页面上下文。请严格按这个智能体的职责处理，不要沿用其他模块逻辑。]\n` + JSON.stringify(currentData, null, 2)
          });
        }
        const result = await api('/api/agent', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ kind: agentKind, messages: payloadMessages })
        });
        agentMessages.push({ role: 'assistant', content: result.reply });
        appendSkillResult(result);
        renderAgentMessages();
        try {
          const json = JSON.parse(result.reply);
          applyAgentResult(json);
          if (json.done) {
            const doneMsg = agentKind === 'diary' ? '日记已根据对话内容自动填充并保存，你可以在页面上查看和修改。' : '已根据对话内容自动生成并填充到表单中，你可以切换到"填写报告"查看和修改。';
            agentMessages.push({ role: 'assistant', content: doneMsg });
            renderAgentMessages();
          }
        } catch (e) { /* 继续对话 */ }
      } catch (err) {
        agentMessages.push({ role: 'assistant', content: '出错：' + err.message });
        renderAgentMessages();
      } finally {
        btn.disabled = false;
        btn.textContent = '发送';
      }
    }

    function getCurrentFormData(kind) {
      if (kind === 'weekly') {
        return {
          weekly_summary: collectWorkRows('summary'),
          weekly_follow: collectWorkRows('follow'),
          weekly_next: collectWorkRows('next')
        };
      }
      if (kind === 'diary') {
        return {
          today_work: el('diaryTodayWork').value,
          tomorrow_plan: el('diaryTomorrowPlan').value,
          thoughts: el('diaryThoughts').value
        };
      }
      if (kind === 'forum') {
        return {
          selected_topic_id: state.forumSelected || '',
          topic_title: document.querySelector('#forumTopicDetail .forum-topic-title')?.textContent || '',
          topic_detail: el('forumTopicDetail')?.innerText || '',
          comment_draft: el('forumCommentInput')?.value || '',
          create_title: el('forumTitle')?.value || '',
          create_body: el('forumBody')?.value || ''
        };
      }
      if (kind === 'news') {
        return {
          title: el('newsTitle')?.textContent || '',
          meta: el('newsMeta')?.textContent || '',
          summary: el('newsSummary')?.textContent || '',
          items: el('newsItems')?.innerText || '',
          keywords: el('newsKeywords')?.innerText || ''
        };
      }
      if (kind === 'mailassistant') {
        return {
          selected_mail: el('mailDetail')?.innerText || '',
          compose_to: el('assistantMailTo')?.value || '',
          compose_cc: el('assistantMailCc')?.value || '',
          compose_subject: el('assistantMailSubject')?.value || '',
          compose_body: el('assistantMailBody')?.value || ''
        };
      }
      if (kind === 'dashboard') {
        return {
          current_task: state.task || 'dashboard',
          current_page: el('taskTitle')?.textContent || '工作台',
          user: state.user?.name || state.user?.username || ''
        };
      }
      return {
        reporter: el('tripReporter').value,
        department: el('tripDepartment').value,
        location: el('tripLocation').value,
        trip_start: el('tripStart').value,
        trip_end: el('tripEnd').value,
        purpose: el('tripPurpose').value,
        itinerary: el('tripItinerary').value,
        details: el('tripDetails').value,
        issues: el('tripIssues').value,
        suggestions: el('tripSuggestions').value
      };
    }

    function hasRowContent(arr) {
      return Array.isArray(arr) && arr.some(r => Object.values(r).some(v => v && String(v).trim()));
    }

    function applyAgentResult(data) {
      if (agentKind === 'weekly') {
        if (hasRowContent(data.weekly_summary)) renderWorkRows('summary', data.weekly_summary);
        if (hasRowContent(data.weekly_follow)) renderWorkRows('follow', data.weekly_follow);
        if (hasRowContent(data.weekly_next)) renderWorkRows('next', data.weekly_next);
      } else if (agentKind === 'trip') {
        if (data.reporter !== undefined) el('tripReporter').value = data.reporter;
        if (data.department !== undefined) el('tripDepartment').value = data.department;
        if (data.location !== undefined) el('tripLocation').value = data.location;
        if (data.trip_start !== undefined) el('tripStart').value = data.trip_start;
        if (data.trip_end !== undefined) el('tripEnd').value = data.trip_end;
        if (data.purpose !== undefined) el('tripPurpose').value = data.purpose;
        if (data.itinerary !== undefined) el('tripItinerary').value = data.itinerary;
        if (data.details !== undefined) el('tripDetails').value = data.details;
        if (data.issues !== undefined) el('tripIssues').value = data.issues;
        if (data.suggestions !== undefined) el('tripSuggestions').value = data.suggestions;
        renderTripCards();
      } else if (agentKind === 'diary') {
        if (data.today_work !== undefined) el('diaryTodayWork').value = data.today_work;
        if (data.tomorrow_plan !== undefined) el('diaryTomorrowPlan').value = data.tomorrow_plan;
        if (data.thoughts !== undefined) el('diaryThoughts').value = data.thoughts;
        if (data.done) saveDiary();
      }
      highlightUpdatedFields();
    }

    function highlightUpdatedFields() {
      document.querySelectorAll('input, textarea, .work-block').forEach(el => {
        el.style.transition = 'box-shadow .4s ease';
        el.style.boxShadow = '0 0 0 2px #17736a40';
        setTimeout(() => { el.style.boxShadow = ''; }, 800);
      });
    }

    boot();

    function openAgentLightbox(src) {
      const box = document.getElementById('agentLightbox');
      const img = document.getElementById('agentLightboxImg');
      if (box && img) { img.src = src; box.classList.remove('hidden'); }
    }
    function closeAgentLightbox() {
      const box = document.getElementById('agentLightbox');
      if (box) box.classList.add('hidden');
    }
    (function() {
      const el = id => document.getElementById(id);
      const agentFloat = el('agentFloat');
      const agentToggle = el('agentToggle');
      const agentWindow = el('agentWindow');
      const agentHeader = agentWindow.querySelector('.agent-header');
      let suppressClickUntil = 0;

      agentToggle.addEventListener('click', event => {
        event.stopPropagation();
        if (Date.now() < suppressClickUntil) return;
        openAgentFromAvatar();
      });
      el('agentClose').addEventListener('click', () => toggleAgent(false));
      el('agentSend').addEventListener('click', () => sendAgentMessage(el('agentInput').value));
      el('agentInput').addEventListener('keydown', e => {
        if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
          e.preventDefault();
          sendAgentMessage(el('agentInput').value);
        }
      });
      if (typeof updateAgentChrome === 'function') updateAgentChrome(typeof agentKindForTask === 'function' ? agentKindForTask() : 'dashboard');
      if (typeof renderIcons === 'function') renderIcons(document);

      // 拖拽逻辑：拖按钮或标题栏都会移动整个 AI 助手，点击按钮只负责唤醒。
      (function() {
        let dragging = false;
        let moved = false;
        let startX = 0;
        let startY = 0;
        let initLeft = 0;
        let initTop = 0;
        let activePointerId = null;
        let pointerStartedOnToggle = false;

        function pointerDown(e) {
          if (e.target.closest('.agent-close') || e.target.closest('textarea') || e.target.closest('.agent-action') || e.target.closest('#agentSend')) return;
          bringAgentToFront();
          dragging = true;
          moved = false;
          activePointerId = e.pointerId;
          pointerStartedOnToggle = !!e.target.closest('#agentToggle');
          startX = e.clientX; startY = e.clientY;
          const rect = agentFloat.getBoundingClientRect();
          initLeft = rect.left; initTop = rect.top;
          agentFloat.style.right = 'auto';
          agentFloat.style.bottom = 'auto';
          agentFloat.style.left = initLeft + 'px';
          agentFloat.style.top = initTop + 'px';
          agentToggle.style.cursor = 'grabbing';
          agentHeader.style.cursor = 'grabbing';
          if (e.currentTarget.setPointerCapture) e.currentTarget.setPointerCapture(e.pointerId);
        }

        agentToggle.addEventListener('pointerdown', pointerDown);
        agentHeader.addEventListener('pointerdown', pointerDown);

        document.addEventListener('pointermove', e => {
          if (!dragging) return;
          if (activePointerId !== null && e.pointerId !== activePointerId) return;
          const dx = e.clientX - startX;
          const dy = e.clientY - startY;
          if (Math.abs(dx) > 4 || Math.abs(dy) > 4) {
            moved = true;
          }
          const rect = agentFloat.getBoundingClientRect();
          const maxLeft = window.innerWidth - Math.max(80, rect.width);
          const maxTop = window.innerHeight - Math.max(80, rect.height);
          const nextLeft = Math.max(8, Math.min(initLeft + dx, maxLeft));
          const nextTop = Math.max(8, Math.min(initTop + dy, maxTop));
          agentFloat.style.left = nextLeft + 'px';
          agentFloat.style.top = nextTop + 'px';
        });

        document.addEventListener('pointerup', e => {
          if (!dragging) return;
          if (activePointerId !== null && e.pointerId !== activePointerId) return;
          dragging = false;
          activePointerId = null;
          agentToggle.style.cursor = 'grab';
          agentHeader.style.cursor = 'move';
          if (moved) {
            suppressClickUntil = Date.now() + 250;
          } else if (pointerStartedOnToggle) {
            openAgentFromAvatar();
          }
          pointerStartedOnToggle = false;
        });
      })();
    })();
