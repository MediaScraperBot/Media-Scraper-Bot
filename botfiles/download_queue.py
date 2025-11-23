import json
import os
from typing import Dict, List, Optional


class DownloadQueue:
    """Persistent FIFO queue for media downloads."""

    def __init__(self, queue_path: str):
        self.queue_path = queue_path
        self._queue: List[Dict] = []
        self._load()

    # Internal utilities -------------------------------------------------
    def _load(self) -> None:
        if os.path.exists(self.queue_path):
            try:
                with open(self.queue_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        self._queue = data
            except Exception:
                # Corrupt queue – start fresh but keep backup for inspection.
                backup = self.queue_path + ".bak"
                try:
                    os.replace(self.queue_path, backup)
                except OSError:
                    pass
                self._queue = []

    def _save(self) -> None:
        tmp_path = self.queue_path + ".tmp"
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(self._queue, f, ensure_ascii=False, indent=2)
            try:
                os.replace(tmp_path, self.queue_path)
            except PermissionError:
                # File locked, try removing first
                try:
                    os.remove(self.queue_path)
                except Exception:
                    pass
                os.rename(tmp_path, self.queue_path)
        except Exception as e:
            # Cleanup temp file on failure
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except Exception:
                pass
            # Don't raise - allow program to continue even if save fails
            print(f"Warning: Failed to save queue: {e}")

    # Queue operations ---------------------------------------------------
    def __len__(self) -> int:
        return len(self._queue)

    def as_list(self) -> List[Dict]:
        return list(self._queue)

    def extend(self, items: List[Dict]) -> None:
        if not items:
            return
        self._queue.extend(items)
        self._save()

    def pop_next(self) -> Optional[Dict]:
        if not self._queue:
            return None
        item = self._queue.pop(0)
        self._save()
        return item

    def remove_where(self, predicate) -> int:
        """Remove queued entries matching predicate(item)."""
        if not self._queue:
            return 0
        initial = len(self._queue)
        self._queue = [item for item in self._queue if not predicate(item)]
        if len(self._queue) != initial:
            self._save()
        return initial - len(self._queue)

    def clear(self) -> None:
        self._queue = []
        if os.path.exists(self.queue_path):
            os.remove(self.queue_path)

    def ensure_unique(self, key: str) -> None:
        """Deduplicate queue entries based on the provided key name."""
        seen = set()
        deduped = []
        for item in self._queue:
            value = item.get(key)
            if value in seen:
                continue
            seen.add(value)
            deduped.append(item)
        if len(deduped) != len(self._queue):
            self._queue = deduped
            self._save()
