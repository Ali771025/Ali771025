from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable

from .models import Envelope
from .protocol import ProtocolError, parse_envelope


logger = logging.getLogger(__name__)
EnvelopeHandler = Callable[[Envelope, str], Awaitable[None]]


class UDPIngestProtocol(asyncio.DatagramProtocol):
    def __init__(
        self,
        handler: EnvelopeHandler,
        invalid_callback: Callable[[], None],
        shared_secret: str | None = None,
    ):
        self.handler = handler
        self.invalid_callback = invalid_callback
        self.shared_secret = shared_secret

    def datagram_received(self, data: bytes, addr) -> None:
        try:
            envelope = parse_envelope(data, self.shared_secret)
        except ProtocolError:
            self.invalid_callback()
            return
        asyncio.create_task(self.handler(envelope, "udp"))

    def error_received(self, exc: Exception) -> None:
        logger.warning("UDP ingest error: %s", exc)


async def handle_tcp_client(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    handler: EnvelopeHandler,
    invalid_callback: Callable[[], None],
    shared_secret: str | None = None,
) -> None:
    peer = writer.get_extra_info("peername")
    try:
        while line := await reader.readline():
            if len(line) > 1_000_000:
                invalid_callback()
                break
            try:
                envelope = parse_envelope(line, shared_secret)
            except ProtocolError:
                invalid_callback()
                writer.write(b'{"ok":false,"error":"invalid_envelope"}\n')
                await writer.drain()
                continue
            await handler(envelope, "tcp")
            writer.write(f'{{"ok":true,"sequence_no":{envelope.sequence_no}}}\n'.encode())
            await writer.drain()
    except (ConnectionError, asyncio.CancelledError):
        pass
    finally:
        writer.close()
        await writer.wait_closed()
        logger.debug("TCP ingest client disconnected: %s", peer)


class IngestServers:
    def __init__(
        self,
        handler: EnvelopeHandler,
        invalid_callback: Callable[[], None],
        shared_secret: str | None = None,
    ):
        self.handler = handler
        self.invalid_callback = invalid_callback
        self.shared_secret = shared_secret
        self.udp_transport: asyncio.DatagramTransport | None = None
        self.tcp_server: asyncio.Server | None = None

    async def start(self, udp_host: str, udp_port: int, tcp_host: str, tcp_port: int) -> None:
        loop = asyncio.get_running_loop()
        transport, _ = await loop.create_datagram_endpoint(
            lambda: UDPIngestProtocol(self.handler, self.invalid_callback, self.shared_secret),
            local_addr=(udp_host, udp_port),
        )
        self.udp_transport = transport
        self.tcp_server = await asyncio.start_server(
            lambda r, w: handle_tcp_client(r, w, self.handler, self.invalid_callback, self.shared_secret),
            tcp_host,
            tcp_port,
            limit=1_100_000,
        )

    async def stop(self) -> None:
        if self.udp_transport:
            self.udp_transport.close()
        if self.tcp_server:
            self.tcp_server.close()
            await self.tcp_server.wait_closed()


class SampleLimiter:
    def __init__(self, hz: float):
        self.interval = 1 / hz
        self.last: dict[str, float] = {}

    def allow(self, source: str) -> bool:
        now = time.monotonic()
        if now - self.last.get(source, 0) < self.interval:
            return False
        self.last[source] = now
        return True

