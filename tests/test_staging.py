import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
from streamlit.testing.v1 import AppTest
from staging.launch import configuration, memory

class StagingTests(unittest.TestCase):
    def test_default_ignores_private_mount(self):
        with patch.object(Path, 'read_text', side_effect=AssertionError('must not read secrets')):
            self.assertEqual(configuration({}), '[v653]\nmode = "synthetic_preview"\n')
    def test_private_requires_approval(self):
        with self.assertRaises(ValueError): configuration({'STHO_STAGING_MODE':'private'})
    def test_budget_and_viewer_guard(self):
        for env in ({'STHO_MONTHLY_COMPUTE_USD':'25'}, {'STHO_VIEWERS':'2'}, {'STHO_STAGING_MODE':'typo'}):
            with self.assertRaises(ValueError): configuration(env)
    def test_private_rejects_multiple_viewers(self):
        with patch.object(Path,'read_text',return_value='[v653]\nmode="private"\nallowed_emails=["a","b"]'):
            with self.assertRaises(ValueError): configuration({'STHO_STAGING_MODE':'private','STHO_PRIVATE_APPROVAL':'OWNER_APPROVED'})
    def test_missing_metrics_are_unknown(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(memory(999,Path(d),Path(d)),dict(rss_bytes=None,cgroup_current_bytes=None,cgroup_limit_bytes=None))
    def test_metrics_units_and_unlimited(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);(p/'1').mkdir();(p/'1/status').write_text('VmRSS: 123 kB\n');(p/'memory.current').write_text('456');(p/'memory.max').write_text('max')
            self.assertEqual(memory(1,p,p),dict(rss_bytes=125952,cgroup_current_bytes=456,cgroup_limit_bytes=None))
    def test_staging_preview_has_no_adapter_calls(self):
        with patch('v653.ui.load_latest',side_effect=AssertionError('network forbidden')):
            app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'staging/app.py')).run()
            self.assertFalse(app.exception)
            self.assertTrue(any('SYNTHETIC PREVIEW' in x.value for x in app.info))

    def test_launcher_serves_payload_free_health(self):
        import os, socket, subprocess, sys, time, urllib.request
        with socket.socket() as sock:
            sock.bind(('127.0.0.1',0)); port=sock.getsockname()[1]
        with tempfile.TemporaryFile() as log:
            child=subprocess.Popen([sys.executable,'staging/launch.py'],env=dict(os.environ,PORT=str(port),STHO_STAGING_MODE='synthetic_preview'),stdout=log,stderr=log)
            try:
                deadline=time.monotonic()+20
                while True:
                    try:
                        with urllib.request.urlopen('http://127.0.0.1:'+str(port)+'/_stcore/health',timeout=1) as response:
                            self.assertEqual(response.status,200); self.assertEqual(response.read(),b'ok')
                        break
                    except OSError:
                        if time.monotonic()>deadline or child.poll() is not None: self.fail('local health failed')
                        time.sleep(.1)
            finally:
                child.terminate()
                try: child.wait(timeout=8)
                except subprocess.TimeoutExpired: child.kill();child.wait()
