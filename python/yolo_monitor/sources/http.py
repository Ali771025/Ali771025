from .base import OpenCVSource
class HttpSource(OpenCVSource):
    def __init__(self, source: str, source_type="http"):
        super().__init__(source, source_type)
