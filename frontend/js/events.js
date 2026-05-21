// DOM event wiring for navigation, forms, uploads, settings, and primary actions.

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
            body: appendMailSignatureText(el('assistantMailBody').value),
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
        state.mailSignature = result.mail_config.email_signature || '';
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
