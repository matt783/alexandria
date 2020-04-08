import logging
from typing import Any, AsyncIterator, Awaitable, Generator, Set

from async_generator import asynccontextmanager
import trio

from alexandria.abc import Endpoint, SessionAPI  # noqa: F401
from alexandria.abc import (
    EventAPI,
    EventsAPI,
    MessageAPI,
    TAwaitable,
    TEventPayload,
)
from alexandria.payloads import (
    Advertise, Ack,
    Retrieve, Chunk,
    FindNodes, FoundNodes,
    Locate, Locations,
    Ping, Pong,
)


class ReAwaitable(Awaitable[TAwaitable]):
    _result: Generator[Any, None, TAwaitable]

    def __init__(self, awaitable: Awaitable[TAwaitable]) -> None:
        self._awaitable = awaitable

    @property
    def is_done(self) -> bool:
        return hasattr(self, '_result')

    def __await__(self) -> Generator[Any, None, TAwaitable]:
        if not self.is_done:
            self._result = self._awaitable.__await__()
        return self._result


class Event(EventAPI[TEventPayload]):
    logger = logging.getLogger('alexandria.events.Event')

    _channels: Set[trio.abc.SendChannel[TEventPayload]]

    def __init__(self, name: str) -> None:
        self.name = name
        self._lock = trio.Lock()
        self._channels = set()

    async def trigger(self, payload: TEventPayload) -> None:
        self.logger.debug('Triggering event: %s(%s)', self.name, payload)
        async with self._lock:
            for send_channel in self._channels:
                await send_channel.send(payload)

    @asynccontextmanager
    async def subscribe(self) -> AsyncIterator[trio.abc.ReceiveChannel[TEventPayload]]:
        send_channel, receive_channel = trio.open_memory_channel[TEventPayload](256)

        async with self._lock:
            self._channels.add(send_channel)

        try:
            async with receive_channel:
                yield receive_channel
        finally:
            async with self._lock:
                self._channels.remove(send_channel)


class Events(EventsAPI):
    def __init__(self) -> None:
        self.listening: Event[Endpoint] = Event('listening')

        self.session_created: Event[SessionAPI] = Event('session-created')
        self.session_idle: Event[SessionAPI] = Event('session-idle')

        self.handshake_complete: Event[SessionAPI] = Event('handshake-complete')
        self.handshake_timeout: Event[SessionAPI] = Event('handshake-timeout')

        self.sent_ping: Event[MessageAPI[Ping]] = Event('sent-Ping')
        self.sent_pong: Event[MessageAPI[Pong]] = Event('sent-Pong')

        self.sent_find_nodes: Event[MessageAPI[FindNodes]] = Event('sent-FindNodes')
        self.sent_found_nodes: Event[MessageAPI[FoundNodes]] = Event('sent-FoundNodes')

        self.sent_advertise: Event[MessageAPI[Advertise]] = Event('sent-Advertise')
        self.sent_ack: Event[MessageAPI[Ack]] = Event('sent-Ack')

        self.sent_locate: Event[MessageAPI[Locate]] = Event('sent-Locate')
        self.sent_locations: Event[MessageAPI[Locations]] = Event('sent-Locations')

        self.sent_retrieve: Event[MessageAPI[Retrieve]] = Event('sent-Retrieve')
        self.sent_chunk: Event[MessageAPI[Chunk]] = Event('sent-Chunk')
