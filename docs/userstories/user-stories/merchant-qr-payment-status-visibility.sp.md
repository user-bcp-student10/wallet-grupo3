# Procesamiento y estado confiable de pagos QR simulados

Como billetera digital que procesa pagos QR en un entorno simulado,
quiero ejecutar las transacciones del cliente mediante un mock de pagos y mostrar su estado confiable y actualizado,
para validar el flujo de pago y brindar trazabilidad de cada transacción sin integrar un proveedor de pagos real.

## Criterios de aceptación

1. La billetera permite iniciar una transacción de pago QR y procesarla mediante el mock, sin realizar llamadas a un proveedor de pagos real ni mover dinero real.
2. La billetera muestra cada transacción del cliente con una referencia única, importe, moneda, fecha y estado actual, accesible únicamente a los usuarios autorizados e identificada como una operación simulada.
3. El estado se actualiza a partir de los registros de la billetera y las respuestas o eventos del mock. Una transacción solo se muestra como completada cuando el mock confirma el resultado exitoso.
4. El mock permite reproducir resultados exitosos, fallidos y pendientes de confirmación. Mientras no exista un resultado definitivo, la billetera mantiene el estado pendiente sin presentarlo como éxito o falla definitiva.
5. Los reintentos y las respuestas o eventos duplicados del mock no generan transacciones duplicadas ni aplican más de una vez un mismo cambio de estado.
6. La billetera conserva el historial de cambios de estado de cada pago, con fecha y referencia de la respuesta o evento del mock que sustenta cada cambio.

## Datos SQLite y alcance del MVP

### Tablas y campos principales

Se utilizarán únicamente las siguientes tres tablas. Los identificadores serán de tipo `TEXT`, los importes de tipo `INTEGER` en céntimos y las fechas de tipo `TEXT` en formato ISO 8601 UTC. La única moneda habilitada será `PEN`.

| Tabla | Campos principales | Interacción con esta historia |
|---|---|---|
| `cuentas_individuales` | `id` (PK), `identificador` (único), `nombre_titular`, `moneda`, `saldo_simulado_centimos`, `estado`, `creada_en` | Proporciona las cuentas de prueba de origen y destino y los datos del titular para identificar a los participantes del pago. `estado` admite `ACTIVA` o `INACTIVA`. El saldo simulado es informativo: esta historia no lo valida ni modifica. |
| `transacciones` | `id` (PK), `referencia` (única), `cuenta_origen_id` (FK), `cuenta_destino_id` (FK), `monto_centimos`, `moneda`, `estado_actual`, `clave_idempotencia` (única), `creada_en`, `actualizada_en` | Registra cada intento de pago y entrega los datos que se muestran al cliente. Ambas cuentas referencian `cuentas_individuales.id`. La clave de idempotencia permite recuperar el mismo intento ante un reenvío. |
| `historial_transacciones` | `id` (PK), `transaccion_id` (FK), `estado_anterior`, `estado_nuevo`, `motivo`, `evento_mock_id` (único cuando exista), `registrado_en` | Registra la creación y cada cambio de estado del pago. Referencia `transacciones.id` y conserva el identificador de la confirmación del mock para evitar aplicarla dos veces. |

### Flujo de datos de esta historia

1. Se consultan dos cuentas de prueba precargadas, distintas, activas y en PEN. El importe debe ser un entero positivo en céntimos. No se crean ni editan cuentas desde este flujo.
2. Se crea una transacción en estado `PENDIENTE` y su primer registro de historial, con `estado_anterior` y `evento_mock_id` nulos y motivo `CREACION`. Ambas inserciones se guardan en una misma transacción SQLite, con claves foráneas habilitadas.
3. Si se repite una solicitud con la misma `clave_idempotencia` y los mismos datos de origen, destino, importe y moneda, se devuelve la transacción existente sin crear otra ni reprocesar el pago. Si esos datos cambian, se rechaza la reutilización de la clave.
4. Para las confirmaciones, el mock devuelve `referencia`, `evento_mock_id` y `resultado`. Los escenarios de prueba predefinidos son éxito, falla y pendiente; no se requiere una tabla adicional para configurarlos. Un resultado pendiente o la ausencia de confirmación mantiene `PENDIENTE` sin agregar cambios de estado ficticios.
5. Una confirmación definitiva cambia `PENDIENTE` a `EXITOSA` o `FALLIDA`. La actualización de `transacciones` y la inserción del historial se realizan juntas en una transacción SQLite. El historial registra el identificador del evento y un motivo que identifica el resultado simulado.
6. Una confirmación con referencia desconocida o resultado no admitido se rechaza sin modificar datos. Un evento ya aplicado no genera otra actualización ni otro historial. Los estados `EXITOSA` y `FALLIDA` son terminales y no se sustituyen por confirmaciones posteriores contradictorias.
7. La consulta del cliente obtiene el estado actual desde `transacciones` y la secuencia de cambios desde `historial_transacciones`, ordenada por fecha e identificador. El acceso se limita a las transacciones permitidas por la identidad de prueba de la sesión.

### Límites de esta entrega

- Se incluye la persistencia de pagos simulados, la consulta de su estado e historial y la protección frente a solicitudes o confirmaciones duplicadas.
- Las cuentas y sus asociaciones con las identidades de prueba se precargan. No se implementan registro de usuarios, inicio de sesión nuevo, mantenimiento de cuentas ni pantallas para administrar el mock en esta historia.
- No se incluyen validación de fondos, débitos o abonos de saldos, libro de movimientos, comisiones, conversión de moneda ni conciliación bancaria. Un pago `EXITOSA` confirma únicamente el resultado simulado del mock.
- No se incluyen expiración automática, cancelaciones, extornos, devoluciones ni gestión de reclamos o quejas. Estos flujos requieren un alcance posterior.
- Esta sección define el modelo mínimo propuesto; no implica crear todavía archivos SQLite, migraciones ni código de implementación.

## Contexto

- Épica: [MVP de wallet en Perú](../epic/peru-wallet-mvp.sp.md).
- El alcance de esta historia es ejecutar transacciones de pago QR simuladas y mostrar sus estados. El mock sustituye al proveedor de pagos y es la fuente de confirmaciones del flujo simulado.
- Un estado confiable significa que la información mostrada es consistente con el resultado del mock y los registros de la billetera; no representa una confirmación financiera real.
- No se incluye la administración de cajas del comercio ni sus decisiones de entrega de productos o servicios.
- Los extornos y devoluciones, así como la gestión de reclamos, quejas y disputas, quedan fuera de esta historia y se abordarán en un alcance posterior.

## Supuestos

- El entorno del MVP utiliza un mock controlado con escenarios reproducibles, sin credenciales ni conexión a una empresa proveedora de pagos.
- Los importes son simulados y los saldos de prueba son informativos; esta historia no realiza movimientos de saldo ni débitos o abonos reales.
- El canal del MVP será una aplicación web con diseño responsive para móviles, tabletas y computadoras de escritorio. El flujo de pago, el estado y el historial se adaptarán al tamaño de pantalla sin perder información ni funcionalidad; no se desarrollarán aplicaciones nativas en esta entrega.

## Preguntas abiertas

- ¿Qué cuentas e identidades de prueba se precargarán para validar los tres escenarios del mock?
