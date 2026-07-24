from .base import OpenCVSource
class UsbSource(OpenCVSource):
    def __init__(self, source: str, source_type="usb"):
        # handle dshow://0
        super().__init__(source, source_type)

class V4L2Source(OpenCVSource):
    def __init__(self, source: str, source_type="v4l2"):
        super().__init__(source, source_type)
