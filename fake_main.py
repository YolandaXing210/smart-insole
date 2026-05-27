import argparse
import asyncio
import math
import random
import time

from bridge_server import DashboardBridge


def parse_args():
    parser = argparse.ArgumentParser(
        description="Fake data WebSocket bridge for the smart insole dashboard."
    )
    parser.add_argument(
        "--ws-host",
        default="127.0.0.1",
        help="Host interface for the WebSocket server. Default: 127.0.0.1",
    )
    parser.add_argument(
        "--ws-port",
        type=int,
        default=6790,
        help="Port for the WebSocket server. Default: 6790",
    )
    return parser.parse_args()


def generate_fake_values(step):
    values = []
    for idx in range(8):
        wave = math.sin(step / 6 + idx * 0.55)
        offset = math.cos(step / 11 + idx * 0.3)
        noise = random.randint(-60, 60)
        raw = 1550 + int(420 * wave + 180 * offset) + noise
        values.append(max(700, min(2400, raw)))
    return values


def build_fake_worker(bridge):
    def fake_data_loop():
        step = 0
        while True:
            values = generate_fake_values(step)
            bridge.print_values(values)
            bridge.push_values(values)
            step += 1
            time.sleep(0.35)

    return fake_data_loop


async def main():
    args = parse_args()
    bridge = DashboardBridge(ws_host=args.ws_host, ws_port=args.ws_port)
    await bridge.run(build_fake_worker(bridge), "fake data mode")


asyncio.run(main())
