# Sistema Distribuido de Monitoreo de Sensores IoT

Proyecto para la materia Internet: Arquitectura y Protocolos. Sistema con servidor central en C (sockets Berkeley), protocolo de aplicación propio, clientes en Python y Java, interfaz web e interfaz de operador con GUI, autenticación externa y despliegue en AWS.

## Estructura del proyecto

- **docs/PROTOCOLO.md** — Especificación completa del protocolo de aplicación.
- **server/** — Servidor central en C (Berkeley Sockets, hilos, logging). Ejecución: `./server puerto archivoDeLogs [auth_host [auth_port]]`.
- **auth_service/** — Servicio externo de autenticación (Python/Flask). No se almacenan usuarios en el servidor principal.
- **web_server/** — Servidor HTTP e interfaz web (login, estado, sensores activos).
- **clients/python/** — Simulador de sensores y cliente operador con GUI (Tkinter).
- **clients/java/** — Simulador de sensores en Java.

## Requisitos

- GCC, Make (servidor C).
- Python 3.8+ (auth, web, clientes Python).
- Java 8+ (clientes Java).
- Opcional: Docker para contenedores.

## Ejecución local (desarrollo)

1. **Servidor de autenticación** (puerto 5000):
   ```bash
   cd auth_service && pip install -r requirements.txt && python auth_server.py
   ```

2. **Servidor central** (puerto 8888):
   ```bash
   cd server && make && ./server 8888 server.log localhost 5000
   ```

3. **Interfaz web** (puerto 8080):
   ```bash
   cd web_server && pip install -r requirements.txt && python app.py
   ```
   Abrir http://localhost:8080 — usuario: `operador1`, contraseña: `secret123`.

4. **Sensores simulados** (al menos 5). En terminales separadas o en segundo plano:
   ```bash
   # Python
   cd clients/python
   python sensor_simulator.py --type temperatura --id s1 --location "Sala A1" &
   python sensor_simulator.py --type humedad --id s2 --location "Sala A2" &
   python sensor_simulator.py --type presion --id s3 --location "Exterior" &
   # Java
   cd clients/java
   javac -encoding UTF-8 SensorSimulator.java
   java SensorSimulator --type vibracion --id s4 --location "Maquina 1" &
   java SensorSimulator --type consumo --id s5 --location "Cuadro electrico" &
   ```

5. **Cliente operador (GUI)**:
   ```bash
   cd clients/python && python operator_client.py --host localhost --port 8888
   ```
   Conectar con usuario `operador1` y contraseña `secret123`.

## Despliegue en AWS

Ver **[docs/DESPLIEGUE_AWS.md](docs/DESPLIEGUE_AWS.md)** para instrucciones detalladas de configuración de EC2, puertos, DNS (Route 53) y ejecución del servidor en la instancia.

## Documentación del protocolo

Ver **[docs/PROTOCOLO.md](docs/PROTOCOLO.md)** para la especificación completa de mensajes, flujos y códigos de error.

## Configuración del dominio / DNS

En AWS se debe configurar un registro DNS (por ejemplo en Route 53) que apunte el nombre de dominio elegido a la IP elástica de la instancia EC2. El código no utiliza direcciones IP fijas; todos los servicios se localizan por nombre de host (resolución de nombres).
