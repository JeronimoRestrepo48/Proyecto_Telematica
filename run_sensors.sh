#!/bin/bash
# Lanza 5 sensores simulados (3 Python + 2 Java) contra el servidor.
# Uso: ./run_sensors.sh [host] [port]
# Requiere: servidor en ejecución, Python3, Java (javac/java).
HOST="${1:-localhost}"
PORT="${2:-8888}"
BASE="$(dirname "$0")"
cd "$BASE"
echo "Iniciando 5 sensores contra $HOST:$PORT"
python3 clients/python/sensor_simulator.py --host "$HOST" --port "$PORT" --type temperatura --id s1 --location "Sala A1" &
python3 clients/python/sensor_simulator.py --host "$HOST" --port "$PORT" --type humedad --id s2 --location "Sala A2" &
python3 clients/python/sensor_simulator.py --host "$HOST" --port "$PORT" --type presion --id s3 --location "Exterior" &
if command -v javac &>/dev/null && command -v java &>/dev/null; then
  (cd clients/java && javac -encoding UTF-8 SensorSimulator.java 2>/dev/null; java SensorSimulator --host "$HOST" --port "$PORT" --type vibracion --id s4 --location "Maquina 1") &
  (cd clients/java && java SensorSimulator --host "$HOST" --port "$PORT" --type consumo --id s5 --location "Cuadro electrico") &
else
  python3 clients/python/sensor_simulator.py --host "$HOST" --port "$PORT" --type vibracion --id s4 --location "Maquina 1" &
  python3 clients/python/sensor_simulator.py --host "$HOST" --port "$PORT" --type consumo --id s5 --location "Cuadro electrico" &
fi
echo "Sensores en segundo plano. Para detener: pkill -f sensor_simulator; pkill -f SensorSimulator"
