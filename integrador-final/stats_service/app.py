"""
Servicio de estadísticas: a solicitud del administrador genera gráficas y envía correo.
"""
from __future__ import annotations

import io
import os
import smtplib
from email.message import EmailMessage

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import psycopg2
from flask import Flask, Response, request
from psycopg2.extras import RealDictCursor

app = Flask(__name__)


def get_conn():
    return psycopg2.connect(os.environ["DATABASE_URL"], cursor_factory=RealDictCursor)


def fetch_totals_by_comuna(cur) -> list[tuple[int, int]]:
    cur.execute(
        """
        SELECT comuna, COUNT(*) AS n
        FROM registros
        GROUP BY comuna
        ORDER BY comuna
        """
    )
    rows = cur.fetchall()
    data = {r["comuna"]: int(r["n"]) for r in rows}
    return [(c, data.get(c, 0)) for c in range(1, 11)]


def fetch_by_comuna_carrera(cur) -> list[dict]:
    cur.execute(
        """
        SELECT comuna, carrera, COUNT(*) AS n
        FROM registros
        GROUP BY comuna, carrera
        ORDER BY comuna, carrera
        """
    )
    return [dict(r) for r in cur.fetchall()]


def figure_comuna_bars(pairs: list[tuple[int, int]]) -> bytes:
    comunas = [str(p[0]) for p in pairs]
    counts = [p[1] for p in pairs]
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.bar(comunas, counts, color="#2563eb")
    ax.set_xlabel("Comuna")
    ax.set_ylabel("Registros")
    ax.set_title("Usuarios por comuna")
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=120)
    plt.close(fig)
    buf.seek(0)
    return buf.read()


def figure_comuna_carrera_heatmap(rows: list[dict]) -> bytes:
    carreras = ["Medicina", "Ingeniería", "Abogacía", "Licenciatura"]
    matrix = [[0] * len(carreras) for _ in range(10)]
    carrera_idx = {c: i for i, c in enumerate(carreras)}
    for r in rows:
        c = int(r["comuna"]) - 1
        if 0 <= c < 10 and r["carrera"] in carrera_idx:
            matrix[c][carrera_idx[r["carrera"]]] = int(r["n"])
    fig, ax = plt.subplots(figsize=(8, 5))
    im = ax.imshow(matrix, aspect="auto", cmap="Blues")
    ax.set_xticks(range(len(carreras)), labels=carreras, rotation=25, ha="right")
    ax.set_yticks(range(10), labels=[f"Comuna {i+1}" for i in range(10)])
    ax.set_title("Interesados por comuna y carrera")
    fig.colorbar(im, ax=ax, label="Cantidad")
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=120)
    plt.close(fig)
    buf.seek(0)
    return buf.read()


def send_email_with_charts(
    to_addr: str,
    from_addr: str,
    png_comuna: bytes,
    png_detalle: bytes,
    summary_html: str,
) -> None:
    host = os.environ.get("SMTP_HOST", "").strip()
    if not host:
        raise RuntimeError(
            "SMTP_HOST no está configurado. Defina SMTP_HOST, SMTP_USER, SMTP_PASSWORD en el entorno."
        )
    port = int(os.environ.get("SMTP_PORT", "587"))
    user = os.environ.get("SMTP_USER", "").strip()
    password = os.environ.get("SMTP_PASSWORD", "").strip()
    use_tls = os.environ.get("SMTP_USE_TLS", "1") not in ("0", "false", "False")

    msg = EmailMessage()
    msg["Subject"] = "Estadísticas acumuladas — registro de interés"
    msg["From"] = from_addr
    msg["To"] = to_addr
    msg.set_content(
        "Resumen de estadísticas en HTML y dos gráficas en archivos PNG adjuntos."
    )
    html = f"""
    <html>
      <body>
        <p>Resumen numérico:</p>
        {summary_html}
        <p style="margin-top:1.25rem">Las gráficas se adjuntan como <strong>PNG</strong>
        (<code>usuarios_por_comuna.png</code> y <code>por_comuna_y_carrera.png</code>).</p>
      </body>
    </html>
    """
    msg.add_alternative(html, subtype="html")
    msg.add_attachment(
        png_comuna, maintype="image", subtype="png", filename="usuarios_por_comuna.png"
    )
    msg.add_attachment(
        png_detalle, maintype="image", subtype="png", filename="por_comuna_y_carrera.png"
    )

    with smtplib.SMTP(host, port, timeout=30) as smtp:
        if use_tls:
            smtp.starttls()
        if user:
            smtp.login(user, password)
        smtp.send_message(msg)


