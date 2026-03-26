#!/usr/bin/env python3

import argparse
import signal
import sys
import time
from datetime import datetime

import obd
from obd import OBDStatus

running = True


def handle_signal(signum, frame):
    global running
    running = False


def fmt_response(response):
    if response is None:
        return "no response object"

    if response.is_null():
        return "null / unsupported / no data"

    if response.value is None:
        return "no parsed value"

    return str(response.value)


def sort_key(cmd):
    mode = getattr(cmd, "mode", None)
    pid = getattr(cmd, "pid", None)
    name = getattr(cmd, "name", "") or ""

    # Normalize to consistent sortable types.
    # Keep unknown values at the end.
    mode_key = mode if isinstance(mode, str) else "ZZ"
    pid_key = pid if isinstance(pid, int) else 999999

    return (mode_key, pid_key, name)

def main():

    parser = argparse.ArgumentParser( description="Connect to an OBD-II adapter and dump all supported standard PIDs in a loop" )
    parser.add_argument( "--interval", type=float,  default=2.0,  help="Seconds to wait between full polling passes (default: 2.0)" )
    parser.add_argument( "--debug",    action="store_true",       help="Enable python-obd debug logging"  )
    args = parser.parse_args()

    if args.debug:
        obd.logger.setLevel(obd.logging.DEBUG)

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    print(f"[{datetime.now().isoformat()}] connecting")

    connection = obd.OBD()
    status = connection.status()
    print(f"[{datetime.now().isoformat()}] connection status: {status}")

    if status != OBDStatus.CAR_CONNECTED:
        print("did not reach CAR_CONNECTED")
        print("things to check:")
        print("- ignition on")
        print("- adapter visible in /dev")
        print("- no other process already has the device open")
        connection.close()
        sys.exit(1)

    supported = sorted(list(connection.supported_commands), key=sort_key)

    # Keep only named standard commands.
    # For v0, that means Mode 01 PIDs with a non-placeholder name.
    standard_named = []
    for cmd in supported:
        mode = getattr(cmd, "mode", None)
        name = getattr(cmd, "name", None)

        if isinstance(mode, int):
            mode_norm = f"{mode:02X}"
        elif isinstance(mode, str):
            mode_norm = mode.upper().zfill(2)
        else:
            mode_norm = None

        if mode_norm != "01":
            continue

        if not name or name.lower() == "unsupported":
            continue

        standard_named.append(cmd)
    print(f"[{datetime.now().isoformat()}] supported named standard PIDs: {len(standard_named)}")
    for cmd in standard_named:
        desc = getattr(cmd, "desc", "")
        print(f"  {cmd.name:<30} mode={cmd.mode} pid={cmd.pid} desc={desc}")

    print("\nstarting poll loop; ctrl-c to stop\n")

    try:
        while running:
            loop_ts = datetime.now().isoformat()
            print(f"\n[{loop_ts}] --- poll start ---")

            for cmd in standard_named:
                try:
                    response = connection.query(cmd)
                    print(f"[{loop_ts}] {cmd.name:<30} {fmt_response(response)}")
                except Exception as exc:
                    print(f"[{loop_ts}] {cmd.name:<30} ERROR: {exc}")

            time.sleep(args.interval)

    finally:
        print(f"\n[{datetime.now().isoformat()}] closing connection")
        connection.close()


if __name__ == "__main__":
    main()
