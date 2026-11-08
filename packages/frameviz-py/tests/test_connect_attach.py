from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

import frameviz.viz as fv_viz


def test_resolve_connection_url_uses_env_var(monkeypatch):
    monkeypatch.setenv("FRAMEVIZ_HOST", "ws://127.0.0.1:11001")

    with patch.object(
        fv_viz, "_resolve_ws_url", return_value="ws://127.0.0.1:11001"
    ) as mock_resolve:
        resolved = fv_viz._resolve_connection_url(None)

    assert resolved == "ws://127.0.0.1:11001"
    mock_resolve.assert_called_once_with(
        "ws://127.0.0.1:11001", allow_discovery=True
    )


def test_connect_by_view_id_uses_list_views_resolution():
    fake_client = MagicMock()
    fake_viz = object()
    fake_client.send_command.return_value = {
        "views": [{"view_id": "v_1", "scene_id": "s_1"}]
    }

    with patch.object(
        fv_viz, "_resolve_connection_url", return_value="ws://127.0.0.1:11002"
    ) as mock_resolve, patch.object(
        fv_viz, "FrameVizClient", return_value=fake_client
    ) as mock_client_cls, patch.object(
        fv_viz.Viz, "_from_viewer", return_value=fake_viz
    ) as mock_from_viewer:
        viz = fv_viz.connect(url=None, timeout=3.0, view_id="v_1")

    mock_resolve.assert_called_once_with(None)
    mock_client_cls.assert_called_once_with(url="ws://127.0.0.1:11002", timeout=3.0)
    fake_client.connect.assert_called_once()
    fake_client.send_command.assert_called_with("list_views", {})
    mock_from_viewer.assert_called_once_with(fake_client, "v_1", "s_1")
    assert viz is fake_viz


def test_connect_auto_select_single_view():
    fake_client = MagicMock()
    fake_viz = object()
    fake_client.send_command.return_value = {
        "views": [{"view_id": "v_single", "scene_id": "s_single"}]
    }

    with patch.object(
        fv_viz, "_resolve_connection_url", return_value="ws://127.0.0.1:11003"
    ), patch.object(
        fv_viz, "FrameVizClient", return_value=fake_client
    ), patch.object(
        fv_viz.Viz, "_from_viewer", return_value=fake_viz
    ) as mock_from_viewer:
        result = fv_viz.connect(timeout=2.0)

    mock_from_viewer.assert_called_once_with(fake_client, "v_single", "s_single")
    assert result is fake_viz


def test_connect_rejects_multiple_views_without_target():
    fake_client = MagicMock()
    fake_client.send_command.return_value = {
        "views": [
            {"view_id": "v_1", "scene_id": "s_1"},
            {"view_id": "v_2", "scene_id": "s_2"},
        ]
    }

    with patch.object(
        fv_viz, "_resolve_connection_url", return_value="ws://127.0.0.1:11004"
    ), patch.object(
        fv_viz, "FrameVizClient", return_value=fake_client
    ):
        with pytest.raises(ValueError, match="Multiple views are available"):
            fv_viz.connect(timeout=2.0)

    fake_client.close.assert_called_once()


def test_connect_raises_timeout_when_target_view_id_missing():
    fake_client = MagicMock()
    fake_client.send_command.return_value = {"views": []}

    with patch.object(
        fv_viz, "_resolve_connection_url", return_value="ws://127.0.0.1:11005"
    ), patch.object(
        fv_viz, "FrameVizClient", return_value=fake_client
    ):
        with pytest.raises(TimeoutError, match="View 'v_missing' not found"):
            fv_viz.connect(timeout=0.1, view_id="v_missing")

    fake_client.close.assert_called_once()


def test_list_views_returns_only_view_and_scene_ids():
    fake_client = MagicMock()
    fake_client.send_command.return_value = {
        "views": [
            {
                "view_id": "v_1",
                "scene_id": "s_1",
                "title": "Main",
                "width": 1280,
            },
            {
                "view_id": "v_2",
                "scene_id": None,
                "title": "Secondary",
                "height": 720,
            },
            {"scene_id": "s_ignored"},
            "invalid",
        ]
    }

    with patch.object(
        fv_viz, "_resolve_connection_url", return_value="ws://127.0.0.1:11006"
    ) as mock_resolve, patch.object(
        fv_viz, "FrameVizClient", return_value=fake_client
    ):
        views = fv_viz.list_views(timeout=2.0)

    assert views == [
        {"view_id": "v_1", "scene_id": "s_1"},
        {"view_id": "v_2", "scene_id": None},
    ]
    mock_resolve.assert_called_once_with(None)
    fake_client.connect.assert_called_once()
    fake_client.send_command.assert_called_once_with("list_views", {})
    fake_client.close.assert_called_once()


def test_destroy_view_also_tries_to_close_tauri_window():
    fake_client = MagicMock()

    with patch.object(
        fv_viz, "_resolve_connection_url", return_value="ws://127.0.0.1:11007"
    ) as mock_resolve, patch.object(
        fv_viz, "FrameVizClient", return_value=fake_client
    ), patch.object(
        fv_viz, "_try_close_tauri_window"
    ) as mock_close_tauri:
        fv_viz.destroy_view("v_1", timeout=2.0)

    mock_resolve.assert_called_once_with(None)
    fake_client.connect.assert_called_once()
    fake_client.send_command.assert_called_once_with("destroy_view", {"view_id": "v_1"})
    fake_client.wait_for_event.assert_called_once()
    mock_close_tauri.assert_called_once_with("v_1")
    fake_client.close.assert_called_once()


