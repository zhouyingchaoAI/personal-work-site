// OpenClaw lobster base integration. The assistant session exchanges for an OpenClaw token server-side.

let lobsterLoaded = false;
let lobsterLoadSeq = 0;

async function loadOpenClawBase(force = false) {
  const status = el('lobsterStatus');
  const frame = el('lobsterFrame');
  const link = el('lobsterOpenLink');
  if (!status || !frame) return;
  if (lobsterLoaded && !force) return;
  const seq = ++lobsterLoadSeq;
  status.textContent = '正在使用办公助手账号登录龙虾平台...';
  status.className = 'status';
  try {
    const result = await api('/api/openclaw-sso');
    if (!result.ok || !result.token) throw new Error(result.error || '龙虾平台未返回登录凭据');
    if (seq !== lobsterLoadSeq) return;
    const url = String(result.url || 'https://yfdemo.chencytech.com/openclaw/').replace(/\/$/, '/');
    localStorage.setItem('openclaw_token', result.token);
    document.cookie = 'openclaw_token=' + encodeURIComponent(result.token) + '; path=/; SameSite=Lax';
    const sep = url.includes('?') ? '&' : '?';
    const nextSrc = url + sep + 'embed=1&from=personal-office-assistant&ts=' + Date.now() + '#token=' + encodeURIComponent(result.token);
    if (force) {
      frame.src = 'about:blank';
      await new Promise(resolve => setTimeout(resolve, 30));
      if (seq !== lobsterLoadSeq) return;
    }
    frame.src = nextSrc;
    if (link) link.href = url + '#token=' + encodeURIComponent(result.token);
    lobsterLoaded = true;
    status.textContent = '已使用当前办公助手账号进入龙虾基地。';
    status.className = 'status ok';
  } catch (err) {
    if (seq !== lobsterLoadSeq) return;
    status.textContent = err.message;
    status.className = 'status err';
  }
}
