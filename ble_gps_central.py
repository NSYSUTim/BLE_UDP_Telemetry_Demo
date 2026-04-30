#!/usr/bin/env python3
"""
Pi #2: Phone / Test Station Simulator
- BLE Central: scan → connect → show GATT services (discovery demo)
- UDP Receiver: 30 秒接收 telemetry
- Log + Test Report
"""

import asyncio
import csv
import json
import socket
import time
from pathlib import Path

from bleak import BleakScanner, BleakClient

DEVICE_NAME    = "OutdoorTracker"
SERVICE_UUID   = "12345678-1234-5678-1234-56789abcde10"
TELEMETRY_UUID = "12345678-1234-5678-1234-56789abcde11"

UDP_PORT        = 9000
RECEIVE_SECONDS = 30

LOG_FILE    = Path("telemetry_log.csv")
REPORT_FILE = Path("test_report.txt")

received_rows    = []
last_seq         = None
packet_loss_count = 0
gps_lost_count   = 0


def init_log():
    with LOG_FILE.open("w", newline="") as f:
        csv.writer(f).writerow([
            "received_at", "seq", "speed_cmps", "speed_mps",
            "distance_dm", "distance_m", "gps_valid", "state",
        ])


def save_row(row: dict):
    with LOG_FILE.open("a", newline="") as f:
        csv.writer(f).writerow([
            row["received_at"], row["seq"], row["speed_cmps"],
            f"{row['speed_mps']:.2f}", row["distance_dm"],
            f"{row['distance_m']:.1f}", row["gps_valid"], row["state"],
        ])


def handle_row(row: dict):
    global last_seq, packet_loss_count, gps_lost_count
    row["received_at"] = time.time()

    if last_seq is not None and row["seq"] > last_seq + 1:
        packet_loss_count += row["seq"] - last_seq - 1
    last_seq = row["seq"]

    if row["gps_valid"] == 0:
        gps_lost_count += 1

    received_rows.append(row)
    save_row(row)

    print(
        f"[UDP RX] seq={row['seq']:3d}  "
        f"speed={row['speed_mps']:.2f}m/s  "
        f"dist={row['distance_m']:.1f}m  "
        f"gps={row['gps_valid']}  "
        f"state={row['state']}"
    )


def generate_report():
    tests = [
        ("Receive at least 5 samples",
         len(received_rows) >= 5),

        ("Sequence strictly increasing",
         all(received_rows[i]["seq"] < received_rows[i+1]["seq"]
             for i in range(len(received_rows)-1))
         if len(received_rows) >= 2 else False),

        ("Distance non-decreasing",
         all(received_rows[i]["distance_dm"] <= received_rows[i+1]["distance_dm"]
             for i in range(len(received_rows)-1))
         if len(received_rows) >= 2 else False),

        ("GPS lost state observable", gps_lost_count > 0),
    ]

    passed = sum(1 for _, r in tests if r)
    lines  = [
        "BLE Outdoor Activity Telemetry Test Report",
        "=" * 50,
        f"Total samples received : {len(received_rows)}",
        f"Packet loss count      : {packet_loss_count}",
        f"GPS lost samples       : {gps_lost_count}",
        "",
    ]
    for name, result in tests:
        lines.append(f"{'PASS' if result else 'FAIL'}  {name}")
    lines += ["", f"Summary: {passed} / {len(tests)} PASS"]

    REPORT_FILE.write_text("\n".join(lines) + "\n")
    print("\n" + "\n".join(lines))


async def ble_discovery_phase() -> bool:
    print("[BLE] Scanning for OutdoorTracker (20s)...")
    device = await BleakScanner.find_device_by_name(DEVICE_NAME, timeout=20.0)

    if device is None:
        print("[BLE] Not found. Nearby devices:")
        for d in await BleakScanner.discover(timeout=8.0):
            print(f"  {d.name}  {d.address}")
        return False

    print(f"[BLE] Found: {device.name}  {device.address}")

    async with BleakClient(device) as client:
        print(f"[BLE] Connected: {client.is_connected}")
        for service in client.services:
            print(f"  Service: {service.uuid}")
            for char in service.characteristics:
                print(f"    Char: {char.uuid}  props={char.properties}")

    print("[BLE] Discovery complete. Disconnected. Switching to UDP receiver.")
    return True


async def udp_receiver_phase():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("0.0.0.0", UDP_PORT))
    sock.setblocking(False)

    loop     = asyncio.get_running_loop()
    end_time = loop.time() + RECEIVE_SECONDS

    print(f"[UDP] Listening on :{UDP_PORT} for {RECEIVE_SECONDS} seconds...")

    while loop.time() < end_time:
        try:
            raw = sock.recv(65535)
            row = json.loads(raw.decode("utf-8"))
            handle_row(row)
        except BlockingIOError:
            await asyncio.sleep(0.05)
        except Exception as e:
            print(f"[ERROR] {e}")
            await asyncio.sleep(0.05)

    sock.close()
    print("[UDP] Done.")


async def main():
    init_log()
    await ble_discovery_phase()
    await udp_receiver_phase()
    generate_report()


if __name__ == "__main__":
    asyncio.run(main())