def test_close_waits_for_view_destroyed_event():
    fake_client = MagicMock()
    viz = fv_viz.Viz(
        client=fake_client,
        scene_id="s_1",
        view_id="v_1",
        opened_via_tauri=False,
        owns_view=True,
        owns_scene=False,
    )
    fake_client.send_command.side_effect = [
        {},
        {"views": [{"view_id": "v_other", "scene_id": "s_other"}]},
    ]

    viz.close()

    fake_client.wait_for_event.assert_called_once()
    args, kwargs = fake_client.wait_for_event.call_args
    assert args[0] == "view_destroyed"
    assert kwargs["timeout"] == 2.0
    assert kwargs["filter_fn"]({"view_id": "v_1"}) is True
    assert kwargs["filter_fn"]({"view_id": "v_other"}) is False


def test_destroy_view_waits_for_view_destroyed_event():
    fake_client = MagicMock()

    with patch.object(
        fv_viz, "_resolve_connection_url", return_value="ws://127.0.0.1:11012"
    ), patch.object(
        fv_viz, "FrameVizClient", return_value=fake_client
    ), patch.object(
        fv_viz, "_try_close_tauri_window"
    ):
        fv_viz.destroy_view("v_1", timeout=2.0)

    fake_client.wait_for_event.assert_called_once()
    args, kwargs = fake_client.wait_for_event.call_args
    assert args[0] == "view_destroyed"
    assert kwargs["timeout"] == 2.0
    assert kwargs["filter_fn"]({"view_id": "v_1"}) is True
    assert kwargs["filter_fn"]({"view_id": "v_2"}) is False


def test_list_scenes_uses_connection_url_resolver():
    fake_client = MagicMock()
    fake_client.send_command.return_value = {"scenes": [{"scene_id": "s_1"}]}

    with patch.object(
        fv_viz, "_resolve_connection_url", return_value="ws://127.0.0.1:11008"
    ) as mock_resolve, patch.object(
        fv_viz, "FrameVizClient", return_value=fake_client
    ):
        scenes = fv_viz.list_scenes(timeout=2.0)

    mock_resolve.assert_called_once_with(None)
    assert scenes == [{"scene_id": "s_1"}]
    fake_client.connect.assert_called_once()
    fake_client.send_command.assert_called_once_with("list_scenes", {})
    fake_client.close.assert_called_once()


def test_destroy_scene_uses_connection_url_resolver():
    fake_client = MagicMock()

    with patch.object(
        fv_viz, "_resolve_connection_url", return_value="ws://127.0.0.1:11009"
    ) as mock_resolve, patch.object(
        fv_viz, "FrameVizClient", return_value=fake_client
    ):
        fv_viz.destroy_scene("s_1", timeout=2.0)

    mock_resolve.assert_called_once_with(None)
    fake_client.connect.assert_called_once()
    fake_client.send_command.assert_called_once_with("destroy_scene", {"scene_id": "s_1"})
    fake_client.close.assert_called_once()


def test_close_from_connect_does_not_destroy_view_or_scene():
    fake_client = MagicMock()
    viz = fv_viz.Viz(
        client=fake_client,
        scene_id="s_1",
        view_id="v_1",
        opened_via_tauri=False,
        owns_view=False,
        owns_scene=False,
    )

    viz.close()

    fake_client.send_command.assert_not_called()
    fake_client.close.assert_called_once()


def test_connect_timeout_mentions_unbound_requested_view():
    fake_client = MagicMock()
    fake_client.send_command.return_value = {
        "views": [{"view_id": "v_pending", "scene_id": None}]
    }

    with patch.object(
        fv_viz, "_resolve_connection_url", return_value="ws://127.0.0.1:11010"
    ), patch.object(
        fv_viz, "FrameVizClient", return_value=fake_client
    ):
        with pytest.raises(TimeoutError, match="exists but is not attached to a scene"):
            fv_viz.connect(timeout=0.1, view_id="v_pending")

    fake_client.close.assert_called_once()


def test_open_uses_connection_url_resolver_when_url_omitted():
    fake_client = MagicMock()
    fake_client.send_command.side_effect = [
        {"scene_id": "s_1"},
        {"view_id": "v_1"},
    ]

    with patch.object(
        fv_viz, "_resolve_connection_url", return_value="ws://127.0.0.1:11011"
    ) as mock_resolve, patch.object(
        fv_viz, "FrameVizClient", return_value=fake_client
    ) as mock_client_cls, patch.object(
        fv_viz, "_get_viewer_url", return_value="http://127.0.0.1:8080/packages/frameviz-web-viewer/"
    ):
        viz = fv_viz.open(url=None, timeout=2.0, window_mode=0)

    mock_resolve.assert_called_once_with(None)
    mock_client_cls.assert_called_once_with(url="ws://127.0.0.1:11011", timeout=2.0)
    fake_client.connect.assert_called_once()
    assert viz.scene_id == "s_1"
    assert viz.view_id == "v_1"
