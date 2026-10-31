import json
import time
import asyncio
import threading
import websockets
import paho.mqtt.client as mqtt

# --- Store connected WebSocket clients ---
clients = set()

# --- MQTT topic (MUST match Arduino) ---
MQTT_TOPIC = "demihu/feeds/insole"   # change if needed

# --- once-a-second printout ---
stats = {"start": time.time(), "samples": 0}

# --- MQTT callbacks ---
def on_connect(client, userdata, flags, rc):
    print("Connected to HiveMQ broker")
    client.subscribe(MQTT_TOPIC)

def parse_samples(payload):
    """Firmware sends batches: samples separated by ';', each "millis,PD1,...,PD8".
    Older firmware sends one "PD1,...,PD8" per message; it gets the arrival time instead."""
    samples = []
    for part in payload.split(";"):
        values = [int(x) for x in part.split(",")]
        if len(values) == 8:
            values = [int(time.time() * 1000)] + values
        if len(values) != 9:
            raise ValueError(f"expected 8 or 9 numbers, got {len(values)}")
        samples.append(values)
    return samples

def on_message(client, userdata, msg):
    try:
        samples = parse_samples(msg.payload.decode())
    except Exception as e:
        print("Parse error:", e)
        return

    stats["samples"] += len(samples)
    now = time.time()
    if now - stats["start"] >= 1:
        labels = [f"PD{i+1}" for i in range(8)]
        print(f"{stats['samples'] / (now - stats['start']):.0f} samples/s, latest:")
        print(" | ".join(f"{label:^8}" for label in labels))
        print("-" * (len(labels) * 11))
        print(" | ".join(f"{value:^8}" for value in samples[-1][1:]))
        print("\n")
        stats["start"], stats["samples"] = now, 0

    # safe async handoff
    asyncio.run_coroutine_threadsafe(
        send_to_clients(samples),
        loop
    )

async def send_to_clients(samples):
    if clients:
        message = json.dumps({"samples": samples})
        await asyncio.gather(*[c.send(message) for c in clients])

# --- MQTT client setup (NO AUTH for HiveMQ public broker) ---
mqtt_client = mqtt.Client()
mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message

mqtt_client.connect("broker.hivemq.com", 1883, 60)

# --- WebSocket server handler ---
async def ws_handler(websocket):
    clients.add(websocket)
    print("WebSocket client connected")
    try:
        async for _ in websocket:
            pass
    finally:
        clients.remove(websocket)
        print("WebSocket client disconnected")

async def main():
    global loop
    loop = asyncio.get_running_loop()

    # WebSocket server
    server = await websockets.serve(ws_handler, "localhost", 6790)
    print("WebSocket server running on ws://localhost:6790")

    # MQTT loop in background thread
    threading.Thread(target=mqtt_client.loop_forever, daemon=True).start()

    await asyncio.Future()

# --- Run ---
asyncio.run(main())