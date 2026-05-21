// Skill catalog, admin configuration, user management, mailbox, and boot loaders.

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
      state.mailSignature = data.email_signature || '';
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

    function mailSignatureText() {
      return String(state.mailSignature || '').trim();
    }

    function appendMailSignatureText(body) {
      const text = String(body || '').trimEnd();
      const signature = mailSignatureText();
      if (!signature) return text;
      if (text.endsWith(signature)) return text;
      return text ? `${text}\n\n${signature}` : signature;
    }

    function ensureAssistantMailSignature(force = false) {
      const node = el('assistantMailBody');
      const signature = mailSignatureText();
      if (!node || !signature) return;
      if (force || !node.value.trim()) {
        node.value = appendMailSignatureText(node.value);
        renderAssistantMailPreview();
      }
    }

    async function refreshMailSignature() {
      if (!state.user) return '';
      const data = await api('/api/mail-config');
      state.mailSignature = data.email_signature || '';
      return state.mailSignature;
    }

    function clearAssistantMail() {
      el('assistantMailTo').value = '';
      el('assistantMailCc').value = '';
      el('assistantMailSubject').value = '';
      el('assistantMailBody').value = '';
      el('assistantMailFiles').value = '';
      state.assistantMailFiles = [];
      renderAssistantMailFiles();
      ensureAssistantMailSignature(true);
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
          await refreshMailSignature();
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
      setDefaultWeeklyDates();
      if (force) clearSavedFormDraft('weekly');
      try {
        const prefill = await api('/api/weekly-prefill');
        if (prefill.error) {
          state.weeklyPrefilled = true;
          el('status').textContent = prefill.error;
          el('status').className = 'status err';
          return;
        }
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
      } catch (err) {
        state.weeklyPrefilled = true;
        el('status').textContent = err.message || '历史周报预填失败';
        el('status').className = 'status err';
      }
    }

    async function loadTripPrefill(force = false) {
      if (!force && state.tripPrefilled) return;
      const today = new Date();
      const fmt = d => d.getFullYear() + '-' + String(d.getMonth()+1).padStart(2,'0') + '-' + String(d.getDate()).padStart(2,'0');
      const defaultStart = fmt(today);
      const defaultEnd = fmt(new Date(today.getTime() + 2*24*60*60*1000));
      if (force) clearSavedFormDraft('trip');
      try {
        const prefill = await api('/api/trip-prefill');
        if (prefill.error) {
          state.tripPrefilled = true;
          el('tripReporter').value = state.user?.name || state.user?.username || '';
          el('tripDepartment').value = '场景研究院';
          el('tripStart').value = defaultStart;
          el('tripEnd').value = defaultEnd;
          renderTripCards();
          el('status').textContent = prefill.error;
          el('status').className = 'status err';
          return;
        }
        el('tripReporter').value = state.user?.name || state.user?.username || prefill.reporter || '';
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
      } catch (err) {
        state.tripPrefilled = true;
        el('tripReporter').value = state.user?.name || state.user?.username || '';
        el('tripDepartment').value = '场景研究院';
        el('tripStart').value = defaultStart;
        el('tripEnd').value = defaultEnd;
        renderTripCards();
        el('status').textContent = err.message || '历史出差报告预填失败';
        el('status').className = 'status err';
      }
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