@app.route("/admin/", methods=["GET"])
def admin_home():
    return Response(
        """<!DOCTYPE html>
<html lang="es"><head><meta charset="utf-8"/><title>Estadísticas</title></head>
<body>
  <h1>Envío de estadísticas por correo</h1>
  <p>Use el botón solo si es administrador. El correo se envía a la dirección configurada en el servidor
  (por defecto <code>ialondonoo@eafit.edu.co</code>).</p>
  <form method="post" action="/admin/enviar-estadisticas">
    <label>Token de administrador<br/>
      <input name="token" type="password" required style="min-width:280px"/></label><br/><br/>
    <button type="submit">Generar gráficas y enviar correo</button>
  </form>
  <p><small>También puede usar <code>curl -k -X POST https://su-dominio/admin/enviar-estadisticas</code>
  con cabecera <code>X-Admin-Token</code>.</small></p>
</body></html>""",
        mimetype="text/html; charset=utf-8",
    )


@app.route("/admin/enviar-estadisticas", methods=["POST"])
def enviar_estadisticas():
    token = request.headers.get("X-Admin-Token") or request.form.get("token") or ""
    expected = os.environ.get("ADMIN_TOKEN", "")
    if not expected or token != expected:
        return {"error": "No autorizado"}, 401

    with get_conn() as conn:
        with conn.cursor() as cur:
            pairs = fetch_totals_by_comuna(cur)
            detalle = fetch_by_comuna_carrera(cur)
            cur.execute("SELECT COUNT(*) AS total FROM registros")
            total = int(cur.fetchone()["total"])

    png1 = figure_comuna_bars(pairs)
    png2 = figure_comuna_carrera_heatmap(detalle)

    rows_html = "".join(
        f"<tr><td>Comuna {c}</td><td>{n}</td></tr>" for c, n in pairs
    )
    det_rows = "".join(
        f"<tr><td>Comuna {r['comuna']}</td><td>{r['carrera']}</td><td>{r['n']}</td></tr>"
        for r in detalle
    )
    summary_html = (
        f"<p>Total de registros: <strong>{total}</strong></p>"
        "<h3>Por comuna</h3>"
        "<table border='1' cellpadding='4' cellspacing='0'>"
        "<tr><th>Comuna</th><th>Cantidad</th></tr>"
        f"{rows_html}</table>"
        "<h3>Por comuna y carrera</h3>"
        "<table border='1' cellpadding='4' cellspacing='0'>"
        "<tr><th>Comuna</th><th>Carrera</th><th>Cantidad</th></tr>"
        f"{det_rows}</table>"
    )

    to_addr = os.environ.get("STATS_EMAIL_TO", "ialondonoo@eafit.edu.co")
    from_addr = os.environ.get("SMTP_FROM", "noreply@localhost")

    try:
        send_email_with_charts(to_addr, from_addr, png1, png2, summary_html)
    except Exception as exc:  # noqa: BLE001
        app.logger.exception("Fallo al enviar correo")
        return {"ok": False, "error": str(exc)}, 500

    return {"ok": True, "message": f"Correo enviado a {to_addr}"}, 200


@app.route("/health")
def health():
    return {"status": "ok", "service": "stats"}, 200
