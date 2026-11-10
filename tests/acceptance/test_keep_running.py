"""A real standalone script needs one lifetime call and preserves a manual Host."""
import json
import os
import selectors
import signal
import subprocess
import sys

from frameviz.client import FrameVizClient
from test_standalone_viewer import standalone


def test_script_keeps_running_then_sigint_closes_only_its_view(standalone, tmp_path):
    info, server, _, discovery = standalone
    script = tmp_path/'script.py'
    script.write_text('''import json
import frameviz as fv
viz = fv.open(window_mode=0)
viz.add_box()
print(json.dumps({'view_id': viz.view_id}), flush=True)
viz.keep_running()
''')
    env = {k: v for k, v in os.environ.items() if not k.startswith('FRAMEVIZ_')}
    env.update(HOME=str(tmp_path), CFFIXED_USER_HOME=str(tmp_path), FRAMEVIZ_DISCOVERY_PATH=str(discovery))
    process = subprocess.Popen([sys.executable, str(script)], env=env,
                               stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, text=True, start_new_session=True)
    observer = FrameVizClient(url=info['ws_url'], token=info['token'], timeout=3)
    observer.connect()
    try:
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ)
            assert selector.select(timeout=5), 'Script did not reach its lifetime call'
            line = process.stdout.readline()
        assert line, 'Script exited before reporting its view'
        view = json.loads(line)['view_id']
        assert process.poll() is None
        assert view in {v['view_id'] for v in observer.send_command('list_views', {})['views']}
        process.send_signal(signal.SIGINT)
        stdout, stderr = process.communicate(timeout=10)
        assert process.returncode == 0, (stdout, stderr)
        assert view not in {v['view_id'] for v in observer.send_command('list_views', {})['views']}
        assert server.poll() is None and discovery.exists()
    finally:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=5)
        process.stdout.close()
        process.stderr.close()
        observer.close()
