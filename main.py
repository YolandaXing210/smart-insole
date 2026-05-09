import json
import asyncio
import threading
import websockets
import paho.mqtt.client as mqtt

# --- Store connected WebSocket clients ---
clients = set()

# --- MQTT topic (MUST match Arduino) ---
MQTT_TOPIC = "demihu/feeds/insole"   # change if needed

# --- MQTT callbacks ---
def on_connect(client, userdata, flags, rc):
    print("Connected to HiveMQ broker")
    client.subscribe(MQTT_TOPIC)

def on_message(client, userdata, msg):
    try:
        values = [int(x) for x in msg.payload.decode().split(",")]
    except Exception as e:
        print("Parse error:", e)
        return

    labels = [f"PD{i+1}" for i in range(len(values))]

    print(" | ".join(f"{label:^8}" for label in labels))
    print("-" * (len(labels) * 11))
    print(" | ".join(f"{value:^8}" for value in values))
    print("\n\n")

    # safe async handoff
    asyncio.run_coroutine_threadsafe(
        send_to_clients(values),
        loop
    )

async def send_to_clients(values):
    if clients:
        message = json.dumps(values)
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
    server = await websockets.serve(ws_handler, "localhost", 6789)
    print("WebSocket server running on ws://localhost:6789")

    # MQTT loop in background thread
    threading.Thread(target=mqtt_client.loop_forever, daemon=True).start()

    await asyncio.Future()

# --- Run ---
asyncio.run(main())