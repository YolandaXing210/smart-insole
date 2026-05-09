# USAGE
# in this directory, run python mqttbridge.py, or run directly from vscode


import json
import asyncio
import threading
import websockets
import paho.mqtt.client as mqtt
from dotenv import load_dotenv
import os

# --- Adafruit IO credentials ---
load_dotenv()  # reads .env from current directory

ADAFRUIT_IO_USERNAME = os.getenv("ADAFRUIT_IO_USERNAME")
ADAFRUIT_IO_KEY = os.getenv("ADAFRUIT_IO_KEY")

# --- Store connected WebSocket clients ---
clients = set()

# --- MQTT callbacks ---
def on_connect(client, userdata, flags, rc):
    print("Connected to Adafruit IO, subscribing to feed")
    client.subscribe(f"{ADAFRUIT_IO_USERNAME}/feeds/insole")

def on_message(client, userdata, msg):
    values = [int(x) for x in msg.payload.decode().split(",")]

    # Create labels PD1–PD8 (or however many values you get)
    labels = [f"PD{i+1}" for i in range(len(values))]

    # Print header row (labels)
    print(" | ".join(f"{label:^8}" for label in labels))

    # Print separator
    print("-" * (len(labels) * 11))

    # Print values row (aligned)
    print(" | ".join(f"{value:^8}" for value in values))

    print()  # spacing between messages
    print()
    print()

    asyncio.run(send_to_clients(values))

async def send_to_clients(values):
    if clients:
        message = json.dumps(values)
        await asyncio.gather(*[client.send(message) for client in clients])

# --- MQTT client setup ---
mqtt_client = mqtt.Client()
mqtt_client.username_pw_set(ADAFRUIT_IO_USERNAME, ADAFRUIT_IO_KEY)
mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message
mqtt_client.connect("io.adafruit.com", 1883, 60)

# --- WebSocket server handler ---
async def ws_handler(websocket):
    clients.add(websocket)
    print("WebSocket client connected")
    try:
        async for _ in websocket:
            pass  # ignore messages from client
    finally:
        clients.remove(websocket)
        print("WebSocket client disconnected")

async def main():
    # Start WebSocket server
    server = await websockets.serve(ws_handler, "localhost", 6789)
    print("WebSocket server running on ws://localhost:6789")
    
    # Run MQTT client loop in another thread
    threading.Thread(target=mqtt_client.loop_forever, daemon=True).start()
    
    await asyncio.Future()  # run forever

# --- Run ---
asyncio.run(main())