#!/usr/bin/env python3
"""
Servidor HTTP básico para la interfaz web del sistema de monitoreo IoT.
Interpreta cabeceras HTTP, maneja GET/POST y devuelve códigos de estado correctos.
"""
import os
import socket
import requests
from flask import Flask, request, redirect, url_for, session, render_template_string

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-me-in-production")

MONITOR_HOST = os.environ.get("MONITOR_HOST", "localhost")
MONITOR_PORT = int(os.environ.get("MONITOR_PORT", "8888"))
AUTH_SERVICE_URL = os.environ.get("AUTH_SERVICE_URL", "http://localhost:5000")
WEB_USER = os.environ.get("WEB_BACKEND_USER", "web")
WEB_PASS = os.environ.get("WEB_BACKEND_PASS", "websecret")


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


def query_monitor_server():
    """Conecta al servidor C por TCP, autentica como 'web' y obtiene estado y sensores."""
    try:
        # Resolución de nombres (sin IP hardcodeada)
        addrinfo = socket.getaddrinfo(MONITOR_HOST, MONITOR_PORT, socket.AF_UNSPEC, socket.SOCK_STREAM)
        if not addrinfo:
            return None, "No se pudo resolver el host del servidor"
        family, socktype, proto, canonname, sockaddr = addrinfo[0]
        sock = socket.socket(family, socktype, proto)
        sock.settimeout(5.0)
        sock.connect(sockaddr)
        # LOGIN
        sock.sendall(f"LOGIN|{WEB_USER}|{WEB_PASS}\r\n".encode())
        line = recv_line(sock)
        if "OK|LOGIN" not in line:
            sock.close()
            return None, "Error de autenticación con el servidor de monitoreo"
        # QUERY_STATUS
        sock.sendall(b"QUERY_STATUS\r\n")
        status_line = recv_line(sock)
        # QUERY_SENSORS
        sock.sendall(b"QUERY_SENSORS\r\n")
        sensors_line = recv_line(sock)
        sock.close()
        return {"status": status_line, "sensors": sensors_line}, None
    except socket.gaierror as e:
        return None, f"Error de resolución de nombres: {e}"
    except (socket.timeout, socket.error, OSError) as e:
        return None, str(e)


LOGIN_HTML = """
<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <title>Login - Monitoreo IoT</title>
  <style>
    body { font-family: sans-serif; max-width: 400px; margin: 2rem auto; padding: 1rem; }
    input { display: block; width: 100%; margin: 0.5rem 0; padding: 0.5rem; box-sizing: border-box; }
    button { padding: 0.5rem 1rem; background: #07c; color: white; border: none; cursor: pointer; }
    .error { color: red; margin-bottom: 1rem; }
  </style>
</head>
<body>
  <h1>Iniciar sesión</h1>
  {% if error %}<p class="error">{{ error }}</p>{% endif %}
  <form method="POST" action="/login">
    <label>Usuario</label>
    <input type="text" name="user" required>
    <label>Contraseña</label>
    <input type="password" name="password" required>
    <button type="submit">Entrar</button>
  </form>
</body>
</html>
"""

DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <title>Dashboard - Monitoreo IoT</title>
  <style>
    body { font-family: sans-serif; max-width: 800px; margin: 2rem auto; padding: 1rem; }
    table { border-collapse: collapse; width: 100%%; margin: 1rem 0; }
    th, td { border: 1px solid #ccc; padding: 0.5rem; text-align: left; }
    .error { color: red; }
    .meta { color: #666; font-size: 0.9rem; }
    a { color: #07c; }
  </style>
</head>
<body>
  <h1>Estado del sistema</h1>
  <p class="meta">Usuario: {{ user }} | <a href="/logout">Cerrar sesión</a></p>
  {% if err %}
  <p class="error">{{ err }}</p>
  {% else %}
  <h2>Estado general</h2>
  <p>{{ status }}</p>
  <h2>Sensores activos</h2>
  {% if sensors_list %}
  <table>
    <thead><tr><th>ID</th><th>Tipo</th><th>Ubicación</th></tr></thead>
    <tbody>
    {% for s in sensors_list %}
    <tr><td>{{ s.id }}</td><td>{{ s.type }}</td><td>{{ s.location }}</td></tr>
    {% endfor %}
    </tbody>
  </table>
  {% else %}
  <p>No hay sensores activos.</p>
  {% endif %}
  {% endif %}
</body>
</html>
"""


@app.route("/")
def index():
    if session.get("user"):
        return redirect(url_for("dashboard"))
    return render_template_string(LOGIN_HTML)


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return redirect(url_for("index"))
    user = request.form.get("user", "").strip()
    password = request.form.get("password", "")
    if not user:
        return render_template_string(LOGIN_HTML, error="Usuario requerido")
    try:
        r = requests.get(
            f"{AUTH_SERVICE_URL.rstrip('/')}/validate",
            params={"user": user, "password": password},
            timeout=5,
        )
        if r.status_code == 200 and "valid=true" in r.text:
            session["user"] = user
            return redirect(url_for("dashboard"))
    except requests.RequestException:
        pass
    return render_template_string(LOGIN_HTML, error="Credenciales inválidas")


@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("index"))


@app.route("/dashboard")
def dashboard():
    if not session.get("user"):
        return redirect(url_for("index"))
    data, err = query_monitor_server()
    sensors_list = []
    status = ""
    if data:
        status = data["status"]
        raw = data["sensors"]
        if raw.startswith("SENSOR_LIST|") and len(raw) > 11:
            part = raw[11:]
            for block in part.split(";"):
                if not block:
                    continue
                fields = block.split(",", 2)
                if len(fields) >= 3:
                    sensors_list.append({"id": fields[0], "type": fields[1], "location": fields[2]})
                elif len(fields) == 2:
                    sensors_list.append({"id": fields[0], "type": fields[1], "location": "-"})
    return render_template_string(
        DASHBOARD_HTML,
        user=session.get("user"),
        status=status,
        sensors_list=sensors_list,
        err=err,
    )


if __name__ == "__main__":
    port = int(os.environ.get("WEB_PORT", 8080))
    host = os.environ.get("WEB_HOST", "0.0.0.0")
    app.run(host=host, port=port, debug=False)
