# Placeholder for ByteTrack - uses IoU tracker fallback if ByteTrack not installed
from .simple_iou_tracker import IOUTracker
class ByteTracker(IOUTracker):
    def __init__(self, *args, **kwargs):
        super().__init__(*args,**kwargs)
