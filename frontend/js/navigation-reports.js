// Navigation, report lists, recent documents, and history views.

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
        ensureAssistantMailSignature();
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
