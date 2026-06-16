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

    @property
    def online_users(self) -> list[str]:
        return [u for u, queues in self._subscribers.items() if queues]

    async def publish(self, message: dict):
        recipient = message.get("recipient")
        sender = message.get("sender")
        for username, queues in self._subscribers.items():
            if recipient == "all" or username == recipient or username == sender:
                for q in queues:
                    await q.put(message)


broadcaster = Broadcaster()
