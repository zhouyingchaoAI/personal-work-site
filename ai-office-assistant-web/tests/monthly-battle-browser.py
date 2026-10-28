import argparse
from pathlib import Path
from playwright.sync_api import sync_playwright

parser = argparse.ArgumentParser()
parser.add_argument('--artifacts', required=True)
output = Path(parser.parse_args().artifacts)
output.mkdir(parents=True, exist_ok=True)
stages = ['初步设计阶段', '项目概算阶段', '初步设计评审阶段', '用户需求书引导阶段', '控制价确认阶段', '招标时间确认阶段', '招标公示阶段', '招投标阶段', '中标谈判（第三方谈判）', '合同条款沟通阶段', '合同签订']
item = dict(id='test', month='2026-11', code='A1', name='轨道通信测试项目', owner='负责人', manager='负责人', assignees=['me'], region='东区-江苏', target='完成阶段11合同签订', target_stage=11, amount=100, tag='推进', stage=11, stage_source='import', cadence=2, completed=False, revision=1, events=[], stage_days={}, overdue=True, last_at='2026-10-26T10:00:00', can_update=True, sources=[], conflicts=[], missing_code=False)
with sync_playwright() as playwright:
    browser = playwright.chromium.launch()
    page = browser.new_page(viewport={'width': 1440, 'height': 1000})
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.route('**/crm/monthly-battle*', lambda route: route.fulfill(json={'ok': True, 'items': [item], 'stages': stages, 'can_import': True, 'scope': {'level': 'company', 'label': '管理者视图 · 全部任务'}, 'view_options': {'regions': ['东区', '西区'], 'users': [{'username': 'me', 'name': '负责人'}]}}))
    calls = []
    def save(route):
        data = route.request.post_data_json
        calls.append(data)
        from_stage = item['stage']
        item.update(stage=data['stage'], revision=2, overdue=False)
        item['events'].append(dict(id='event', at='2026-10-26T15:00:00', author='负责人', from_stage=from_stage, stage=data['stage'], completed=False, content=data['content'], next_action=data['next_action'], attachments=[]))
        route.fulfill(json={'ok': True})
    page.route('**/crm/monthly-battle/progress', save)
    page.goto('http://127.0.0.1:5179/personal-office-assistant/tests/fixtures/monthly-battle.html')
    page.locator('.mb-project').wait_for()
    assert page.locator('.mb-stage').count() == 12
    assert page.locator('.mb-compact-summary').is_visible()
    assert page.locator('.mb-command').count() == 0
    assert not page.locator('.mb-distribution').evaluate('(element) => element.open')
    assert '100' in page.locator('.mb-table .mb-money').inner_text()
    page.locator('.mb-distribution > summary').click()
    assert '1 个' in page.locator('.mb-stage').nth(11).inner_text()
    page.locator('.mb-distribution > summary').click()
    assert '11 · 合同签订' in page.locator('.mb-table').inner_text()
    page.screenshot(path=str(output / 'monthly-battle-board.png'), full_page=True)
    page.locator('.mb-project').click()
    assert page.locator('.mb-quantified').is_visible()
    assert page.get_by_role('button', name='保存本次推进').count() == 0
    assert page.locator('.el-dialog .el-form').count() == 0
    assert not page.locator('.mb-original-strip').evaluate('(element) => element.open')
    page.screenshot(path=str(output / 'readonly-progress.png'), full_page=True)
    page.locator('.el-dialog__headerbtn').click()
    page.get_by_role('dialog').wait_for(state='hidden')
    page.get_by_role('button', name='变更阶段', exact=True).click()
    page.locator('.el-form-item').filter(has_text='变更后的阶段').locator('.el-select').click()
    page.get_by_role('option', name='1. 初步设计阶段', exact=True).click()
    page.get_by_placeholder('说明为什么调整阶段、依据是什么；首次确认也需要说明').fill('客户确认进入初设阶段')
    assert page.get_by_placeholder('下一步联系谁、做什么、计划何时完成').count() == 0
    assert page.locator('.mb-upload-zone').count() == 0
    page.get_by_role('button', name='确认变更阶段').click()
    page.get_by_role('dialog').wait_for(state='hidden')
    assert calls[-1]['stage'] == 1
    page.get_by_role('button', name='＋ 登记动作', exact=True).click()
    assert page.locator('.mb-register-context').is_visible()
    assert '登记日期（北京时间）' in page.locator('.mb-registration-date').inner_text()
    assert '保存时自动记录实际提交时间' in page.locator('.mb-registration-date').inner_text()
    assert page.get_by_placeholder('说明为什么调整阶段、依据是什么；首次确认也需要说明').count() == 0
    page.get_by_placeholder('沟通对象、采取的动作、反馈结果、阻碍事项；阶段变化请说明依据').fill('继续核对接口细节，阶段不变')
    page.get_by_placeholder('下一步联系谁、做什么、计划何时完成').fill('明日反馈接口清单')
    page.get_by_role('button', name='保存本次推进').click()
    page.get_by_role('dialog').wait_for(state='hidden')
    assert len(calls) == 2 and calls[-1]['stage'] == 1
    page.locator('.mb-project').click()
    assert page.locator('.mb-timeline .mb-action').count() == 2
    assert page.locator('.el-dialog .el-form').count() == 0
    assert page.locator('.mb-state-node.current').count() == 1
    page.screenshot(path=str(output / 'readonly-timeline.png'), full_page=True)
    assert not errors, errors
    browser.close()
    print('PASS stages, unknown baseline, progress record, timeline and board update')
