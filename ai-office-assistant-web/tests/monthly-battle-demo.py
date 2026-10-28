import argparse
from pathlib import Path
from datetime import datetime, timedelta
from playwright.sync_api import sync_playwright

parser = argparse.ArgumentParser()
parser.add_argument('--artifacts', required=True)
output = Path(parser.parse_args().artifacts)
output.mkdir(parents=True, exist_ok=True)
stages = ['初步设计阶段', '项目概算阶段', '初步设计评审阶段', '用户需求书引导阶段', '控制价确认阶段', '招标时间确认阶段', '招标公示阶段', '招投标阶段', '中标谈判（第三方谈判）', '合同条款沟通阶段', '合同签订']
item = dict(id='demo', month='2026-11', code='DEMO-001', name='【模拟演示】轨道通信项目', owner='演示商务经理', manager='演示商务经理', assignees=['demo'], region='东区-江苏', target='完成阶段7招标公示', target_stage=7, amount=1069, tag='推进', stage=7, stage_source='import', cadence=1, completed=False, revision=1, events=[], stage_days={}, overdue=False, last_at='', can_update=True, sources=[], conflicts=[], missing_code=False)
actions = [
    (1, '与设计院沟通设备清单，确认接口范围。', '次日提交初设方案'),
    (1, '客户反馈新增两项接口，已更新方案并发送确认。', '明日与造价单位核对概算'),
    (2, '与造价单位核对清单，概算进入评审准备。', '提交评审材料'),
    (3, '完成初设评审沟通，形成三项整改意见。', '与客户确认整改范围'),
    (2, '客户调整数量，退回概算阶段重新核价。', '次日提交修订概算'),
]
with sync_playwright() as api:
    browser = api.chromium.launch()
    page = browser.new_page(viewport={'width':1440,'height':1100})
    proof = browser.new_page(viewport={'width':800,'height':450})
    proof.set_content('<body style="font-family:sans-serif;padding:40px;background:#eef5ff;color:#234"><h1>模拟沟通截图 · 非真实客户资料</h1><p>商务经理：设备清单已提交，请确认接口范围。</p><p>演示客户：收到，请补充接口与预算说明。</p><hr><p>仅用于验证附件上传、缩略图与状态树联动。</p></body>')
    proof.screenshot(path=str(output/'demo-communication.png'))
    proof.close()
    attachment = dict(id='demo-image', name='模拟沟通截图.png', is_image=True, url='/demo-communication.png')
    page.route('**/demo-communication.png', lambda route: route.fulfill(path=str(output/'demo-communication.png'), content_type='image/png'))
    uploads = []
    def upload(route):
        uploads.append(route.request.method)
        route.fulfill(json={'ok':True,'attachment':attachment})
    page.route('**/forum/attachment', upload)
    page.route('**/crm/monthly-battle*', lambda route: route.fulfill(json={'ok':True,'items':[item],'stages':stages,'can_import':False,'scope':{'level':'personal','label':'模拟个人视图'},'view_options':None}))
    def save(route):
        payload = route.request.post_data_json
        index = len(item['events'])
        stamp = (datetime.now() - timedelta(days=4-index)).replace(hour=10, minute=0, second=0, microsecond=0).isoformat()
        item['events'].append(dict(id='event-'+str(index), at=stamp, author='演示商务经理', from_stage=item['stage'], stage=payload['stage'], completed=False, content=payload['content'], next_action=payload['next_action'], attachments=payload['attachments']))
        item.update(stage=payload['stage'], revision=item['revision']+1, last_at=stamp, stage_days={'1':2,'2':1,'3':1})
        route.fulfill(json={'ok':True})
    page.route('**/crm/monthly-battle/progress', save)
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.goto('http://127.0.0.1:5179/personal-office-assistant/tests/fixtures/monthly-battle.html')
    page.locator('.mb-project').click()
    for stage, content, next_action in actions:
        page.locator('.el-form-item').filter(has_text='当前阶段（无变化请保持）').locator('.el-select').click()
        page.get_by_role('option', name=str(stage)+'. '+stages[stage-1], exact=True).click()
        if stage != item['stage']:
            page.get_by_placeholder('说明为什么调整阶段、依据是什么；首次确认也需要说明').fill('模拟阶段依据：' + content)
        page.get_by_placeholder('沟通对象、采取的动作、反馈结果、阻碍事项；阶段变化请说明依据').fill(content)
        page.get_by_placeholder('下一步联系谁、做什么、计划何时完成').fill(next_action)
        page.locator('input[type=file][multiple]').set_input_files(str(output/'demo-communication.png'))
        page.locator('.mb-images .el-button').last.wait_for()
        page.get_by_role('button', name='保存本次推进').click()
        page.get_by_text('每日推进时间线 · '+str(len(item['events']) or 1)+' 条')
        page.wait_for_function('document.querySelectorAll(".mb-timeline .mb-action").length === '+str(actions.index((stage, content, next_action))+1))
    assert len(uploads) == 5
    assert len(item['events']) == 5
    assert all(len(event['attachments']) == 1 for event in item['events'])
    assert '02' in page.locator('.mb-state-node.current').inner_text()
    page.locator('.mb-state-tree').scroll_into_view_if_needed()
    page.screenshot(path=str(output/'demo-state-tree.png'))
    page.get_by_role('button', name='查看全部阶段', exact=True).click()
    page.locator('.mb-state-node').nth(1).click()
    assert page.locator('.mb-timeline .mb-action').count() == 3
    assert '阶段回退' in page.locator('.mb-timeline').inner_text()
    page.locator('.mb-timeline').scroll_into_view_if_needed()
    page.screenshot(path=str(output/'demo-action-timeline.png'))
    page.locator('.mb-timeline .ticket-attachment-preview').first.click()
    page.locator('.el-image-viewer__wrapper').wait_for()
    page.screenshot(path=str(output/'demo-image-preview.png'))
    assert not errors, errors
    browser.close()
print('PASS 5 daily uploads, 5 screenshots, same-stage actions, advance, rollback, stage filtering and image preview; no production writes')
