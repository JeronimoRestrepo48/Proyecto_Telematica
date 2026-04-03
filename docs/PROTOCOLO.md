# Especificación del Protocolo de Aplicación - Sistema de Monitoreo IoT

## 1. Generalidades

- **Capa:** Aplicación (capa 7).
- **Transporte:** TCP (SOCK_STREAM). Conexión fiable y ordenada para mediciones, registro y alertas.
- **Formato:** Texto, codificación UTF-8. Mensajes delimitados por secuencia de fin de línea `\r\n` (CRLF).
- **Estructura de mensaje:** `COMANDO [campo1|campo2|...]` — campos separados por `|`, sin espacios alrededor del separador en los datos; espacios permitidos al inicio/final de campos si se documentan.

## 2. Comandos y mensajes

### 2.1 Desde sensor hacia servidor

#### REGISTER
Registro de un sensor en el servidor. Debe enviarse tras conectar, antes de MEASUREMENT.

- **Formato:** `REGISTER|tipo|id|ubicacion`
- **Campos:**
  - `tipo`: temperatura|humedad|presion|vibracion|consumo
  - `id`: identificador único del sensor (alfanumérico)
  - `ubicacion`: descripción corta (ej: "Sala A1")
- **Ejemplo:** `REGISTER|temperatura|sensor01|Sala A1`

#### MEASUREMENT
Envío de una medición.

- **Formato:** `MEASUREMENT|id|tipo|valor|timestamp`
- **Campos:**
  - `id`: mismo id del REGISTER
  - `tipo`: mismo tipo del REGISTER
  - `valor`: número (entero o decimal, punto como separador)
  - `timestamp`: entero Unix (segundos desde 1970-01-01 UTC)
- **Ejemplo:** `MEASUREMENT|sensor01|temperatura|35.2|1709123456`

### 2.2 Desde operador hacia servidor

#### LOGIN
Autenticación del operador. El servidor validará con el servicio externo de identidad.

- **Formato:** `LOGIN|usuario|password`
- **Ejemplo:** `LOGIN|operador1|secret123`

#### QUERY_STATUS
Solicitud de estado general del sistema.

- **Formato:** `QUERY_STATUS`

#### QUERY_SENSORS
Solicitud de lista de sensores activos.

- **Formato:** `QUERY_SENSORS`

### 2.3 Desde servidor hacia clientes

#### OK
Confirmación de operación correcta.

- **Formato:** `OK|codigo|[datos_opcionales]`
- **Ejemplos:**
  - `OK|REGISTER|sensor01`
  - `OK|LOGIN|operador1`
  - `OK|QUERY_STATUS|sensores_activos=5|alertas_hoy=2`

#### ERROR
Operación fallida o rechazada.

- **Formato:** `ERROR|codigo|mensaje`
- **Códigos sugeridos:** AUTH_FAILED, INVALID_MSG, SENSOR_DUPLICATE, NOT_AUTHENTICATED
- **Ejemplo:** `ERROR|AUTH_FAILED|Credenciales invalidas`

#### ALERT
Notificación de evento anómalo (enviada a operadores conectados).

- **Formato:** `ALERT|id_sensor|tipo|valor|umbral|mensaje`
- **Ejemplo:** `ALERT|sensor01|temperatura|45.0|40.0|Temperatura sobre umbral`

#### SENSOR_LIST
Respuesta a QUERY_SENSORS: lista de sensores activos.

- **Formato:** `SENSOR_LIST|id1,tipo1,ubic1;id2,tipo2,ubic2;...`
- **Ejemplo:** `SENSOR_LIST|sensor01,temperatura,Sala A1;sensor02,humedad,Sala B2`

#### MEASUREMENT (reenvío)
El servidor puede reenviar a operadores una medición recibida (para tiempo real).

- **Formato:** igual que el MEASUREMENT del sensor: `MEASUREMENT|id|tipo|valor|timestamp`

## 3. Flujos

### 3.1 Sensor

1. Conexión TCP al servidor (host y puerto por resolución de nombres).
2. Enviar `REGISTER|tipo|id|ubicacion`.
3. Esperar `OK|REGISTER|id` o `ERROR|...`.
4. En bucle: enviar `MEASUREMENT|id|tipo|valor|timestamp` periódicamente (ej. cada 5 s).
5. Ante cierre de conexión o ERROR: intentar reconexión según política del cliente.

### 3.2 Operador

1. Conexión TCP al servidor.
2. Enviar `LOGIN|usuario|password`.
3. Esperar `OK|LOGIN|usuario` o `ERROR|AUTH_FAILED|...`.
4. Tras login correcto: puede enviar `QUERY_STATUS`, `QUERY_SENSORS` y recibir `ALERT`, `MEASUREMENT`, `SENSOR_LIST`, `OK|QUERY_STATUS|...`.

### 3.3 Servidor

- Mantiene lista de sensores registrados (id, tipo, ubicación, última medición, timestamp).
- Mantiene lista de operadores autenticados (sockets).
- Para cada MEASUREMENT recibida: actualiza estado; si supera umbral del tipo, genera ALERT y la envía a todos los operadores conectados; opcionalmente reenvía MEASUREMENT a operadores.
- Umbrales por tipo (ejemplo): temperatura max 40, humedad max 90, presion min 1000 max 1020, vibracion max 10, consumo max 5000.

## 4. Manejo de errores

- Mensaje mal formado o comando desconocido: responder `ERROR|INVALID_MSG|descripcion`.
- Sensor ya registrado con mismo id: `ERROR|SENSOR_DUPLICATE|id`.
- Operador no autenticado envía QUERY_*: `ERROR|NOT_AUTHENTICATED|Login requerido`.
- En cualquier error de red (desconexión, timeout): cerrar socket y registrar en log; no finalizar el proceso del servidor.

## 5. Delimitadores y escape

- Fin de mensaje: `\r\n` (CRLF).
- Separador de campos: `|`.
- En SENSOR_LIST, separador entre sensores: `;`; entre campos de un sensor: `,`.
- No se definen caracteres de escape; evitar `|`, `;`, `,` y `\r\n` en valores de ubicación o mensaje. Si se necesitan, en una futura versión se puede definir `\` como escape.
