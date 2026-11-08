from importlib.metadata import version as _get_version

from .client import DEFAULT_WS_URL, FrameVizClient  # noqa: F401
from .host import ensure_host_running, is_host_running, start_host, stop_host  # noqa: F401
from .viz import (  # noqa: F401
    DEFAULT_VIEWER_URL,
    Viz,
    connect,
    destroy_scene,
    destroy_view,
    list_scenes,
    list_views,
    open,
)

try:
    __version__ = _get_version("frameviz")
except Exception:
    __version__ = "0.0.0"  # Fallback for editable installs without metadata
__all__ = [
    "FrameVizClient",
    "Viz",
    "open",
    "connect",
    "list_scenes",
    "list_views",
    "destroy_scene",
    "destroy_view",
    "DEFAULT_WS_URL",
    "DEFAULT_VIEWER_URL",
    "ensure_host_running",
    "is_host_running",
    "start_host",
    "stop_host",
]
