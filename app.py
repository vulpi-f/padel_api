#!/usr/bin/env python3

import os
import asyncio
import sys

import aioconsole
from quart import Quart, render_template, websocket, url_for
from bleak import BleakClient
import json

# --- CONFIGURAZIONE ---
HOST = os.getenv("APP_HOST", "0.0.0.0")
PORT = int(os.getenv("APP_PORT", 5000))
TARGET_ADDRESS = os.getenv("BLE_TARGET_ADDRESS", "16:11:28:03:1C:81")
NOTIFY_CHAR_UUID = os.getenv("BLE_NOTIFY_CHAR_UUID", "00001c0f-d102-11e1-9b23-000efb0000b2")
USE_BLE = os.getenv("USE_BLE", "0") == "1"


ALLOWED_EXT = (".png", ".jpg", ".jpeg", ".gif", ".mp4", ".webm")
# per il ciclo dei banner
BANNERS_DIR = os.path.join(os.path.dirname(__file__), "static", "ads", "banners")
BANNER_FILES = sorted(
    f for f in os.listdir(BANNERS_DIR)
    if f.lower().endswith(ALLOWED_EXT)
)
current_banner_idx = 0

# percorso e lista FULLSCREEN ads
FULLSCREEN_DIR = os.path.join(os.path.dirname(__file__), "static", "ads", "fullscreen")
FULLSCREEN_FILES = sorted(
    f for f in os.listdir(FULLSCREEN_DIR)
    if f.lower().endswith(ALLOWED_EXT)
)
current_fs_idx = 0

# Mappature dei codici
BUTTON_CODES = {
    0x08: "BLU",
    0x04: "RED",
    0x01: "YEL",
    0x02: "GRN",
    0x10: "CNT",
}
PRESS_TYPE_CODES = {
    0xA1: "SHORT",
    0xA3: "LONG",
}

# Stato e variabili globali
clients = set()
last_button = None
last_press_type = None
ble_connected = False

# Istanza Quart
app = Quart(__name__, template_folder="templates")

# Funzioni di broadcast
async def broadcast_status(status: str):
    msg = f"STATUS:{status}"
    for ws in clients.copy():
        try:
            await ws.send(msg)
        except:
            clients.discard(ws)

async def broadcast_message(msg: str):
    for ws in clients.copy():
        try:
            await ws.send(msg)
        except:
            clients.discard(ws)

# Parsing dati BLE
def parse_data(data: bytearray) -> str:
    global last_button, last_press_type
    for b in data:
        if b in PRESS_TYPE_CODES:
            last_press_type = PRESS_TYPE_CODES[b]
        elif b in BUTTON_CODES:
            last_button = BUTTON_CODES[b]
        else:
            app.logger.warning(f"Codice sconosciuto: 0x{b:02X}")
    if last_button and last_press_type:
        msg = f"{last_press_type} PRESS : {last_button}"
        last_button = None
        last_press_type = None
        return msg
    return None

# Callback BLE
async def handle_notification(sender: int, data: bytearray):
    msg = parse_data(data)
    if msg:
        app.logger.info(f"Notifica BLE: {msg}")
        await broadcast_message(msg)

# Loop BLE
async def ble_loop():
    global ble_connected
    while True:
        try:
            async with BleakClient(TARGET_ADDRESS) as client:
                if not client.is_connected:
                    raise RuntimeError(f"Fallita connessione a {TARGET_ADDRESS}")
                app.logger.info(f"Connesso a {TARGET_ADDRESS}")
                ble_connected = True
                await broadcast_status("connesso")
                await client.start_notify(NOTIFY_CHAR_UUID, handle_notification)
                while client.is_connected:
                    await asyncio.sleep(1)
        except asyncio.CancelledError:
            break
        except Exception as e:
            app.logger.error(f"BLE error: {e}; riprovo in 5s")
        finally:
            ble_connected = False
            await broadcast_status("disconnesso, reconnecting...")
            try:
                await client.stop_notify(NOTIFY_CHAR_UUID)
            except:
                pass
            app.logger.info("Connessione BLE chiusa, prossima riconnessione in 5s")
        await asyncio.sleep(5)

