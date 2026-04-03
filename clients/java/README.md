# Clientes Java - Simuladores de sensores

Compilar y ejecutar (desde este directorio):

```bash
javac -encoding UTF-8 SensorSimulator.java
java SensorSimulator --host localhost --port 8888 --type humedad --location "Sala B2"
```

Opciones: `--host`, `--port`, `--type` (temperatura|humedad|presion|vibracion|consumo), `--id`, `--location`, `--interval` (segundos).

Para levantar varios sensores en segundo plano (ejemplo 2 sensores Java):

```bash
java SensorSimulator --type humedad --location "Sala B1" &
java SensorSimulator --type presion --location "Exterior" &
```
