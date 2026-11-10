"""Real runtime cleanup respects process and discovery ownership."""
import json
import os
import signal
from test_standalone_viewer import standalone


def test_sdk_style_termination_shuts_down_cleanly(standalone):
    _,process,_,discovery=standalone
    process.send_signal(signal.SIGTERM)
    assert process.wait(timeout=5)==0
    assert not discovery.exists()


def test_shutdown_preserves_a_replaced_discovery_record(standalone):
    _,process,_,discovery=standalone
    replacement=json.dumps({'pid':os.getpid(),'token':'synthetic-another-runtime'})
    discovery.write_text(replacement)
    process.send_signal(signal.SIGINT)
    assert process.wait(timeout=5)==0
    assert discovery.exists() and discovery.read_text()==replacement
