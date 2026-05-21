// Diary, forum, and news page behavior.

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
        renderDiaryList();
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
    function renderNewsHistory(history = [], activeDate = '') {
      const list = el('newsHistoryList');
      if (!list) return;
      el('newsHistoryMeta').textContent = history.length ? `已保存 ${history.length} 期每日资讯。` : '暂无历史资讯。';
      if (!history.length) {
        list.innerHTML = '<div class="forum-empty">暂无历史资讯，生成后会自动保存。</div>';
        return;
      }
      list.innerHTML = history.map(item => `
        <div class="news-item news-history-item ${item.date === activeDate ? 'active' : ''}" data-date="${escapeHtml(item.date || '')}">
          <div class="news-history-date">${escapeHtml(item.date || '')}</div>
          <div class="news-history-main">
            <div class="news-item-title">${escapeHtml(item.title || item.date || '每日资讯')}</div>
            <div class="news-history-summary">${escapeHtml(item.summary || '暂无摘要。')}</div>
          </div>
          <div class="news-history-count">${item.item_count || 0} 条</div>
        </div>
      `).join('');
      list.querySelectorAll('.news-history-item').forEach(item => {
        item.addEventListener('click', () => loadNewsIssueByDate(item.dataset.date));
      });
    }
    async function loadNewsIssueByDate(date) {
      if (!date) return;
      try {
        const data = await api('/api/news/history?date=' + encodeURIComponent(date));
        renderNewsIssue(data.issue);
        renderNewsHistory(data.history || [], data.issue?.date || date);
      } catch (err) {
        el('newsConfigStatus').textContent = err.message;
        el('newsConfigStatus').className = 'status err';
      }
    }
    function setNewsConfigCollapsed(collapsed) {
      const body = el('newsConfigBody');
      const button = el('newsConfigToggle');
      if (!body || !button) return;
      body.classList.toggle('hidden', collapsed);
      button.textContent = collapsed ? '展开' : '收起';
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
        renderNewsHistory(data.history || [], data.issue?.date || '');
        setNewsConfigCollapsed(true);
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
    el('newsConfigToggle').addEventListener('click', () => {
      setNewsConfigCollapsed(el('newsConfigBody').classList.contains('hidden') ? false : true);
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
        const latest = await api('/api/news/history');
        renderNewsHistory(latest.history || [], result.issue?.date || '');
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
