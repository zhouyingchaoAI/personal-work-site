import unittest
from unittest.mock import patch
from backend import runtime as rt


class SignatureInlineTests(unittest.TestCase):
    def test_company_logo_is_embedded_in_mime(self):
        signature = '<img src="https://mail.263.net/a/mailInnerFileDownloadImg?id=old">'
        with patch.object(rt, 'smtp_settings_for_account', return_value={'from_addr': 'sender@example.com'}), patch.object(rt, 'user_mail_config', return_value={'email_signature': signature}):
            message = rt.build_message({'to': 'recipient@example.com', 'body': '正文'})
        html = next(part.get_content() for part in message.walk() if part.get_content_type() == 'text/html')
        self.assertIn('cid:signature-', html)
        self.assertNotIn('mailInnerFileDownloadImg', html)
        self.assertNotIn('◈ CHENCY', html)
        images = [part for part in message.walk() if part.get_content_maintype() == 'image']
        self.assertEqual(len(images), 1)
        self.assertEqual(images[0].get_content_disposition(), 'inline')
        self.assertTrue(images[0].get_payload(decode=True).startswith(b'\x89PNG'))
        self.assertEqual(images[0].get_payload(decode=True), (rt.BASE_DIR / 'backend/assets/company-signature-original.png').read_bytes())
        self.assertNotIn('<table', html)
        self.assertIn(images[0]['Content-ID'].strip('<>'), html)

    def test_custom_signature_image_preserved(self):
        signature = '<img src="data:image/png;base64,aGVsbG8=">'
        with patch.object(rt, 'smtp_settings_for_account', return_value={'from_addr': 'sender@example.com'}), patch.object(rt, 'user_mail_config', return_value={'email_signature': signature}):
            message = rt.build_message({'to': 'recipient@example.com', 'body': '正文'})
        images = [part for part in message.walk() if part.get_content_maintype() == 'image']
        self.assertEqual(images[0].get_payload(decode=True), b'hello')
