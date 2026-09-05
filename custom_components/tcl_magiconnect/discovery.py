"""One-shot native UDP discovery (only when explicitly requested in setup)."""

import asyncio
import time

from .protocol import DISCOVERY_PORT, discovery_message, parse_discovery


class DiscoveryProtocol(asyncio.DatagramProtocol):
    def __init__(self):
        self.devices = {}
        self.error = None

    def datagram_received(self, data, addr):
        if device := parse_discovery(data, addr[0]):
            self.devices[device.host] = device

    def error_received(self, exc):
        self.error = exc


async def discover(client_id: str, *, target: str = "255.255.255.255", duration: float = 3):
    """Listen on the native port; surface bind errors instead of hiding them."""
    transport, protocol = await asyncio.get_running_loop().create_datagram_endpoint(
        DiscoveryProtocol,
        local_addr=("0.0.0.0", DISCOVERY_PORT),
        allow_broadcast=True,
    )
    try:
        transport.sendto(
            discovery_message(client_id, int(time.time() * 1000)), (target, DISCOVERY_PORT)
        )
        await asyncio.sleep(duration)
        if protocol.error and not protocol.devices:
            raise protocol.error
        return list(protocol.devices.values())
    finally:
        transport.close()
