# Proyecto integrador final — despliegue con Docker

Este documento describe la arquitectura y el despliegue del **proyecto integrador** (Internet: Arquitectura y Protocolos): balanceador **NGINX** con **HTTPS** y **round robin**, dos servidores de aplicación (**inglés** y **español**), **PostgreSQL** y servicio de **estadísticas por correo**.

## Arquitectura

1. **Cliente (navegador)** accede por `https://<su-dominio>/` (registro A en DNS hacia la IP pública de AWS).
2. **Contenedor `nginx`**: termina TLS, actúa como **proxy inverso** y distribuye peticiones `GET/POST /` en **round robin** entre `web_en` (inglés) y `web_es` (español). Idioma fijo por servidor; no hay selector de idioma.
3. **`web_en` y `web_es`**: aplicación **Python (Flask)** + Gunicorn; registran nombre, comuna (1–10), fecha de ingreso y carrera (Medicina, Ingeniería, Abogacía, Licenciatura) en la misma base de datos.
4. **`db`**: **PostgreSQL** en Docker con volumen persistente.
5. **`stats`**: aplicación Python que, **a solicitud del administrador**, consulta la base, genera **gráficas (PNG)** con Matplotlib y envía un correo a `ialondonoo@eafit.edu.co` (configurable) con resumen en HTML y adjuntos.

Ruta de administración (no balanceada entre webs): `https://<su-dominio>/admin/` (formulario con token) o `POST /admin/enviar-estadisticas` con cabecera `X-Admin-Token`.

## Requisitos

- Docker y Docker Compose v2.
- OpenSSL (solo para generar certificado de prueba local).

## Puesta en marcha local

```bash
cd integrador-final
chmod +x nginx/generate-certs.sh
./nginx/generate-certs.sh localhost   # crea nginx/certs/server.crt y .key
```

Defina variables (puede copiar a un archivo `.env` en esta carpeta):

- `ADMIN_TOKEN`: token secreto para enviar estadísticas.
- Para correo real: `SMTP_HOST`, `SMTP_PORT` (587 típico), `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`, `STATS_EMAIL_TO` (por defecto ya apunta al correo del enunciado).

```bash
export ADMIN_TOKEN=un-token-largo-y-secreto
docker compose up --build -d
```

Abrir en el navegador: `https://localhost/` (aceptar advertencia del certificado **autofirmado**). Refrescar varias veces: verá alternancia entre formulario en **inglés** y en **español** (round robin).

## Prueba del correo de estadísticas

Sin SMTP configurado, el envío responderá error indicando que falta `SMTP_HOST`. En AWS suele usarse **Amazon SES** (verificar dominio/correo, credenciales SMTP).

Ejemplo con cabecera:

```bash
curl -k -X POST "https://localhost/admin/enviar-estadisticas" \
  -H "X-Admin-Token: un-token-largo-y-secreto"
```

O use el formulario en `https://localhost/admin/`.

## Despliegue en Amazon Web Services (Educate)

1. **EC2** (por ejemplo Amazon Linux 2023 o Ubuntu): instalar Docker y Docker Compose plugin.
2. Clonar el repositorio y generar certificados **reales** (recomendado en producción) con **Let’s Encrypt** (por ejemplo `certbot` en el host montando los `.pem` en `nginx/certs/`) o usar un ACM + ALB si la arquitectura del curso permite sustituir NGINX por ALB (el enunciado pide NGINX como balanceador; lo habitual es NGINX en EC2 con certificados locales o certbot).
3. **Grupo de seguridad**: abrir **443** (y **80** si desea solo redirección a HTTPS), SSH 22 solo desde su IP.
4. **DNS**: en el proveedor gratuito o en **Route 53**, registro **A** al **Elastic IP** de la instancia.
5. Copiar `.env` con `POSTGRES_PASSWORD`, `ADMIN_TOKEN` y credenciales SMTP.
6. `docker compose up --build -d` en el directorio `integrador-final`.

## Entregables documentales (recordatorio)

- Procedimiento de configuración (este archivo complementa el despliegue general en `docs/DESPLIEGUE_AWS.md` del otro módulo del curso si aplica).
- Descripción de NGINX, aplicaciones web y servicio de estadísticas.
- Evidencia de **certificado de sitio** (captura o cadena del certificado en producción).

## Seguridad

- Cambie `ADMIN_TOKEN` y `POSTGRES_PASSWORD` en producción.
- No suba `.env` ni claves privadas al repositorio.
