# Instrucciones de despliegue en AWS

Este documento describe los pasos para desplegar el Sistema de Monitoreo IoT en Amazon Web Services.

## Requisitos previos

- Cuenta de AWS.
- Acceso a la consola de AWS (EC2, Route 53 si se usa DNS propio).
- Cliente SSH para acceso remoto a la instancia.

## 1. Crear una instancia de cómputo (EC2)

1. En la consola de AWS, ir a **EC2** > **Instancias** > **Iniciar instancia**.
2. Elegir una AMI: **Amazon Linux 2** o **Ubuntu Server** (recomendado para tener `gcc` y `make`).
3. Tipo de instancia: **t2.micro** (capa gratuita) o **t3.micro** según disponibilidad.
4. Configurar par de claves (key pair) para SSH y guardar el archivo `.pem`.
5. En **Configuración de red / Security group**:
   - Crear o editar el grupo de seguridad para permitir:
     - **SSH (22)** — su IP o 0.0.0.0/0 solo para pruebas.
     - **TCP 8888** — puerto del servidor de monitoreo (origen: 0.0.0.0/0 o restringido).
     - **TCP 8080** — interfaz web (origen: 0.0.0.0/0 o restringido).
     - **TCP 5000** — servicio de autenticación si corre en la misma instancia (origen: 127.0.0.1 o mismo SG).
6. Asignar **IP elástica** a la instancia (EC2 > Direcciones IP elásticas > Asociar) para que la IP no cambie al reiniciar.

## 2. Acceso remoto al servidor

```bash
chmod 400 mi-clave.pem
ssh -i mi-clave.pem ec2-user@<IP_ELASTICA>   # Amazon Linux
# o
ssh -i mi-clave.pem ubuntu@<IP_ELASTICA>     # Ubuntu
```

## 3. Instalar dependencias en la instancia

**Amazon Linux 2:**

```bash
sudo yum update -y
sudo yum install -y gcc make
sudo yum install -y python3 python3-pip
```

**Ubuntu:**

```bash
sudo apt update && sudo apt install -y build-essential
sudo apt install -y python3 python3-pip
```

## 4. Subir el código y compilar el servidor C

Desde su máquina local (con el código en el repo):

```bash
scp -i mi-clave.pem -r server auth_service web_server ec2-user@<IP_ELASTICA>:~/iot-monitor/
```

En la instancia:

```bash
cd ~/iot-monitor/server
make
# Verificar que existe el binario:
ls -la server
```

El servidor debe compilarse **en la instancia EC2** (no enviar binarios precompilados desde otra arquitectura).

## 5. Ejecución del servidor en la instancia

En la instancia EC2:

```bash
cd ~/iot-monitor/server
./server 8888 /home/ec2-user/iot-monitor/server.log localhost 5000
```

- **8888**: puerto del protocolo de aplicación (sensores y operadores).
- **server.log**: archivo de logs (ruta absoluta recomendada).
- **localhost** y **5000**: host y puerto del servicio de autenticación (mismo equipo).

Para ejecutar en segundo plano:

```bash
nohup ./server 8888 /home/ec2-user/iot-monitor/server.log localhost 5000 &
```

## 6. Servicio de autenticación e interfaz web en la instancia

En la misma instancia (o en otra si se configura DNS y seguridad):

```bash
cd ~/iot-monitor/auth_service
pip3 install --user -r requirements.txt
python3 auth_server.py &
# Por defecto escucha en 0.0.0.0:5000

cd ~/iot-monitor/web_server
pip3 install --user -r requirements.txt
MONITOR_HOST=localhost MONITOR_PORT=8888 AUTH_SERVICE_URL=http://localhost:5000 python3 app.py &
# Por defecto escucha en 0.0.0.0:8080
```

Asegurarse de que el security group permita tráfico en los puertos 5000 (si es público) y 8080.

## 7. Configuración del dominio o registro DNS (Route 53)

