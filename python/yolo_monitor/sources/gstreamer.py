from .base import OpenCVSource
class GStreamerSource(OpenCVSource):
    def __init__(self, source: str, source_type="gstreamer"):
        super().__init__(source, source_type, backend="gstreamer")
