"""Read-only browser fixture for knowledge layout and document polling."""
import os
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from playwright.sync_api import sync_playwright, expect

out = Path(os.environ['KB_ARTIFACT_DIR'])
out.mkdir(parents=True, exist_ok=True)
with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True, args=['--no-sandbox'])
    page = browser.new_page(viewport={'width': 1366, 'height': 768})
    errors = []
    deferred = []
    doc_requests = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    def api(route):
        url = route.request.url
        data = {'ok': True}
        if url.endswith('/session'):
            data = {'authenticated': True, 'user': {'username': 'test', 'name': '测试', 'role': 'superadmin', 'is_admin': True, 'is_superadmin': True, 'avatar_url': '', 'hobbies': []}, 'assistant_prompt': ''}
        elif '/knowledge/kbs' in url:
            data = {'provider': 'ragflow', 'kbs': [{'id': str(i), 'name': '测试企业知识库较长名称' + str(i), 'chunk_count': 10, 'document_count': 2} for i in range(6)]}
        elif '/knowledge/chat-sessions' in url:
            data = {'sessions': []}
        elif '/knowledge/chat-history' in url:
            data = {'messages': []}
        elif '/knowledge/list' in url:
            scope = parse_qs(urlparse(url).query)['scope'][0]
            doc_requests.append(scope)
            data = {'docs': [{'id': 'doc'+scope, 'name': '知识库'+scope+'的文档.pdf', 'status': 'parsing', 'progress': 25, 'chunk_count': 3}], 'embedding_model': '', 'provider': 'ragflow'}
            if scope == '2':
                deferred.append((route, data))
                return
        route.fulfill(json=data)
    page.route('**/api/**', api)
    page.goto('http://127.0.0.1:8765/workspace/knowledge')
    page.locator('.kb-chat-scope').wait_for()
    page.wait_for_timeout(1500)
    page.evaluate('''() => {
      window.samples = []; window.changes = 0;
      new MutationObserver(() => window.changes++).observe(document.querySelector('.kb-chat-scope'), {subtree:true,childList:true,attributes:true});
      let n=0; function sample() {
        const e=document.querySelector('.kb-chat-scope');
        window.samples.push([e.clientWidth,e.clientHeight,document.querySelector('.kb-stage').clientWidth]);
        if (++n<300) requestAnimationFrame(sample);
      } sample();
    }''')
    page.wait_for_timeout(5500)
    sizes = page.evaluate('[...new Set(window.samples.map(JSON.stringify))]')
    changes = page.evaluate('window.changes')
    print('ERRORS', errors[:10], 'SIZES', sizes, 'LAYOUT MUTATIONS', changes)
    for width in (1920, 1600, 1280, 1100, 1024, 900, 768, 390):
        page.set_viewport_size({'width': width, 'height': 900})
        page.wait_for_timeout(1200)
        print('WIDTH', width, 'ERRORS', errors[-2:])
    page.set_viewport_size({'width': 1366, 'height': 768})
    page.locator('.kb-kbs-item').nth(2).click()
    page.wait_for_timeout(200)
    assert deferred
    page.locator('.kb-kbs-item').nth(3).click()
    expect(page.locator('.kb-doc strong')).to_have_text('知识库3的文档.pdf')
    for route, data in deferred:
        route.fulfill(json=data)
    page.wait_for_timeout(300)
    expect(page.locator('.kb-doc strong')).to_have_text('知识库3的文档.pdf')
    page.screenshot(path=str(out/'knowledge-stability.png'))
    assert not errors, errors[:10]
    assert len(sizes) == 1, sizes
    assert changes < 20, changes
    page.get_by_role('button', name='首页', exact=True).click()
    page.wait_for_timeout(500)
    count = len(doc_requests)
    page.wait_for_timeout(4500)
    assert len(doc_requests) == count, 'Knowledge polling continued after leaving'
    print('PASS: stable layout, stale responses ignored, polling pauses after leaving')
    browser.close()
