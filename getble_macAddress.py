#!/usr/bin/env python3
import asyncio
from bleak import BleakScanner

# Secondi di scansione
SCAN_SECONDS = 8

# Dizionario MAC -> (device, adv_data)
found = {}

def cb(device, adv_data):
    """
    Callback chiamata ogni volta che viene ricevuto un advertising.
    Salviamo l'ultimo advertising visto per ogni MAC.
    """
    found[device.address] = (device, adv_data)

async def main():
    scanner = BleakScanner(cb)
    print(f"Scanning BLE per {SCAN_SECONDS} secondi...\n")

    await scanner.start()
    await asyncio.sleep(SCAN_SECONDS)
    await scanner.stop()

    print("\n--- RISULTATI ---")
    if not found:
        print("Nessun dispositivo trovato.")
        return

    for addr, (dev, adv) in found.items():
        # Nome: proviamo prima dev.name, poi adv.local_name
        name = getattr(dev, "name", None) or getattr(adv, "local_name", None)
        rssi = getattr(adv, "rssi", None)

        print("\n==============================")
        print(f"MAC : {addr}")
        print(f"NAME: {name}")
        if rssi is not None:
            print(f"RSSI: {rssi}")

        # MANUFACTURER DATA
        mdata = getattr(adv, "manufacturer_data", None)
        if mdata:
            print("MANUFACTURER DATA:")
            for cid, data in mdata.items():
                # cid = Company ID (manufacturer), data = bytes
                print(f"  CompanyID={cid}  Data={data.hex()}")

        # SERVICE DATA
        sdata = getattr(adv, "service_data", None)
        if sdata:
            print("SERVICE DATA:")
            for uuid, data in sdata.items():
                print(f"  UUID={uuid}  Data={data.hex()}")

        # SERVICE UUIDS
        suuids = getattr(adv, "service_uuids", None)
        if suuids:
            print("SERVICE UUIDS:")
            for uuid in suuids:
                print(f"  {uuid}")

        # TX POWER
        txp = getattr(adv, "tx_power", None)
        if txp is not None:
            print(f"TX POWER: {txp}")

if __name__ == "__main__":
    asyncio.run(main())
