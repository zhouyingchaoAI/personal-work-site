// Mail review/send flow and floating AI agent behavior.

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

