#!/usr/bin/env python3
"""
Listener BLE minimale e robusto per Windows.
Scopo: ottenere notifiche stabili dal device come avviene su Debian,
senza dipendere dal resto dell'app Quart.
"""

import asyncio
import logging
import os
import sys
from typing import Optional

from bleak import BleakClient

# --- Config ---
TARGET_ADDR = os.getenv("BLE_TARGET_ADDRESS", "16:11:28:03:1C:81").upper()
PREFERRED_UUID = os.getenv("BLE_NOTIFY_CHAR_UUID", "00001c0f-d102-11e1-9b23-000efb0000b2")
RETRY_DELAY_S = float(os.getenv("BLE_RETRY_DELAY", "1"))
CONNECT_TIMEOUT_S = float(os.getenv("BLE_CONNECT_TIMEOUT", "12"))

# Mappature device
BUTTON_CODES = {0x08: "BLU", 0x04: "RED", 0x01: "YEL", 0x02: "GRN", 0x10: "CNT"}
PRESS_TYPE_CODES = {0xA1: "SHORT", 0xA3: "LONG"}

last_button: Optional[str] = None
last_press_type: Optional[str] = None

# Event loop piu' stabile per Bleak su Windows (evita il Proactor loop)
if sys.platform.startswith("win") and hasattr(asyncio, "WindowsSelectorEventLoopPolicy"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("ble_bridge")


def parse_data(data: bytearray) -> Optional[str]:
    """Replica la logica di app.py (accoppia press + button)."""
    global last_button, last_press_type
    for b in data:
        if b in PRESS_TYPE_CODES:
            last_press_type = PRESS_TYPE_CODES[b]
        elif b in BUTTON_CODES:
            last_button = BUTTON_CODES[b]
        else:
            log.warning("Codice sconosciuto: 0x%02X", b)

    if last_button and last_press_type:
        msg = f"{last_press_type} PRESS : {last_button}"
        last_button = None
        last_press_type = None
        return msg
    return None


def notification_handler(sender: int, data: bytearray):
    msg = parse_data(data)
    if msg:
        log.info("[BLE] %s", msg)
    else:
        # utile per capire se arrivano pacchetti ma non si traducono in eventi
        log.debug("[RAW] %s %s", sender, data.hex(" "))


async def run():
    while True:
        try:
            addr = TARGET_ADDR
            async with BleakClient(addr, timeout=CONNECT_TIMEOUT_S, use_cached=False) as client:
                if not client.is_connected:
                    raise RuntimeError("Connessione BLE fallita")
                log.info("Connesso a %s", addr)

                await client.start_notify(PREFERRED_UUID, notification_handler)

                log.info("In ascolto su %s (CTRL+C per uscire)", PREFERRED_UUID)
                while client.is_connected:
                    await asyncio.sleep(0.2)
                raise RuntimeError("Connessione persa")
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            log.warning("Errore: %s", exc)
            await asyncio.sleep(RETRY_DELAY_S)


def main():
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        log.info("Interrotto da tastiera.")


if __name__ == "__main__":
    main()
