"""Script lifetime convenience must preserve cleanup and error propagation."""
from unittest.mock import MagicMock

import pytest
from frameviz.viz import Viz


@pytest.mark.parametrize('interrupted', [False, True])
def test_keep_running_closes_after_disconnect_or_keyboard_interrupt(interrupted):
    client = MagicMock()
    if interrupted:
        client.spin.side_effect = KeyboardInterrupt
    viz = Viz(client, 'scene', 'view')
    viz.keep_running()
    client.spin.assert_called_once()
    client.close.assert_called_once()


def test_keep_running_preserves_unexpected_errors_after_cleanup():
    client = MagicMock()
    client.spin.side_effect = RuntimeError('Synthetic lifetime failure')
    viz = Viz(client, 'scene', 'view')
    with pytest.raises(RuntimeError, match='Synthetic lifetime failure'):
        viz.keep_running()
    client.close.assert_called_once()
