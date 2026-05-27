import argparse
import asyncio
import os
import ssl
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


def env(name, default=None, required=False):
    value = os.getenv(name, default)
    if required and not value:
        raise SystemExit(f"Missing required environment variable: {name}")
    return value


def truthy(value):
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def parse_args():
    default_port = env("PORT", env("WS_PORT", "6790"))
    parser = argparse.ArgumentParser(
        description="MQTT to WebSocket bridge for the smart insole dashboard."
    )
    parser.add_argument("--ws-host", default=env("WS_HOST", "0.0.0.0"))
    parser.add_argument("--ws-port", type=int, default=int(default_port))
    parser.add_argument("--mqtt-host", default=env("MQTT_HOST"))
    parser.add_argument("--mqtt-port", type=int, default=int(env("MQTT_PORT", "8883")))
    parser.add_argument("--mqtt-topic", default=env("MQTT_TOPIC", "smartinsole/data"))
    parser.add_argument("--mqtt-username", default=env("MQTT_USERNAME"))
    parser.add_argument("--mqtt-password", default=env("MQTT_PASSWORD"))
    parser.add_argument("--mqtt-client-id", default=env("MQTT_CLIENT_ID", "smart-insole-bridge"))
    parser.add_argument("--mqtt-keepalive", type=int, default=int(env("MQTT_KEEPALIVE", "60")))
    parser.add_argument("--mqtt-tls", default=env("MQTT_TLS", "true"))
    return parser.parse_args()


def build_mqtt_worker(bridge, args):
    if not args.mqtt_host:
        raise SystemExit("Provide MQTT_HOST or --mqtt-host with your HiveMQ Cloud cluster hostname.")

    mqtt_client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id=args.mqtt_client_id,
    )

    if args.mqtt_username:
        mqtt_client.username_pw_set(args.mqtt_username, args.mqtt_password)

    if truthy(args.mqtt_tls):
        mqtt_client.tls_set(cert_reqs=ssl.CERT_REQUIRED)

    def on_connect(client, userdata, flags, reason_code, properties):
        if reason_code.is_failure:
            print(f"MQTT connection failed: {reason_code}")
            return
        print(f"Connected to MQTT broker at {args.mqtt_host}:{args.mqtt_port}")
        client.subscribe(args.mqtt_topic)
        print(f"Subscribed to topic: {args.mqtt_topic}")

    def on_disconnect(client, userdata, disconnect_flags, reason_code, properties):
        print(f"MQTT disconnected: {reason_code}")

    def on_message(client, userdata, msg):
        raw_payload = msg.payload.decode().strip()
        try:
            values = [int(x) for x in raw_payload.split(",")]
        except ValueError:
            print(f"Skipping non-CSV payload on {msg.topic}: {raw_payload}")
            return

        bridge.print_values(values)
        bridge.push_values(values)

    mqtt_client.on_connect = on_connect
    mqtt_client.on_disconnect = on_disconnect
    mqtt_client.on_message = on_message

    def mqtt_loop():
        while True:
            try:
                mqtt_client.connect(args.mqtt_host, args.mqtt_port, args.mqtt_keepalive)
                mqtt_client.loop_forever()
            except Exception as exc:
                print(f"MQTT reconnecting after error: {exc}")
                time.sleep(3)

    return mqtt_loop


async def main():
    args = parse_args()
    bridge = DashboardBridge(ws_host=args.ws_host, ws_port=args.ws_port)
    await bridge.run(build_mqtt_worker(bridge, args), "HiveMQ Cloud bridge mode")


asyncio.run(main())
