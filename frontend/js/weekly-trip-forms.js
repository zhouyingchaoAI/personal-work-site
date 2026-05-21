// Weekly report rows, modal editing, draft persistence, and trip forms.

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
            tripReporter: state.user?.name || state.user?.username || draft.trip.reporter,
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