1. En **Route 53** > **Zonas alojadas**, crear una zona (o usar una existente).
2. Crear un **registro A** (o CNAME si lo prefiere):
   - Nombre: por ejemplo `monitor` o `iot.tudominio.com`.
   - Tipo: A.
   - Valor: **IP elástica** de la instancia EC2.
   - TTL: 300.
3. Apuntar el dominio (o subdominio) al registro creado.
4. En el código y en los clientes, usar el **nombre de dominio** (por ejemplo `monitor.tudominio.com`) en lugar de la IP; la resolución se hace por DNS (sin IPs hardcodeadas).

## 8. Acceso al sistema desde Internet

- **Interfaz web:** `http://<DOMINIO_O_IP>:8080`
- **Cliente operador / sensores:** conectar al host `DOMINIO_O_IP` y puerto **8888**.

Durante la sustentación se debe demostrar:

- Compilación y ejecución del programa del servidor en la instancia EC2 (en C).
- Ejecución del sistema (y del contenedor si se usa Docker).
- Acceso desde clientes externos (navegador, cliente operador, sensores) usando el nombre de dominio o la IP pública.

## 9. Opcional: contenedor Docker

Para empaquetar el servidor C (y opcionalmente auth y web) en un contenedor:

- Crear un `Dockerfile` en `server/` que instale `gcc`, `make`, copie el código, ejecute `make` y arranque `./server ...`.
- Construir la imagen en la instancia o en un registro (ECR) y ejecutar el contenedor en la instancia EC2.

Ejemplo mínimo para solo el servidor C:

```dockerfile
FROM amazonlinux:2
RUN yum install -y gcc make
WORKDIR /app
COPY . .
RUN make
EXPOSE 8888
CMD ["./server", "8888", "/app/server.log", "host.docker.internal", "5000"]
```

(En Linux, usar la IP del host en lugar de `host.docker.internal` si auth corre en el host.)

## 10. Troubleshooting y reinicio rapido (comandos usados en practicas)

### 10.1 Conexion SSH (Windows)

```bash
ssh -i "C:\Users\SAMUEL\Downloads\labsuser.pem" ubuntu@98.91.154.40
```

### 10.2 Reiniciar servicios en la instancia AWS

```bash
sudo fuser -k 5000/tcp
cd ~/Proyecto_Telematica/auth_service
nohup python3 auth_server.py > ~/auth.log 2>&1 &
disown

sudo docker start iot-server

sudo fuser -k 8080/tcp
cd ~/Proyecto_Telematica/web_server
nohup python3 app.py > ~/web.log 2>&1 &
disown
```

Verificacion basica:

```bash
sudo docker ps
ps aux | grep auth_server
```

### 10.3 Ejecutar simuladores de sensores (Windows, consola local)

```bash
cd C:\Users\SAMUEL\Downloads\Proyecto_Telematica\clients\python
python sensor_simulator.py --host iot-monitor.ddns.net --type temperatura --id s1 --location "Sala A1"
python sensor_simulator.py --host iot-monitor.ddns.net --type humedad --id s2 --location "Sala A2"
python sensor_simulator.py --host iot-monitor.ddns.net --type presion --id s3 --location "Exterior"
python sensor_simulator.py --host iot-monitor.ddns.net --type vibracion --id s4 --location "Maquina 1"
python sensor_simulator.py --host iot-monitor.ddns.net --type consumo --id s5 --location "Cuadro electrico"
```

Interfaz web:

```text
http://iot-monitor.ddns.net:8080
```

### 10.4 Ejecutar cliente operador (Windows, consola local)

```bash
cd C:\Users\SAMUEL\Downloads\Proyecto_Telematica\clients\python
python operator_client.py --host iot-monitor.ddns.net --port 8888
```

### 10.5 Si falla autenticacion o no responde web

Repetir este flujo:

```bash
sudo fuser -k 5000/tcp
cd ~/Proyecto_Telematica/auth_service
nohup python3 auth_server.py > ~/auth.log 2>&1 &
disown

cd ~/Proyecto_Telematica/web_server
```
