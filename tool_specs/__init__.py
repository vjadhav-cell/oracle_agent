"""Tool specification registries shared between main + manifest."""

try:
    from .metadata import TOOL_METADATA  # noqa: F401
except ModuleNotFoundError:
    TOOL_METADATA = {}

