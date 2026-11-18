import asyncio
import logging
import time
import uuid
from pathlib import Path

log = logging.getLogger("card_webhook")

# Filled from the back. Card 12 waits out the hold, then becomes the next GK.
ROLES = (
    "GK",
    "LB",
    "LCB",
    "RCB",
    "RB",
    "LCM",
    "CM",
    "RCM",
    "LW",
    "ST",
    "RW",
)


class Lineup:
    def __init__(self, hold_seconds: float, data_dir: Path, broadcast):
        self.hold_seconds = hold_seconds
        self.data_dir = data_dir
        self._broadcast = broadcast
        self.slots: list[dict | None] = [None] * len(ROLES)
        self.phase = "filling"
        self.queue: list[dict] = []
        self.seen: set[str] = set()
        self.hold_until: float | None = None
        self._lock = asyncio.Lock()
        self._hold_task: asyncio.Task | None = None

    async def current(self) -> dict:
        async with self._lock:
            return self._snapshot()

    async def submit(self, request_id: str, card: dict | None, image: bytes | None, ext: str | None) -> str:
        async with self._lock:
            if request_id in self.seen:
                return "duplicate"
            if card is None or not image or not ext:
                return "no_image"

            filename = f"{uuid.uuid4().hex}.{ext}"
            (self.data_dir / filename).write_bytes(image)
            card = {**card, "request_id": request_id, "image_url": f"/cards/{filename}"}
            self.seen.add(request_id)

            if self.phase == "holding":
                self.queue.append(card)
                result = "queued"
            else:
                self._place(card)
                result = "placed"
                if self._first_empty() is None:
                    self._begin_hold()

            snap = self._snapshot()

        await self._broadcast(snap)
        log.info("lineup %s request_id=%s name=%s", result, request_id, card.get("name", ""))
        return result

    def _place(self, card: dict) -> None:
        index = self._first_empty()
        if index is None:
            raise RuntimeError("lineup is full")
        self.slots[index] = card

    def _first_empty(self) -> int | None:
        for index, slot in enumerate(self.slots):
            if slot is None:
                return index
        return None

    def _begin_hold(self) -> None:
        self.phase = "holding"
        self.hold_until = time.time() + self.hold_seconds
        current = asyncio.current_task()
        previous = self._hold_task
        self._hold_task = asyncio.create_task(self._hold_and_reset())
        if previous is not None and previous is not current and not previous.done():
            previous.cancel()

    async def _hold_and_reset(self) -> None:
        try:
            await asyncio.sleep(self.hold_seconds)
        except asyncio.CancelledError:
            return
        async with self._lock:
            self.slots = [None] * len(ROLES)
            self.phase = "filling"
            self.hold_until = None
            while self.queue and self._first_empty() is not None:
                self.slots[self._first_empty()] = self.queue.pop(0)
            if self._first_empty() is None:
                self._begin_hold()
            snap = self._snapshot()
        await self._broadcast(snap)
        log.info("lineup reset phase=%s queued=%s", snap["phase"], snap["queue_length"])

    def _snapshot(self) -> dict:
        slots = []
        for role, card in zip(ROLES, self.slots):
            slots.append({"role": role, "card": card})
        return {
            "type": "snapshot",
            "phase": self.phase,
            "queue_length": len(self.queue),
            "hold_until": self.hold_until,
            "hold_seconds": self.hold_seconds,
            "slots": slots,
        }

    def cancel(self) -> None:
        if self._hold_task is not None and not self._hold_task.done():
            self._hold_task.cancel()
