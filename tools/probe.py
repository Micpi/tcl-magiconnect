"""Read-only MagiConnect probe for a computer on the TV's LAN."""

import argparse
import asyncio
import json
import sys
from pathlib import Path
from types import ModuleType
from uuid import uuid4

# The protocol is HA-independent, although shipped within the integration.
package = ModuleType("magiconnect_wire")
package.__path__ = [str(Path(__file__).resolve().parents[1] / "custom_components/tcl_magiconnect")]
sys.modules[package.__name__] = package

from magiconnect_wire.client import CannotConnect, MagiConnectClient  # noqa: E402
from magiconnect_wire.discovery import discover  # noqa: E402
from magiconnect_wire.protocol import ProtocolError  # noqa: E402


async def run(host):
    client_id = uuid4().hex
    if not host:
        return {
            "devices": [
                {"host": d.host, "name": d.name, "protocol_version": d.version}
                for d in await discover(client_id)
            ]
        }
    client = MagiConnectClient(host, client_id)
    try:
        info = await client.identify()
        return {
            "magiconnect": True,
            "model": info.model,
            "software_version": info.software_version,
            "service_version": info.app_version,
            "algorithm": info.algorithm,
            "functions": info.functions,
            "stable_identifier_available": bool(info.unique_id),
        }
    finally:
        await client.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", help="TV IP address. Omit to discover devices on UDP 6537.")
    args = parser.parse_args()
    try:
        result = asyncio.run(run(args.host))
    except (CannotConnect, ProtocolError, OSError) as err:
        print(json.dumps({"error": str(err), "magiconnect": False}))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
