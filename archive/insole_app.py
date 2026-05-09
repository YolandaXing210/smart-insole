import subprocess, sys, os, threading, tkinter as tk
from tkinter import ttk
import paho.mqtt.client as mqtt

# ── Config ──────────────────────────────────────────────────────────────
BROKER_HOST = "localhost"
BROKER_PORT = 1883
TOPIC       = "insole/data"
PD_NAMES    = ["PD1","PD2","PD3","PD4","PD5","PD6","PD7","PD8"]

# Path to mosquitto relative to this script
BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
MOSQ_EXE    = os.path.join(BASE_DIR, "mosquitto.exe")
MOSQ_CONF   = os.path.join(BASE_DIR, "mosquitto.conf")

# ── Start Mosquitto silently (no cmd window) ─────────────────────────────
def start_broker():
    subprocess.Popen(
        [MOSQ_EXE, "-c", MOSQ_CONF],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW   # Windows: hides the console
    )

# ── GUI ──────────────────────────────────────────────────────────────────
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Insole Sensor Monitor")
        self.resizable(False, False)
        self.configure(padx=20, pady=20)

        tk.Label(self, text="Insole Sensor Monitor",
                 font=("Segoe UI", 14, "bold")).grid(row=0, column=0,
                 columnspan=2, pady=(0,12))

        self.bars   = {}
        self.labels = {}

        for i, name in enumerate(PD_NAMES):
            tk.Label(self, text=name, width=5,
                     font=("Segoe UI", 10)).grid(row=i+1, column=0, sticky="w")
            bar = ttk.Progressbar(self, length=260, maximum=4095)
            bar.grid(row=i+1, column=1, padx=(8,0), pady=2)
            lbl = tk.Label(self, text="—", width=6,
                           font=("Segoe UI", 10))
            lbl.grid(row=i+1, column=2, padx=(6,0))
            self.bars[name]   = bar
            self.labels[name] = lbl

        self.status = tk.Label(self, text="Connecting...",
                               font=("Segoe UI", 9), fg="gray")
        self.status.grid(row=9, column=0, columnspan=3, pady=(12,0))

    def update_readings(self, values):
        for name, val in zip(PD_NAMES, values):
            self.bars[name]["value"]   = val
            self.labels[name].config(text=str(val))
        self.status.config(text="● Live", fg="green")

    def set_status(self, text, color="gray"):
        self.status.config(text=text, fg=color)

# ── MQTT callbacks ────────────────────────────────────────────────────────
def make_client(app):
    client = mqtt.Client()

    def on_connect(c, *_):
        c.subscribe(TOPIC)
        app.after(0, app.set_status, "● Live", "green")

    def on_disconnect(*_):
        app.after(0, app.set_status, "Reconnecting...", "orange")

    def on_message(c, userdata, msg):
        try:
            vals = [int(x) for x in msg.payload.decode().split(",")]
            app.after(0, app.update_readings, vals)
        except Exception:
            pass

    client.on_connect    = on_connect
    client.on_disconnect = on_disconnect
    client.on_message    = on_message
    return client

def mqtt_thread(client):
    while True:
        try:
            client.connect(BROKER_HOST, BROKER_PORT, keepalive=60)
            client.loop_forever()
        except Exception:
            import time; time.sleep(3)

# ── Main ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    start_broker()
    app    = App()
    client = make_client(app)
    threading.Thread(target=mqtt_thread, args=(client,), daemon=True).start()
    app.mainloop()