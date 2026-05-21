// Application boot call, lightbox helpers, and draggable agent shell.

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
        if (typeof openAgentFromAvatar === 'function') openAgentFromAvatar();
        else if (typeof toggleAgent === 'function') toggleAgent();
      });
      el('agentClose').addEventListener('click', () => {
        if (typeof toggleAgent === 'function') toggleAgent(false);
        else el('agentWindow')?.classList.add('hidden');
      });
      el('agentSend').addEventListener('click', () => {
        if (typeof sendAgentMessage === 'function') sendAgentMessage(el('agentInput').value);
      });
      el('agentInput').addEventListener('keydown', e => {
        if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
          e.preventDefault();
          if (typeof sendAgentMessage === 'function') sendAgentMessage(el('agentInput').value);
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
          }
          pointerStartedOnToggle = false;
        });
      })();
    })();
