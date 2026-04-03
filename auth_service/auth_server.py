#!/usr/bin/env python3
"""
Servicio externo de autenticación. El servidor C no almacena usuarios;
consulta este servicio por nombre de host (resolución DNS) para validar
credenciales y obtener el rol.
"""
import os
from flask import Flask, request

app = Flask(__name__)

# Usuarios: en producción leer de archivo o variable de entorno.
# Formato: USER:password:rol
USERS = {
    "operador1": ("secret123", "operador"),
    "operador2": ("pass2", "operador"),
    "web": ("websecret", "operador"),  # Usuario para el backend de la interfaz web
}

@app.route("/validate", methods=["GET"])
def validate():
    user = request.args.get("user", "")
    password = request.args.get("password", "")
    if not user or not password:
        return "valid=false", 401, {"Content-Type": "text/plain"}
    if user in USERS and USERS[user][0] == password:
        return "valid=true", 200, {"Content-Type": "text/plain"}
    return "valid=false", 401, {"Content-Type": "text/plain"}

@app.route("/health", methods=["GET"])
def health():
    return "OK", 200

if __name__ == "__main__":
    port = int(os.environ.get("AUTH_PORT", 5000))
    host = os.environ.get("AUTH_HOST", "0.0.0.0")
    app.run(host=host, port=port, debug=False)
