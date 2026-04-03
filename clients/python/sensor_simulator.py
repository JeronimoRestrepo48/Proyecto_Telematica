#!/usr/bin/env python3
"""
Simulador de sensor IoT. Se conecta al servidor por nombre de dominio (resolución DNS),
registra el sensor y envía mediciones periódicas.
"""
import socket
import time
import random
import sys
import argparse

def resolve_and_connect(host, port):
    addrinfo = socket.getaddrinfo(host, port, socket.AF_UNSPEC, socket.SOCK_STREAM)
    if not addrinfo:
        raise OSError(f"No se pudo resolver el host: {host}")
    family, socktype, proto, canonname, sockaddr = addrinfo[0]
    sock = socket.socket(family, socktype, proto)
    sock.settimeout(10.0)
    sock.connect(sockaddr)
    return sock

def recv_line(sock):
    buf = b""
    while b"\r\n" not in buf and b"\n" not in buf:
        try:
            data = sock.recv(1)
            if not data:
                break
            buf += data
        except (socket.timeout, socket.error):
            break
    return buf.decode("utf-8", errors="ignore").strip()

def send_cmd(sock, cmd):
    sock.sendall((cmd + "\r\n").encode())
    return recv_line(sock)

def main():
    parser = argparse.ArgumentParser(description="Simulador de sensor IoT")
    parser.add_argument("--host", default="localhost", help="Host del servidor (nombre o IP)")
    parser.add_argument("--port", type=int, default=8888, help="Puerto del servidor")
    parser.add_argument("--type", default="temperatura",
                        choices=["temperatura", "humedad", "presion", "vibracion", "consumo"],
                        help="Tipo de sensor")
    parser.add_argument("--id", default=None, help="ID del sensor (por defecto sensor_<tipo>_<random>)")
    parser.add_argument("--location", default="Ubicacion default", help="Ubicación del sensor")
    parser.add_argument("--interval", type=float, default=5.0, help="Intervalo entre mediciones (segundos)")
    args = parser.parse_args()

    sensor_id = args.id or f"sensor_{args.type}_{random.randint(1000, 9999)}"

    while True:
        try:
            sock = resolve_and_connect(args.host, args.port)
        except (socket.gaierror, OSError) as e:
            print(f"Error de conexión (resolución o red): {e}. Reintento en 5s...")
            time.sleep(5)
            continue

        try:
            resp = send_cmd(sock, f"REGISTER|{args.type}|{sensor_id}|{args.location}")
            if not resp.startswith("OK|REGISTER"):
                print(f"Registro fallido: {resp}")
                sock.close()
                time.sleep(5)
                continue
            print(f"Registrado: {sensor_id} ({args.type}) en {args.location}")
        except (socket.timeout, socket.error, OSError) as e:
            print(f"Error en registro: {e}")
            sock.close()
            time.sleep(5)
            continue

        # Rangos por tipo (para simulación; ocasionalmente fuera de rango para alertas)
        ranges = {
            "temperatura": (15.0, 45.0),
            "humedad": (30.0, 95.0),
            "presion": (1005.0, 1025.0),
            "vibracion": (0.0, 12.0),
            "consumo": (100.0, 5200.0),
        }
        lo, hi = ranges.get(args.type, (0.0, 100.0))

        while True:
            try:
                time.sleep(args.interval)
                # 90% valor normal, 10% posible anomalía
                if random.random() < 0.9:
                    value = round(random.uniform(lo, hi), 2)
                else:
                    value = round(random.uniform(lo, hi * 1.2), 2)
                ts = int(time.time())
                resp = send_cmd(sock, f"MEASUREMENT|{sensor_id}|{args.type}|{value}|{ts}")
                if not resp.startswith("OK"):
                    print(f"Medición rechazada: {resp}")
                else:
                    print(f"Enviado: {value} @ {ts} -> {resp[:50]}")
            except (socket.timeout, socket.error, OSError, BrokenPipeError) as e:
                print(f"Conexión perdida: {e}")
                break
        try:
            sock.close()
        except OSError:
            pass
        print("Reconectando en 5s...")
        time.sleep(5)

if __name__ == "__main__":
    main()
