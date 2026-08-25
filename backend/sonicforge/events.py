from __future__ import annotations
import asyncio
from collections.abc import AsyncIterator
class EventBus:
    def __init__(self)->None: self._subscribers:set[asyncio.Queue]=set()
    async def publish(self,event:dict)->None:
        for queue in tuple(self._subscribers):
            if queue.full():
                try: queue.get_nowait()
                except asyncio.QueueEmpty: pass
            await queue.put(event)
    async def subscribe(self)->AsyncIterator[dict]:
        queue:asyncio.Queue=asyncio.Queue(maxsize=100); self._subscribers.add(queue)
        try:
            while True: yield await queue.get()
        finally: self._subscribers.discard(queue)
