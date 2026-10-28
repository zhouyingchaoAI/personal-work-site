import json
from pathlib import Path
import unittest
from unittest.mock import patch
from backend import runtime as rt


class TicketMcpTests(unittest.TestCase):
    def setUp(self):
        self.user = patch.object(rt, 'find_user', side_effect=lambda username: {'name': '研发', 'role': 'member'} if username == 'dev' else None)
        self.user.start()
        self.addCleanup(self.user.stop)
        self.rows = [
            {'id':'one','title':'布局','body':'对齐','module':'联指经营助手','author':'成员','updated_at':'2026-10-23T10:00:00','comments':[]},
            {'id':'two','title':'邮件','body':'异常','module':'邮件助手','author':'成员','updated_at':'2026-10-23T11:00:00','comments':[]},
        ]

    def test_discovery(self):
        names = {tool['name']: tool for tool in rt._mcp_tools_list()}
        for name in ('tickets.list', 'tickets.get', 'tickets.reply', 'tickets.image'):
            self.assertIn(name, names)
        self.assertEqual(names['tickets.reply']['inputSchema']['properties']['confirm']['type'], 'boolean')

    def test_live_list_pagination_and_filters(self):
        with patch.object(rt, 'load_tickets', return_value=self.rows):
            first = rt.ticket_mcp_tool('tickets.list', {'limit':1}, 'dev')
            self.assertEqual(first['next_offset'], 1)
            self.assertEqual(rt.ticket_mcp_tool('tickets.list', {'offset':1}, 'dev')['tickets'][0]['id'], 'two')
            self.assertEqual(rt.ticket_mcp_tool('tickets.list', {'module':'联指经营助手'}, 'dev')['total'], 1)
            self.assertEqual(rt.ticket_mcp_tool('tickets.list', {'updated_since':'2026-10-23T11:00:00'}, 'dev')['total'], 1)
            self.rows.append({**self.rows[0], 'id':'three'})
            self.assertEqual(rt.ticket_mcp_tool('tickets.list', {}, 'dev')['total'], 3)

    def test_details_do_not_write(self):
        with patch.object(rt, 'load_tickets', return_value=self.rows), patch.object(rt, 'save_tickets') as save:
            detail = rt.ticket_mcp_tool('tickets.get', {'id':'one'}, 'dev')['ticket']
            self.assertIn('comments', detail)
            save.assert_not_called()

    def test_unresolved_with_module(self):
        rows = [{**self.rows[0], 'id': status, 'comments': [{'status': status}]} for status in ('open', 'accepted', 'resolved', 'rejected')]
        rows.append(self.rows[1])
        with patch.object(rt, 'load_tickets', return_value=rows):
            result = rt.ticket_mcp_tool('tickets.list', {'module': '联指经营助手', 'status': 'unresolved'}, 'dev')
            self.assertEqual({item['id'] for item in result['tickets']}, {'open', 'accepted'})
            self.assertEqual(result['total'], 2)
            self.assertEqual(rt.ticket_mcp_tool('tickets.list', {'status': 'unresolved'}, 'dev')['total'], 3)
            self.assertEqual(rt.ticket_mcp_tool('tickets.list', {'status': 'open', 'module': '联指经营助手'}, 'dev')['total'], 1)
            self.assertEqual(rt.ticket_mcp_tool('tickets.list', {'status': 'unresolved', 'module': '不存在'}, 'dev')['total'], 0)

    def test_image_membership_and_reply_attachments(self):
        self.rows[0]['comments'] = [{'attachments':[{'id':'shot','name':'截图.png'}]}]
        with patch.object(rt, 'load_tickets', return_value=self.rows), patch.object(rt, 'forum_attachment_entry', return_value=(Path('shot.png'), 100)):
            result = rt.ticket_mcp_tool('tickets.image', {'id':'one','attachment_id':'shot'}, 'dev')
            self.assertNotIn('data', result)
            with self.assertRaises(PermissionError):
                rt.ticket_mcp_tool('tickets.image', {'id':'two','attachment_id':'shot'}, 'dev')
            with self.assertRaises(ValueError):
                rt.ticket_mcp_tool('tickets.image', {'id':'one','attachment_id':'../shot'}, 'dev')

    def test_mcp_image_content_and_unsupported_files(self):
        metadata = {'ok':True,'ticket_id':'one','attachment_id':'shot','name':'截图.png','size':10}
        with patch.object(rt, 'execute_skill', return_value=metadata), patch.object(rt, 'forum_attachment_content', return_value=(Path('shot.png'),b'\x89PNG\r\n\x1a\n123')):
            result = rt._mcp_call_tool('tickets.image', {'id':'one','attachment_id':'shot'}, 'dev')
            self.assertEqual(result['content'][1]['type'], 'image')
            self.assertEqual(result['content'][1]['mimeType'], 'image/png')
        with patch.object(rt, 'forum_attachment_content', return_value=(Path('fake.png'),b'<html>fake</html>')):
            with self.assertRaises(ValueError):
                rt.ticket_mcp_image_content(metadata)

    def test_reply_auth_confirmation_status(self):
        with self.assertRaises(PermissionError):
            rt.ticket_mcp_tool('tickets.list', {}, '')
        with self.assertRaises(ValueError):
            rt.ticket_mcp_tool('tickets.reply', {'id':'one','content':'修复中'}, 'dev')
        with self.assertRaises(PermissionError):
            rt.ticket_mcp_tool('tickets.reply', {'id':'one','content':'完成','confirm':True,'status':'resolved'}, 'dev')
        with patch.object(rt, 'ticket_add_comment', return_value={'ok':True}) as reply:
            rt.ticket_mcp_tool('tickets.reply', {'id':'one','content':'修复中','confirm':True}, 'dev')
            self.assertEqual(reply.call_args.args[0]['status'], '')
            self.assertEqual(reply.call_args.args[1], 'dev')
        with self.assertRaises(ValueError):
            rt.ticket_mcp_tool('tickets.list', {'limit':101}, 'dev')

    def test_mcp_transport_auth_and_audited_dispatch(self):
        request = json.dumps({'jsonrpc':'2.0','id':1,'method':'tools/call','params':{'name':'tickets.list','arguments':{}}}).encode()
        with patch.object(rt, '_mcp_secret', return_value='test-secret'), patch.object(rt, 'execute_skill', return_value={'ok':True,'tickets':[]}) as execute:
            self.assertEqual(rt.mcp_handle_post('', 'dev', request)[0], 401)
            status, result = rt.mcp_handle_post('Bearer test-secret', 'dev', request)
            self.assertEqual(status, 200)
            self.assertNotIn('isError', result['result'])
            execute.assert_called_once_with('tickets.list', {}, 'dev', source='mcp')
