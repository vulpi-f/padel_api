#!/usr/bin/env python3
"""
Bridge BLE per Windows usando direttamente le API WinRT via pacchetto `winrt`,
senza Bleak. Richiede: pip install winrt

Esegue:
- connessione al MAC target
- ricerca caratteristica notify (preferita, poi prima notify disponibile)
- abilita notify e stampa i payload grezzi
- riconnessione rapida se cade
"""

import asyncio
import os
import sys
from typing import Optional

# WinRT namespaces
from winrt.windows.devices.bluetooth import (
    BluetoothLEDevice,
    BluetoothCacheMode,
    BluetoothConnectionStatus,
    BluetoothAddressType,
)
from winrt.windows.devices.bluetooth.genericattributeprofile import (
    GattCommunicationStatus,
    GattClientCharacteristicConfigurationDescriptorValue,
    GattCharacteristicProperties,
)
from winrt.windows.storage.streams import DataReader

TARGET_ADDR = os.getenv("BLE_TARGET_ADDRESS", "16:11:28:03:1C:81").upper()
PREFERRED_UUID = os.getenv("BLE_NOTIFY_CHAR_UUID", "00001c0f-d102-11e1-9b23-000efb0000b2")
RETRY_DELAY_S = float(os.getenv("BLE_RETRY_DELAY", "1"))


def mac_to_int(mac: str) -> int:
    return int(mac.replace(":", "").replace("-", ""), 16)


async def connect_device(addr: str):
    try:
        dev = None
        for addr_type in (BluetoothAddressType.PUBLIC, BluetoothAddressType.RANDOM):
            try:
                dev = await BluetoothLEDevice.from_bluetooth_address_async(
                    mac_to_int(addr), addr_type
                )
                if dev:
                    break
            except Exception:
                dev = None
        if dev is None:
            print("Device non trovato")
            return None
        # forza refresh servizi (uncached)
        await dev.get_gatt_services_async(BluetoothCacheMode.UNCACHED)
        print(f"Connesso a {dev.name or 'device'}")
        return dev
    except Exception as exc:
        print(f"Connect failed: {exc}")
        return None


async def find_notify_char(dev, preferred: str) -> Optional[object]:
    services_result = await dev.get_gatt_services_async(BluetoothCacheMode.UNCACHED)
    if services_result.status != GattCommunicationStatus.SUCCESS:
        return None

    for svc in services_result.services:
        chars_result = await svc.get_characteristics_async(BluetoothCacheMode.UNCACHED)
        if chars_result.status != GattCommunicationStatus.SUCCESS:
            continue
        # preferita
        for ch in chars_result.characteristics:
            if str(ch.uuid).lower() == preferred.lower() and ch.characteristic_properties & GattCharacteristicProperties.NOTIFY:
                return ch
        # fallback prima notify
        for ch in chars_result.characteristics:
            if ch.characteristic_properties & GattCharacteristicProperties.NOTIFY:
                return ch
    return None


def on_value_changed(sender, args):
    try:
        reader = DataReader.from_buffer(args.characteristic_value)
        buf = bytes(reader.read_bytes(reader.unconsumed_buffer_length))
        print(f"[BLE] {buf.hex(' ')}")
    except Exception as exc:
        print(f"Parse error: {exc}")


async def run():
    while True:
        dev = await connect_device(TARGET_ADDR)
        if dev is None:
            await asyncio.sleep(RETRY_DELAY_S)
            continue
        try:
            ch = await find_notify_char(dev, PREFERRED_UUID)
            if ch is None:
                raise RuntimeError("Notify characteristic non trovata")

            ch.add_value_changed(on_value_changed)
            status = await ch.write_client_characteristic_configuration_descriptor_async(
                GattClientCharacteristicConfigurationDescriptorValue.NOTIFY
            )
            if status != GattCommunicationStatus.SUCCESS:
                raise RuntimeError(f"Abilitazione notify fallita: {status}")

            print(f"In ascolto su {ch.uuid} (CTRL+C per uscire)")
            while dev.connection_status == BluetoothConnectionStatus.CONNECTED:
                await asyncio.sleep(0.2)
            raise RuntimeError("Connessione persa")
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            print(f"Errore: {exc}")
        finally:
            try:
                dev and dev.close()
            except Exception:
                pass
        await asyncio.sleep(RETRY_DELAY_S)


def main():
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        print("Interrotto da tastiera.")


if __name__ == "__main__":
    main()
