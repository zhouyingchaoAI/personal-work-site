from pathlib import Path
import unittest


class ContractLayoutTests(unittest.TestCase):
    def test_contract_detail_has_separate_persistent_sections(self):
        source = (Path(__file__).resolve().parents[2] / 'ai-office-assistant-web/src/views/LedgerAssistantView/ContractWorkbench.vue').read_text()
        for section in ('basic', 'lines', 'payments', 'generate'):
            self.assertIn(f'v-show="detailTab === \'{section}\'"', source)
        self.assertIn('v-model="detailTab"', source)
        self.assertIn('class="contract-save-bar"', source)
        self.assertNotIn('<details open>', source)
