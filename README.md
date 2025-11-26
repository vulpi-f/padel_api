# Padel API

Applicazione web basata su Quart che legge eventi via BLE e li invia al frontend tramite WebSocket.

## Requisiti

- Python 3.11 (o compatibile)
- pip

## Installazione

```bash
python -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.venv\Scripts\Activate.ps1  # su Windows vedi README
pip install -r requirements.txt
```
## Configurazione

Variabili d'ambiente principali:

- APP_HOST (default: 0.0.0.0)

- APP_PORT (default: 5000)

- BLE_TARGET_ADDRESS

- BLE_NOTIFY_CHAR_UUID

- USE_BLE (1 per usare BLE, 0 per la modalità tastiera)

## Avvio

Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.venv\Scripts\Activate.ps1
python app.py

Poi apri http://localhost:5000 nel browser.