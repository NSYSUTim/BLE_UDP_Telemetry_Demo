#!/usr/bin/env python3
"""
Pi #1: Outdoor Device Simulator
- BLE Peripheral: advertising OutdoorTracker (discovery demo)
- UDP Sender: GPS telemetry → Pi #2
"""

import asyncio
import json
import logging
import math
import signal
import socket

from bless import (
    BlessServer,
    GATTCharacteristicProperties,
    GATTAttributePermissions,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

DEVICE_NAME  = "OutdoorTracker"
SERVICE_UUID = "12345678-1234-5678-1234-56789abcde10"
TELEMETRY_UUID = "12345678-1234-5678-1234-56789abcde11"

PI2_IP   = "192.168.x.x"   # ← 改成 Pi #2 的 IP
UDP_PORT = 9000

_seq         = 0
_distance_dm = 0
_running     = True


def make_telemetry() -> dict:
    global _seq, _distance_dm
    _seq += 1
    speed_cmps   = 120 + int(20 * math.sin(_seq / 5.0))
    _distance_dm += max(1, speed_cmps // 10)
    gps_valid    = 0 if _seq % 20 in (15, 16, 17) else 1
    return {
        "seq"        : _seq,
        "speed_cmps" : speed_cmps,
        "speed_mps"  : round(speed_cmps / 100.0, 2),
        "distance_dm": _distance_dm,
        "distance_m" : round(_distance_dm / 10.0, 1),
        "gps_valid"  : gps_valid,
        "state"      : "GPS_LOST" if gps_valid == 0 else "TRACKING",
    }


async def udp_sender():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    logging.info("UDP sender ready → %s:%d", PI2_IP, UDP_PORT)

    while _running:
        data = make_telemetry()
        msg  = json.dumps(data).encode("utf-8")
        try:
            sock.sendto(msg, (PI2_IP, UDP_PORT))
            logging.info("[UDP TX] %s", json.dumps(data))
        except Exception as e:
            logging.error("[UDP TX] failed: %s", e)
        await asyncio.sleep(1)

    sock.close()


async def main():
    global _running
    loop = asyncio.get_running_loop()

    server = BlessServer(name=DEVICE_NAME, loop=loop)
    server.read_request_func  = lambda c, **kw: bytearray(b"ok")
    server.write_request_func = lambda c, v, **kw: None

    await server.add_new_service(SERVICE_UUID)
    await server.add_new_characteristic(
        SERVICE_UUID,
        TELEMETRY_UUID,
        GATTCharacteristicProperties.read | GATTCharacteristicProperties.notify,
        bytearray(b"0,0,0,1"),
        GATTAttributePermissions.readable | GATTAttributePermissions.writeable,
    )

    await server.start()

    logging.info("OutdoorTracker BLE Peripheral started")
    logging.info("Service UUID   : %s", SERVICE_UUID)
    logging.info("Telemetry UUID : %s", TELEMETRY_UUID)
    logging.info("UDP target     : %s:%d", PI2_IP, UDP_PORT)

    stop_event = asyncio.Event()

    def _stop():
        global _running
        _running = False
        stop_event.set()

    try:
        loop.add_signal_handler(signal.SIGINT,  _stop)
        loop.add_signal_handler(signal.SIGTERM, _stop)
    except NotImplementedError:
        pass

    udp_task = asyncio.create_task(udp_sender())

    await stop_event.wait()

    udp_task.cancel()
    try:
        await udp_task
    except asyncio.CancelledError:
        pass

    await server.stop()
    logging.info("Stopped")


if __name__ == "__main__":
    asyncio.run(main())
