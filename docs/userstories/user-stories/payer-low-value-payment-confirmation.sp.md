# W2: Pago a contacto, confirmación e historial

Como usuario de la billetera,
quiero pagar a una persona o comercio, confirmar el resultado y consultar el movimiento en mi historial,
para enviar y verificar pagos de forma segura.

## Criterios de aceptación

1. El pagador puede identificar y seleccionar a una persona o comercio registrado escaneando un QR que contiene un hash único asociado a su cuenta. El servidor resuelve el hash a una cuenta activa; si no corresponde a un destinatario válido, rechaza la operación. El QR sirve para identificar al destinatario, no para autorizar el pago.
2. El pagador ingresa un monto en soles (PEN). Antes de crear la intención, se muestran el nombre o identificador del destinatario y el monto para que el pagador los confirme explícitamente.
3. Solo se aceptan pagos en soles (PEN). El servidor rechaza montos no positivos, pagos a la propia cuenta, destinatarios no registrados, solicitudes en otras monedas y pagos que exceden el saldo disponible.
4. El pago requiere una sesión autenticada y vigente. Si la evaluación de riesgo requiere autenticación reforzada, el pagador debe completarla antes de confirmar.
5. Al seleccionar destinatario y monto, se crea una intención con identificador único, estado `PENDING_CONFIRMATION`, pagador, destinatario, monto en PEN y fecha de expiración.
6. Al confirmar, el servidor verifica que la intención siga vigente y que sus datos coincidan exactamente con lo mostrado al pagador. La intención solo puede confirmarse una vez; antes de enviarla, el servidor vuelve a validar la sesión, los límites y el saldo disponible.
7. La intención confirmada se envía al proveedor de pagos simulado. El MVP no realiza transferencias con un proveedor externo real.
8. El proveedor simulado devuelve un resultado de pago exitoso, fallido o expirado. La billetera muestra el resultado definitivo y no presenta un pago como exitoso antes de recibirlo.
9. Si el pago es exitoso, se debita el saldo del pagador y se acredita el del destinatario de forma atómica. Si falla o expira, ninguno de los saldos cambia.
10. Una confirmación repetida o reintento de la misma intención devuelve el resultado existente y no duplica la transacción ni el movimiento de saldo.
11. Cuando el pago es exitoso, el pagador puede consultar un comprobante con referencia, destinatario, monto en PEN, fecha y resultado.
12. El historial muestra los pagos enviados por el usuario y los pagos recibidos, con destinatario u origen, monto en PEN, fecha, estado y referencia.
13. La información se almacena en estas tres tablas:
    - `cuentas_individuales`: cuenta de cada usuario y su saldo disponible en soles (PEN).
    - `transacciones`: intención y resultado del pago, con identificadores del pagador y destinatario, monto en PEN, estado y referencia.
    - `log_transacciones`: registro de creación y cambios de estado, con fecha y hora e identificadores de transacción y correlación; no almacena credenciales ni datos de autenticación sensibles.
14. La creación de la intención y cada cambio de estado se registran en la transacción y en el log. El resultado exitoso y los cambios de saldo se confirman de forma atómica para evitar saldos o historiales parciales.

## Contexto

- Épica: [MVP de wallet en Perú](../epic/peru-wallet-mvp.sp.md).
- El flujo cubre pagos entre usuarios y pagos a comercios registrados, usando un proveedor simulado para el MVP.
- La billetera opera exclusivamente en soles peruanos (PEN); no se admiten ni convierten otras monedas.
- Los estados de pago son procesados por el proveedor simulado y deben quedar reflejados en la billetera y en el historial.

## Preguntas abiertas

- ¿Cuál será el monto máximo que define un pago de bajo monto para el MVP?
- ¿Cuánto tiempo permanece vigente una intención de pago sin confirmar?
- ¿Qué mensaje debe mostrar la billetera cuando el QR permanente identifica una cuenta bloqueada o inactiva?
