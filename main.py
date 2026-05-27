import argparse
import asyncio
import time

try:
    import paho.mqtt.client as mqtt
except ModuleNotFoundError as exc:
    missing_package = exc.name or "a required package"
    raise SystemExit(
        "Missing dependency: "
        f"{missing_package}\n"
        "Install the project requirements with:\n"
        "python3 -m pip install -r requirements.txt"
    ) from exc

from bridge_server import DashboardBridge


MQTT_TOPIC = "demihu/feeds/insole"


def parse_args():
    parser = argparse.ArgumentParser(
        description="MQTT WebSocket bridge for the smart insole dashboard."
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


def build_mqtt_worker(bridge):
    mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)

    def on_connect(client, userdata, flags, reason_code, properties):
        print("Connected to HiveMQ broker")
        client.subscribe(MQTT_TOPIC)

    def on_message(client, userdata, msg):
        try:
            values = [int(x) for x in msg.payload.decode().split(",")]
        except Exception as exc:
            print("Parse error:", exc)
            return

        bridge.print_values(values)
        bridge.push_values(values)

    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = on_message

    def mqtt_loop():
        while True:
            try:
                mqtt_client.connect("broker.hivemq.com", 1883, 60)
                mqtt_client.loop_forever()
            except Exception as exc:
                print(f"MQTT reconnecting after error: {exc}")
                time.sleep(3)

    return mqtt_loop


async def main():
    args = parse_args()
    bridge = DashboardBridge(ws_host=args.ws_host, ws_port=args.ws_port)
    await bridge.run(build_mqtt_worker(bridge), "MQTT mode")


asyncio.run(main())
