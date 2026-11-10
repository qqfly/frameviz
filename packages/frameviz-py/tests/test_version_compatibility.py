"""Patch compatibility applies to authentication and active discovery."""
import json
import os

import pytest
from frameviz.client import FrameVizClient
from frameviz.exceptions import ProtocolError
from frameviz._internal import _read_discovery_port


def authenticate(version):
    client = FrameVizClient(token='synthetic-version-token', timeout=.1)
    class Transport:
        def send(self, _):
            response = {'type':'auth_resp','ok':True}
            if version is not None:response['protocol_version']=version
            client._handle_message(json.dumps(response))
    client._ws = Transport()
    try:client._authenticate()
    finally:client._ws = None


@pytest.mark.parametrize('version',['0.4.0','0.4.1','0.4.99'])
def test_patch_host_authenticates(version):
    authenticate(version)


@pytest.mark.parametrize('version,upgrade',[('0.3.99','runtime'),('0.5.0','SDK'),('1.0.0','SDK')])
def test_incompatible_auth_identifies_upgrade_direction(version, upgrade):
    with pytest.raises(ProtocolError,match='[Uu]pgrade.*'+upgrade):authenticate(version)


@pytest.mark.parametrize('version',[None,'','0.4','00.4.1','0.04.1','0.4.01','0.4.1-beta','0.4.1+build','0.4.9999999999','0.4.x'])
def test_malformed_auth_rejected(version):
    with pytest.raises(ProtocolError,match='[Mm]issing|[Mm]alformed'):authenticate(version)


def test_same_series_discovery_reused(tmp_path, monkeypatch):
    path=tmp_path/'host.json'
    path.write_text(json.dumps({'pid':os.getpid(),'port':21599,'version':'0.4.7'}))
    assert _read_discovery_port(path)==21599
