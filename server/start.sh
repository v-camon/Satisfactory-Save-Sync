#!/bin/bash
set -e

echo "=== Iniciando Satisfactory Sync Server ==="

if [ -f "server/requirements.txt" ]; then
    echo "Instalando dependencias de server/requirements.txt..."
    python3 -m pip install -r server/requirements.txt
elif [ -f "requirements.txt" ]; then
    echo "Instalando dependencias de requirements.txt..."
    python3 -m pip install -r requirements.txt
fi

echo "Arrancando Uvicorn en el puerto ${SERVER_PORT:-8000}..."
export PYTHONUNBUFFERED=1
export PYTHONPATH=.
exec python3 -m uvicorn server.main:app --host 0.0.0.0 --port "${SERVER_PORT:-8000}" --log-level info