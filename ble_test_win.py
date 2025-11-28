#!/usr/bin/env python3
"""
Listener BLE per Windows che replica il comportamento di app.py su Ubuntu.
Si connette al dispositivo, sottoscrive la caratteristica di notify e
stampa gli eventi (SHORT/LONG + colore) gia' decodificati.
"""

import asyncio
import os
import sys
from typing import Optional

from bleak import BleakClient, BleakScanner

# --- CONFIG ---
TARGET_ADDR = os.getenv("BLE_TARGET_ADDRESS", "16:11:28:03:1C:81").upper()
# Lascia vuoto per auto-selezionare la prima caratteristica con notify
NOTIFY_CHAR_UUID = os.getenv("BLE_NOTIFY_CHAR_UUID", "").strip() or None
PREFERRED_UUID = "00001c0f-d102-11e1-9b23-000efb0000b2"

BUTTON_CODES = {
    0x08: "BLU",
    0x04: "RED",
    0x01: "YEL",
    0x02: "GRN",
    0x10: "CNT",
}
PRESS_TYPE_CODES = {0xA1: "SHORT", 0xA3: "LONG"}

last_button: Optional[str] = None
last_press_type: Optional[str] = None


def parse_data(data: bytearray) -> Optional[str]:
    """
    Replica la logica di app.py: ogni notifica contiene un byte di tipo
    press e/o un byte di bottone; si accoppiano per comporre il messaggio.
    """
    global last_button, last_press_type
    for b in data:
        if b in PRESS_TYPE_CODES:
            last_press_type = PRESS_TYPE_CODES[b]
        elif b in BUTTON_CODES:
            last_button = BUTTON_CODES[b]
        else:
            print(f"[WARN] Codice sconosciuto: 0x{b:02X}")

    if last_button and last_press_type:
        msg = f"{last_press_type} PRESS : {last_button}"
        last_button = None
        last_press_type = None
        return msg
    return None


def notification_handler(sender: int, data: bytearray):
    msg = parse_data(data)
    if msg:
        print(f"[BLE] {msg}")
    else:
        # utile per debugging se il parsing non produce output
        print(f"[RAW] {sender}: {data.hex(' ')}")


async def wait_for_device(address: str):
    """
    Attende che il device compaia nello scan per evitare connect falliti.
    """
    print(f"Scanning per {address} ...")
    device = await BleakScanner.find_device_by_address(address, timeout=8.0)
    if device is None:
        print("Device non trovato. Verifica che sia acceso e vicino.")
    else:
        print(f"Trovato {device.name or 'device'} @ {device.address}")
    return device


def pick_notify_char(services, preferred: str | None) -> str | None:
    """Cerca una caratteristica con notify. Se preferred e' presente la usa."""
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


async def run_listener(address: str, char_uuid: str | None):
    """
    Versione semplice: come app.py ma con uno scan rapido prima di connettere.
    """
    while True:
        device = await wait_for_device(address)
        if device is None:
            await asyncio.sleep(3)
            continue

        try:
            async with BleakClient(device.address, timeout=8.0, use_cached=False) as client:
                if not client.is_connected:
                    raise RuntimeError("Connessione BLE fallita")
                print(f"Connesso a {client.address}")

                # Lettura servizi (compatibile con versioni senza get_services)
                try:
                    services = await client.get_services()  # type: ignore[attr-defined]
                except AttributeError:
                    services = client.services

                selected_char = char_uuid or pick_notify_char(services, PREFERRED_UUID)
                if not selected_char:
                    raise RuntimeError("Nessuna caratteristica con notify trovata")

                await client.start_notify(selected_char, notification_handler)
                print(f"In ascolto delle notifiche su {selected_char} (CTRL+C per uscire)...")

                try:
                    while True:
                        if not client.is_connected:
                            raise RuntimeError("Connessione persa")
                        await asyncio.sleep(1)
                finally:
                    try:
                        await client.stop_notify(selected_char)
                    except Exception:
                        pass
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            print(f"[ERRORE] {exc}")
            print("Riprovo tra 5 secondi...")
            await asyncio.sleep(5)

def main():
    if sys.platform.startswith("win") and hasattr(
        asyncio, "WindowsSelectorEventLoopPolicy"
    ):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    try:
        asyncio.run(run_listener(TARGET_ADDR, NOTIFY_CHAR_UUID))
    except KeyboardInterrupt:
        print("Uscita richiesta da tastiera.")


if __name__ == "__main__":
    main()
