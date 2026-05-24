import asyncio
from typing import Dict


class Broadcaster:
    def __init__(self):
        self._subscribers: Dict[str, list[asyncio.Queue]] = {}

    def subscribe(self, username: str) -> asyncio.Queue:
        q = asyncio.Queue()
        self._subscribers.setdefault(username, []).append(q)
        return q

    def unsubscribe(self, username: str, q: asyncio.Queue):
        queues = self._subscribers.get(username, [])
        if q in queues:
            queues.remove(q)

    async def publish(self, message: dict):
        recipient = message.get("recipient")
        sender = message.get("sender")
        notified = set()
        for username, queues in self._subscribers.items():
            if username == recipient or username == sender:
                for q in queues:
                    await q.put(message)
                notified.add(username)


broadcaster = Broadcaster()
