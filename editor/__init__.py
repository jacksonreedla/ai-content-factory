"""Video assembly (Phase 3). Interfaces are defined now so agents and GUI
can reference them; FFmpeg/MoviePy implementation lands with Phase 3."""
from editor.spec import RenderSpec, VideoFormat

__all__ = ["RenderSpec", "VideoFormat"]
