from __future__ import annotations
import queue
from typing import Optional

class BoundedQueue:
    def __init__(self, maxsize: int = 8, drop_policy: str = "oldest"):
        self.q = queue.Queue(maxsize=maxsize)
        self.drop_policy = drop_policy

    def put(self, item):
        try:
            self.q.put_nowait(item)
        except queue.Full:
            if self.drop_policy == "oldest":
                try:
                    self.q.get_nowait()
                except queue.Empty:
                    pass
                try:
                    self.q.put_nowait(item)
                except queue.Full:
                    pass
            elif self.drop_policy == "newest":
                # drop new item
                pass
            else:
                # blocking put with timeout
                try:
                    self.q.put(item, timeout=0.1)
                except queue.Full:
                    pass

    def get(self, timeout: float = 0.1):
        return self.q.get(timeout=timeout)

    def task_done(self):
        self.q.task_done()

    def empty(self):
        return self.q.empty()

    def qsize(self):
        return self.q.qsize()
