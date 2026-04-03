#!/usr/bin/env python3
"""
Cliente operador con interfaz gráfica (Tkinter).
Muestra sensores activos, mediciones en tiempo real y alertas.
"""
import socket
import threading
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import argparse

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

class OperatorApp:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.sock = None
        self.running = False
        self.recv_thread = None

        self.root = tk.Tk()
        self.root.title("Cliente Operador - Monitoreo IoT")
        self.root.geometry("700x500")
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        # Login
        f_login = ttk.Frame(self.root, padding=10)
        f_login.pack(fill=tk.X)
        ttk.Label(f_login, text="Usuario:").pack(side=tk.LEFT, padx=(0, 5))
        self.entry_user = ttk.Entry(f_login, width=15)
        self.entry_user.pack(side=tk.LEFT, padx=(0, 15))
        ttk.Label(f_login, text="Contraseña:").pack(side=tk.LEFT, padx=(0, 5))
        self.entry_pass = ttk.Entry(f_login, width=15, show="*")
        self.entry_pass.pack(side=tk.LEFT, padx=(0, 10))
        self.btn_connect = ttk.Button(f_login, text="Conectar y entrar", command=self.do_connect)
        self.btn_connect.pack(side=tk.LEFT)
        self.lbl_status = ttk.Label(f_login, text="Desconectado")
        self.lbl_status.pack(side=tk.LEFT, padx=20)

        # Tabs
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # Sensores activos
        self.sensors_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.sensors_frame, text="Sensores")
        self.sensors_text = scrolledtext.ScrolledText(self.sensors_frame, height=8, state=tk.DISABLED)
        self.sensors_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        ttk.Button(self.sensors_frame, text="Actualizar lista", command=self.query_sensors).pack(pady=5)

        # Mediciones en tiempo real
        self.measure_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.measure_frame, text="Mediciones")
        self.measure_text = scrolledtext.ScrolledText(self.measure_frame, height=10, state=tk.DISABLED)
        self.measure_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Alertas
        self.alert_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.alert_frame, text="Alertas")
        self.alert_text = scrolledtext.ScrolledText(self.alert_frame, height=10, state=tk.DISABLED)
        self.alert_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.alert_text.tag_config("alert", foreground="red")

    def send_cmd(self, cmd):
        if not self.sock:
            return None
        try:
            self.sock.sendall((cmd + "\r\n").encode())
            return recv_line(self.sock)
        except (socket.timeout, socket.error, OSError):
            return None

    def do_connect(self):
        user = self.entry_user.get().strip()
        password = self.entry_pass.get()
        if not user:
            messagebox.showwarning("Aviso", "Ingrese usuario")
            return
        try:
            addrinfo = socket.getaddrinfo(self.host, self.port, socket.AF_UNSPEC, socket.SOCK_STREAM)
            if not addrinfo:
                messagebox.showerror("Error", "No se pudo resolver el host")
                return
            family, socktype, proto, canonname, sockaddr = addrinfo[0]
            self.sock = socket.socket(family, socktype, proto)
            self.sock.settimeout(5.0)
            self.sock.connect(sockaddr)
        except (socket.gaierror, OSError) as e:
            messagebox.showerror("Error", f"Conexión fallida: {e}")
            return
        resp = self.send_cmd(f"LOGIN|{user}|{password}")
        if not resp or "OK|LOGIN" not in resp:
            self.sock.close()
            self.sock = None
            messagebox.showerror("Error", resp or "Login fallido")
            return
        self.lbl_status.config(text=f"Conectado como {user}")
        self.btn_connect.config(state=tk.DISABLED)
        self.running = True
        self.recv_thread = threading.Thread(target=self.recv_loop, daemon=True)
        self.recv_thread.start()
        self.query_sensors()

    def recv_loop(self):
        while self.running and self.sock:
            try:
                line = recv_line(self.sock)
                if not line:
                    break
                if line.startswith("ALERT|"):
                    self.root.after(0, lambda l=line: self.append_alert(l))
                elif line.startswith("MEASUREMENT|"):
                    self.root.after(0, lambda l=line: self.append_measurement(l))
            except (socket.timeout, socket.error, OSError):
                continue
        self.root.after(0, self.on_disconnect)

    def append_alert(self, line):
        self.alert_text.config(state=tk.NORMAL)
        self.alert_text.insert(tk.END, line + "\n", "alert")
        self.alert_text.see(tk.END)
        self.alert_text.config(state=tk.DISABLED)

    def append_measurement(self, line):
        self.measure_text.config(state=tk.NORMAL)
        self.measure_text.insert(tk.END, line + "\n")
        self.measure_text.see(tk.END)
        self.measure_text.config(state=tk.DISABLED)

    def query_sensors(self):
        if not self.sock:
            return
        resp = self.send_cmd("QUERY_SENSORS")
        self.sensors_text.config(state=tk.NORMAL)
        self.sensors_text.delete(1.0, tk.END)
        if resp and resp.startswith("SENSOR_LIST|"):
            part = resp[11:]
            for block in part.split(";"):
                if block:
                    self.sensors_text.insert(tk.END, block.replace(",", " | ") + "\n")
        else:
            self.sensors_text.insert(tk.END, resp or "Sin respuesta")
        self.sensors_text.config(state=tk.DISABLED)

    def on_disconnect(self):
        self.running = False
        if self.sock:
            try:
                self.sock.close()
            except OSError:
                pass
            self.sock = None
        self.lbl_status.config(text="Desconectado")
        self.btn_connect.config(state=tk.NORMAL)

    def on_closing(self):
        self.on_disconnect()
        self.root.destroy()

    def run(self):
        self.root.mainloop()


def main():
    parser = argparse.ArgumentParser(description="Cliente operador con GUI")
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=8888)
    args = parser.parse_args()
    app = OperatorApp(args.host, args.port)
    app.run()


if __name__ == "__main__":
    main()
