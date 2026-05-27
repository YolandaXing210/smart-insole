import asyncio
import json
import threading

try:
    import websockets
except ModuleNotFoundError as exc:
    missing_package = exc.name or "a required package"
    raise SystemExit(
        "Missing dependency: "
        f"{missing_package}\n"
        "Install the project requirements with:\n"
        "python3 -m pip install -r requirements.txt"
    ) from exc


class DashboardBridge:
    def __init__(self, ws_host="127.0.0.1", ws_port=6790):
        self.ws_host = ws_host
        self.ws_port = ws_port
        self.clients = set()
        self.loop = None
        self.latest_values = None

    async def send_to_clients(self, values):
        if not self.clients:
            return

        message = json.dumps(values)
        disconnected = []

        for client in self.clients:
            try:
                await client.send(message)
            except websockets.ConnectionClosed:
                disconnected.append(client)

        for client in disconnected:
            self.clients.discard(client)

    def push_values(self, values):
        self.latest_values = values
        if self.loop is None:
            return
        asyncio.run_coroutine_threadsafe(self.send_to_clients(values), self.loop)

    @staticmethod
    def print_values(values):
        labels = [f"PD{i + 1}" for i in range(len(values))]
        print(" | ".join(f"{label:^8}" for label in labels))
        print("-" * (len(labels) * 11))
        print(" | ".join(f"{value:^8}" for value in values))
        print()

    async def ws_handler(self, websocket):
        self.clients.add(websocket)
        print("WebSocket client connected")
        try:
            if self.latest_values is not None:
                await websocket.send(json.dumps(self.latest_values))
            async for _ in websocket:
                pass
        finally:
            self.clients.discard(websocket)
            print("WebSocket client disconnected")

    async def run(self, worker, mode_label):
        self.loop = asyncio.get_running_loop()
        await websockets.serve(self.ws_handler, self.ws_host, self.ws_port)
        print(f"WebSocket server running on ws://{self.ws_host}:{self.ws_port}")
        print(f"Starting {mode_label}")
        threading.Thread(target=worker, daemon=True).start()
        await asyncio.Future()
