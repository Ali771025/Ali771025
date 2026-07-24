from .base import OpenCVSource
class VideoFileSource(OpenCVSource):
    def __init__(self, source: str, source_type="video"):
        super().__init__(source, source_type)
    def is_live(self) -> bool:
        return False