# --- aggiungi queste mappe in alto vicino alle altre ---
PRESS_ABBR = {'S': 'SHORT', 'L': 'LONG'}
BUTTON_ABBR = {'R': 'RED', 'B': 'BLU', 'Y': 'YEL', 'G': 'GRN', 'C': 'CNT'}

DEFAULT_PRESS = "SHORT"

def parse_keyboard_line(line: str) -> str | None:
    tokens = line.strip().upper().split()

    # Caso 1: input tipo "SHORT BLU"
    if (len(tokens) == 2 and
        tokens[0] in PRESS_TYPE_CODES.values() and
        tokens[1] in BUTTON_CODES.values()):
        return f"{tokens[0]} PRESS : {tokens[1]}"

    # Caso 2: input tipo "S R"
    if (len(tokens) == 2 and
        tokens[0] in PRESS_ABBR and
        tokens[1] in BUTTON_ABBR):
        press = PRESS_ABBR[tokens[0]]
        button = BUTTON_ABBR[tokens[1]]
        return f"{press} PRESS : {button}"

    # Caso 3: input tipo "SR"
    if len(tokens) == 1 and len(tokens[0]) == 2:
        p, b = tokens[0][0], tokens[0][1]
        press = PRESS_ABBR.get(p)
        button = BUTTON_ABBR.get(b)
        if press and button:
            return f"{press} PRESS : {button}"

    # **NUOVO Caso 4: solo bottone -> SHORT automatico**
    if len(tokens) == 1:
        t = tokens[0]
        # Abbreviazione singola (R, B, Y, G, C)
        if t in BUTTON_ABBR:
            return f"{DEFAULT_PRESS} PRESS : {BUTTON_ABBR[t]}"
        # Nome completo (RED, BLU, YEL, GRN, CNT)
        if t in BUTTON_CODES.values():
            return f"{DEFAULT_PRESS} PRESS : {t}"

    return None

# Loop Tastiera (simulazione BLE)
async def keyboard_loop():
    await broadcast_status("modalità tastiera attiva")
    app.logger.info("Keyboard simulation mode active")
    while True:
        try:
            line = await aioconsole.ainput("Simula input (es. SR, LB, SHORT BLU): ")
        except (EOFError, asyncio.CancelledError):
            break
        if not line:
            continue

        msg = parse_keyboard_line(line)
        if msg:
            app.logger.info(f"Simulated BLE: {msg}")
            await broadcast_message(msg)
        else:
            app.logger.warning(f"Input non valido: {line}")

# Endpoint WebSocket
@app.websocket("/ws")
async def ws():
    ws_obj = websocket._get_current_object()
    clients.add(ws_obj)
    try:
        # Invia stato iniziale a connessione
        if USE_BLE:
            status = "connesso" if ble_connected else "disconnesso, reconnecting..."
        else:
            status = "modalità tastiera"
        await ws_obj.send(f"STATUS:{status}")
        # Mantiene viva la connessione
        while True:
            await asyncio.sleep(30)
    finally:
        clients.discard(ws_obj)

# Rotta principale
@app.route("/")
async def index():
    global current_banner_idx
    banner = None
    if BANNER_FILES:
        banner = BANNER_FILES[current_banner_idx]
        current_banner_idx = (current_banner_idx + 1) % len(BANNER_FILES)

    global current_fs_idx
    fs = None
    if FULLSCREEN_FILES:
        fs = FULLSCREEN_FILES[current_fs_idx]
        current_fs_idx = (current_fs_idx + 1) % len(FULLSCREEN_FILES)

    return await render_template(
        "index.html",
        ad_banner=banner,
        banners_json=json.dumps(BANNER_FILES),
        fs_ad=fs,
        fullscreens_json=json.dumps(FULLSCREEN_FILES)
    )

# Avvio controller
@app.before_serving
async def startup():
    loop = asyncio.get_event_loop()
    if USE_BLE:
        loop.create_task(ble_loop())
    else:
        loop.create_task(keyboard_loop())

# Avvio app
if __name__ == "__main__":
    try:
        app.run(debug=True,host=HOST, port=PORT)
    except (KeyboardInterrupt, SystemExit):
        sys.exit(0)
