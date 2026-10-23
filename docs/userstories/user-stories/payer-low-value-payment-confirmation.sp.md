# W2: Pago al comercio por QR, confirmación e historial

Como cliente de la billetera,
quiero pagar a un comercio escaneando su QR, confirmar el resultado y consultar el movimiento en mi historial,
para enviar y verificar pagos de forma segura; y como comercio, quiero recibir el pago y consultarlo en mi historial.

## Criterios de aceptación

1. El comercio autenticado genera el QR de uno de sus documentos de deuda. El cliente autenticado identifica al comercio y su documento escaneando ese QR, que contiene `comercio_id`, `documento_deuda_id` y un hash. El servidor valida los tres contra `documentos_deuda` y obtiene la billetera `ACTIVE` del comercio; si no corresponden a un destinatario válido, rechaza la operación. El QR sirve para identificar al destinatario, no para autorizar el pago. Es el único tipo de QR del MVP; su contrato está en [Pagos QR de documentos de deuda](./merchant-qr-payment-status-visibility.sp.md).
2. El monto en soles (PEN) es el del documento de deuda, se lee del servidor y el cliente no puede editarlo. Antes de crear la intención, se muestran el comercio, el documento y el monto para que el cliente los confirme explícitamente.
3. Solo se aceptan pagos en soles (PEN). El servidor rechaza montos no positivos, pagos a la propia billetera, destinatarios no registrados o no `ACTIVE`, solicitudes en otras monedas, documentos que no estén `PENDIENTE`, montos que superan el límite por operación del titular definido en W1 y pagos que exceden el saldo disponible.
4. El pago requiere una sesión de cliente autenticada y vigente, con la autenticación definida en [W1](./user-onboarding-mvp-completion.sp.md) (300 segundos sin renovación). Si la sesión vence antes de confirmar, el cliente debe ingresar de nuevo. Solo clientes con cuenta `ACTIVE` pueden pagar.
5. Al seleccionar el documento, se crea una intención en `transacciones` con identificador único, referencia, clave de idempotencia, estado `PENDIENTE_CONFIRMACION`, billetera origen, billetera destino, documento, monto en PEN y fecha de expiración.
6. Al confirmar, el servidor verifica que la intención siga vigente y que sus datos coincidan exactamente con lo mostrado al cliente. La intención solo puede confirmarse una vez; antes de enviarla, el servidor vuelve a validar la sesión, el límite, el saldo disponible y la deuda, y la reserva (`EN_PROCESO`). Entonces el pago pasa a `PENDIENTE`. Una intención vencida pasa a `EXPIRADA`.
7. La intención confirmada se envía al proveedor de pagos de prueba (mock). El MVP no realiza transferencias con un proveedor externo real.
8. El mock devuelve `APROBADA`, `FALLIDA` o `PENDIENTE`. La billetera muestra el resultado definitivo persistido y no presenta un pago como exitoso antes de recibirlo y guardarlo.
9. Si el pago queda `APROBADA`, se debita el saldo del cliente, se acredita el del comercio y la deuda pasa a `PAGADA`, todo de forma atómica. Si queda `FALLIDA` o `EXPIRADA`, ningún saldo cambia y la deuda sigue o vuelve a `PENDIENTE`.
10. Una confirmación repetida o reintento de la misma intención devuelve el resultado existente, deja un registro `DUPLICADO` en el log y no duplica la transacción ni el movimiento de saldo.
11. Cuando el pago es `APROBADA`, el cliente puede consultar un comprobante con referencia, comercio, documento, monto en PEN, fecha y resultado.
12. El historial muestra, para el cliente, los pagos enviados y, para el comercio, los pagos recibidos, con la contraparte, monto en PEN, fecha, estado y referencia. Cada rol solo ve sus propios movimientos.
13. La información se almacena en las cuatro tablas definidas en [Pagos QR de documentos de deuda](./merchant-qr-payment-status-visibility.sp.md): `cuentas_individuales`, `documentos_deuda`, `transacciones` y `log_transacciones`. El log registra creación y cambios de estado con fecha, hora y identificadores de transacción y correlación; no almacena credenciales ni datos de autenticación sensibles.
14. La creación de la intención y cada cambio de estado se registran en la transacción y en el log. El resultado `APROBADA` y los cambios de saldo y de deuda se confirman de forma atómica para evitar saldos o historiales parciales. Todas las pantallas se rotulan "Modo prueba" y funcionan en 360 y 1280 píxeles de ancho.

## Contexto

- Épica: [MVP de wallet en Perú](../epic/peru-wallet-mvp.sp.md).
- El flujo cubre pagos de clientes a comercios registrados mediante el QR de un documento de deuda, usando un proveedor de pruebas (mock) para el MVP. Los roles que ingresan son `CLIENTE` (DNI) y `COMERCIO` (RUC); no hay pagos entre personas.
- La billetera opera exclusivamente en soles peruanos (PEN); no se admiten ni convierten otras monedas.
- Los estados de pago los procesa el mock y deben quedar reflejados en la billetera y en el historial.

## Preguntas abiertas

- ¿Cuál será el monto máximo por operación para el MVP, dentro del máximo de PEN 1,000.00 propuesto en W1?
- ¿Cuánto tiempo permanece vigente una intención de pago sin confirmar?
