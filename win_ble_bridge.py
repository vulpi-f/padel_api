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

from bleak import BleakClient, BleakScanner

# --- Config ---
TARGET_ADDR = os.getenv("BLE_TARGET_ADDRESS", "16:11:28:03:1C:81").upper()
PREFERRED_UUID = os.getenv("BLE_NOTIFY_CHAR_UUID", "00001c0f-d102-11e1-9b23-000efb0000b2")
SCAN_TIMEOUT_S = float(os.getenv("BLE_SCAN_TIMEOUT", "10"))
RETRY_DELAY_S = float(os.getenv("BLE_RETRY_DELAY", "5"))
CONNECT_TIMEOUT_S = float(os.getenv("BLE_CONNECT_TIMEOUT", "20"))
FAST_NOTIFY = os.getenv("BLE_FAST_NOTIFY", "1") == "1"  # se true, salta get_services

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


async def wait_for_device(address: str, timeout: float) -> Optional[str]:
    """Attende che il device appaia nello scan e restituisce l'indirizzo (upper)."""
    log.info("Scan %ss per %s ...", timeout, address)
    device = await BleakScanner.find_device_by_address(address, timeout=timeout)
    if device is None:
        log.error("Device non trovato")
        return None
    log.info("Trovato %s (%s)", device.name or "device", device.address)
    return device.address


def pick_notify_char(services, preferred: str | None) -> Optional[str]:
    """Seleziona una caratteristica notify (prima la preferita, poi la prima disponibile)."""
    if not services:
        return None

    if preferred:
        for svc in services:
            for ch in svc.characteristics:
                if ch.uuid.lower() == preferred.lower() and "notify" in ch.properties:
                    return ch.uuid

    for svc in services:
        for ch in svc.characteristics:
            if "notify" in ch.properties:
                return ch.uuid
    return None


async def run():
    while True:
        addr = await wait_for_device(TARGET_ADDR, SCAN_TIMEOUT_S)
        if not addr:
            await asyncio.sleep(RETRY_DELAY_S)
            continue

        try:
            async with BleakClient(addr, timeout=CONNECT_TIMEOUT_S, use_cached=False) as client:
                if not client.is_connected:
                    raise RuntimeError("Connessione BLE fallita")
                log.info("Connesso a %s", addr)

                char_uuid = PREFERRED_UUID
                services = None
                if not FAST_NOTIFY:
                    try:
                        services = await client.get_services()
                    except asyncio.CancelledError:
                        log.warning("get_services cancellato, uso UUID configurato")
                    except AttributeError:
                        services = getattr(client, "services", None)
                    except Exception as exc:
                        log.warning("get_services fallito (%s), continuo con UUID configurato", exc)

                if services:
                    char_uuid = pick_notify_char(services, PREFERRED_UUID) or PREFERRED_UUID
                if not char_uuid:
                    raise RuntimeError("Nessuna caratteristica notify trovata")

                await client.start_notify(char_uuid, notification_handler)
                log.info("In ascolto su %s (CTRL+C per uscire)", char_uuid)

                while True:
                    if not client.is_connected:
                        raise RuntimeError("Connessione persa")
                    await asyncio.sleep(1)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            log.error("Errore BLE: %s", exc)
            log.info("Riprovo tra %ss", RETRY_DELAY_S)
            await asyncio.sleep(RETRY_DELAY_S)


def main():
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        log.info("Interrotto da tastiera.")


if __name__ == "__main__":
    main()
