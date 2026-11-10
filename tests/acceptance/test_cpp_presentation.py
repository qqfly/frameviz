"""Installed C++ SDK uses the exact presentation command exposed to Python."""
import json
import os
import subprocess

import pytest
from test_presentation_contracts import h, marked_viewer


def test_installed_cpp_can_present_an_authenticated_managed_page(h, tmp_path):
    binary = os.environ.get('FRAMEVIZ_CPP_PRESENT_VIEW')
    if not binary:
        pytest.skip('Installed SDK present_view executable required')
    first = h.view('a'); second = h.view('b'); handle = h.box('b')
    page = marked_viewer(h, first, 'cpp_page')
    env = dict(os.environ, FRAMEVIZ_AUTH_TOKEN=h.token,
               FRAMEVIZ_DISCOVERY_PATH=str(tmp_path/'unused.json'))
    result = subprocess.run([binary, h.url, 'cpp_page', second], env=env,
                            capture_output=True, text=True, timeout=5)
    assert result.returncode == 0 and result.stdout.strip() == '1', result.stderr
    assert json.loads(page.recv(timeout=2))['view_id'] == second
    snapshot = json.loads(page.recv(timeout=2))
    assert snapshot['scene_id'] == 'b' and snapshot['objects'][0]['handle'] == handle
