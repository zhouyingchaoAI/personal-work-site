import unittest
from unittest.mock import patch

from backend import runtime as rt


class MonitoringTests(unittest.TestCase):
    def setUp(self):
        self.inst = {'id': 'ragflow-mysql', 'kind': 'mysql', 'host': 'example', 'port': 3306}

    def test_mysql_probe_uses_authenticated_query_without_raw_socket(self):
        with patch.object(rt, '_dcdb_mysql_run', return_value=[]) as query, patch.object(rt.socket, 'create_connection', side_effect=AssertionError('raw handshake')):
            self.assertTrue(rt._dcdb_probe_host(self.inst))
        query.assert_called_once_with(self.inst, None, [('SELECT 1', None)])

    def test_overview_uses_registered_mysql_probe(self):
        with patch.object(rt, '_dcdb_inst', return_value=self.inst), patch.object(rt, '_dcdb_probe_host', return_value=True) as probe, patch.object(rt.socket, 'create_connection', side_effect=AssertionError('raw handshake')):
            self.assertEqual(rt._datacenter_probe('example', 3306, 'ragflow-mysql'), 'up')
        probe.assert_called_once_with(self.inst)

    def test_mysql_sampler_does_not_preflight_raw_connection(self):
        with patch.object(rt, '_dcdb_probe_host', side_effect=AssertionError('redundant preflight')), patch.dict(rt._DCFLOW_SAMPLERS, {'mysql': lambda inst: ({'连接失败': 0}, {}, [])}), patch.dict(rt._dcflow_last, {}, clear=True):
            alerts = []
            result = rt._dcflow_sample_instance(self.inst, alerts)
        self.assertEqual(result['status'], 'up')
        self.assertEqual(alerts, [])

    def test_real_mysql_sampling_errors_are_still_alerted(self):
        def fail(inst):
            raise ConnectionError('unavailable')
        with patch.dict(rt._DCFLOW_SAMPLERS, {'mysql': fail}):
            alerts = []
            result = rt._dcflow_sample_instance(self.inst, alerts)
        self.assertEqual(result['status'], 'auth-error')
        self.assertEqual(alerts[0]['code'], 'sample-error')
