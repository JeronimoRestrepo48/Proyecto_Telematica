import os
from datetime import date

import psycopg2
from flask import Flask, flash, redirect, render_template, request, url_for
from psycopg2.extras import RealDictCursor
from werkzeug.middleware.proxy_fix import ProxyFix

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-es")
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)


def get_conn():
    return psycopg2.connect(os.environ["DATABASE_URL"], cursor_factory=RealDictCursor)


CARRERAS = [
    ("Medicina", "Medicina"),
    ("Ingeniería", "Ingeniería"),
    ("Abogacía", "Abogacía"),
    ("Licenciatura", "Licenciatura"),
]


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        nombre = (request.form.get("nombre") or "").strip()
        comuna = request.form.get("comuna")
        fecha = request.form.get("fecha_ingreso")
        carrera_val = request.form.get("carrera")
        if not nombre or not comuna or not fecha or not carrera_val:
            flash("Todos los campos son obligatorios.", "error")
            return redirect(url_for("index"))
        try:
            comuna_i = int(comuna)
            if comuna_i < 1 or comuna_i > 10:
                raise ValueError()
        except ValueError:
            flash("La comuna debe estar entre 1 y 10.", "error")
            return redirect(url_for("index"))
        allowed = {c[0] for c in CARRERAS}
        if carrera_val not in allowed:
            flash("Carrera no válida.", "error")
            return redirect(url_for("index"))
        try:
            fecha_d = date.fromisoformat(fecha)
        except ValueError:
            flash("Fecha no válida.", "error")
            return redirect(url_for("index"))
        try:
            with get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO registros (nombre, comuna, fecha_ingreso, carrera)
                        VALUES (%s, %s, %s, %s)
                        """,
                        (nombre, comuna_i, fecha_d, carrera_val),
                    )
                conn.commit()
        except Exception as exc:  # noqa: BLE001
            app.logger.exception("DB error")
            flash(f"No se pudo guardar: {exc}", "error")
            return redirect(url_for("index"))
        flash("Registro guardado correctamente.", "ok")
        return redirect(url_for("index"))
    return render_template("index.html", carreras=CARRERAS, today=date.today().isoformat())


@app.route("/health")
def health():
    return {"status": "ok", "locale": "es"}, 200
