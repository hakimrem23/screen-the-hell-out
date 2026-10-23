"""Manual staging runtime; no provisioning, deployment API or secret logging."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import tomllib

ROOT = Path(__file__).resolve().parents[1]

def configuration(env):
    if env.get('STHO_MONTHLY_COMPUTE_USD', '7') != '7' or env.get('STHO_VIEWERS', '1') != '1':
        raise ValueError('STAGING_BUDGET_OR_VIEWER_POLICY')
    mode = env.get('STHO_STAGING_MODE', 'synthetic_preview')
    if mode == 'synthetic_preview':
        # Ignore mounted private settings entirely in the default mode.
        return '[v653]\nmode = "synthetic_preview"\n'
    if mode != 'private' or env.get('STHO_PRIVATE_APPROVAL') != 'OWNER_APPROVED':
        raise ValueError('PRIVATE_STAGING_NOT_APPROVED')
    body = Path('/etc/secrets/staging-secrets.toml').read_text()
    data = tomllib.loads(body)
    viewers = data.get('v653', {}).get('allowed_emails', [])
    if data.get('v653', {}).get('mode') != 'private' or len(viewers) != 1:
        raise ValueError('SINGLE_VIEWER_REQUIRED')
    # Existing authorization enforces all other identity and source controls.
    return body

def memory(pid, proc=Path('/proc'), cgroup=Path('/sys/fs/cgroup')):
    def integer(path):
        try: return int(path.read_text().strip())
        except (OSError, ValueError): return None
    try:
        line = next(x for x in (proc/str(pid)/'status').read_text().splitlines() if x.startswith('VmRSS:'))
        rss = int(line.split()[1]) * 1024
    except (OSError, ValueError, StopIteration): rss = None
    return {'rss_bytes': rss, 'cgroup_current_bytes': integer(cgroup/'memory.current'),
            'cgroup_limit_bytes': integer(cgroup/'memory.max')}

def main():
    try: body = configuration(os.environ)
    except Exception: raise SystemExit('STAGING_CONFIGURATION_REJECTED') from None
    port = os.environ.get('PORT', '8501')
    if not port.isdigit() or not 1024 <= int(port) <= 65535: raise SystemExit('INVALID_PORT')
    # Fresh HOME prevents inherited Streamlit secrets from entering this service.
    with tempfile.TemporaryDirectory(prefix='stho-staging-') as folder:
        home = Path(folder); settings = home/'.streamlit'; settings.mkdir(mode=0o700)
        secret = settings/'secrets.toml'; secret.write_text(body); secret.chmod(0o600)
        env = dict(os.environ, HOME=folder, PYTHONPATH=str(ROOT))
        args = [sys.executable, '-m', 'streamlit', 'run', str(ROOT/'staging/app.py'),
                '--server.address=0.0.0.0', '--server.port='+port,
                '--server.headless=true', '--theme.base=dark', '--browser.gatherUsageStats=false',
                '--server.fileWatcherType=none', '--server.enableCORS=true',
                '--server.enableXsrfProtection=true']
        # cwd is also isolated: root project secrets cannot override fresh HOME.
        child = subprocess.Popen(args, cwd=folder, env=env)
        def stop(*_): child.terminate()
        signal.signal(signal.SIGTERM, stop); signal.signal(signal.SIGINT, stop)
        while child.poll() is None:
            print(json.dumps({'type':'STAGING_MEMORY', **memory(child.pid)}), flush=True)
            time.sleep(5)
        raise SystemExit(child.returncode)

if __name__ == '__main__': main()
