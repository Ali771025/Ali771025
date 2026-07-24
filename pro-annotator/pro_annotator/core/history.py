from __future__ import annotations
from copy import deepcopy
from typing import Any, List, Optional
import time

class HistoryManager:
    """
    Undo/Redo with full snapshot history for professional annotator.
    Stores deep copies of project images dict or specific image annotations.
    """
    def __init__(self, max_history: int = 150):
        self.undo_stack: List[Any] = []
        self.redo_stack: List[Any] = []
        self.max_history = max_history
        self.last_push = 0.0
        self.coalesce_ms = 500  # coalesce rapid changes

    def push(self, state: Any, force: bool = False):
        now = time.time()*1000
        if not force and self.undo_stack and (now - self.last_push) < self.coalesce_ms:
            # replace last instead of push to avoid spam
            self.undo_stack[-1] = deepcopy(state)
        else:
            self.undo_stack.append(deepcopy(state))
            if len(self.undo_stack) > self.max_history:
                self.undo_stack.pop(0)
            self.redo_stack.clear()
        self.last_push = now

    def can_undo(self) -> bool:
        return len(self.undo_stack) > 1

    def can_redo(self) -> bool:
        return len(self.redo_stack) > 0

    def undo(self) -> Optional[Any]:
        if not self.can_undo():
            return None
        cur = self.undo_stack.pop()
        self.redo_stack.append(cur)
        return deepcopy(self.undo_stack[-1])

    def redo(self) -> Optional[Any]:
        if not self.can_redo():
            return None
        state = self.redo_stack.pop()
        self.undo_stack.append(deepcopy(state))
        return deepcopy(state)

    def clear(self):
        self.undo_stack.clear()
        self.redo_stack.clear()
