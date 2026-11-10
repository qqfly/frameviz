"""Signing must fail closed without explicit external identity and credentials."""
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]


def test_signed_builder_requires_explicit_credentials_before_creating_output(tmp_path):
    env = {k: v for k, v in os.environ.items() if k not in
           ('FRAMEVIZ_SIGNING_IDENTITY', 'FRAMEVIZ_NOTARY_PROFILE')}
    output = tmp_path / 'signed-output'
    result = subprocess.run(['bash', str(ROOT/'scripts/release/build-macos-signed.sh'), str(output)],
                            env=env, capture_output=True, text=True)
    assert result.returncode != 0
    assert 'FRAMEVIZ_SIGNING_IDENTITY' in result.stderr
    assert not output.exists()
