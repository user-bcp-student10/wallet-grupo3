# Idempotencia en pagos

como analista de operaciones y confiabilidad (rol interno sin ingreso a la billetera),
quiero que los intentos de pago duplicados se manejen con comportamiento idempotente,
para evitar duplicidad financiera y desvíos en conciliación cuando hay reintentos.

## Criterios de aceptación

1. Cada intento de pago, sea `QR_COMERCIO` o `CONTACTO` (persona a persona o persona a comercio), se crea con una clave de idempotencia única (`transacciones.clave_idempotencia`) por intención, ligada a modalidad, pagador, destinatario, documento (solo `QR_COMERCIO`), monto y moneda.
2. Una solicitud repetida con la misma clave y los mismos datos devuelve el resultado original y no crea una nueva transacción ni mueve saldos; con datos distintos se rechaza. Esto incluye repetir el escaneo del mismo QR o el reenvío del mismo pago a contacto (mismo `hash_pago`).
3. Cada solicitud o evento duplicado se registra en `log_transacciones` con motivo `DUPLICADO` y su identificador de correlación para auditoría.
4. Las salidas de conciliación distinguen el intento original de los reintentos duplicados mediante esos registros `DUPLICADO`, por modalidad de pago.

## Contexto

- Épica: [MVP de wallet en Perú](../epic/peru-wallet-mvp.sp.md).
- Aplica a [W2](./payer-low-value-payment-confirmation.sp.md) y a [Pagos QR de documentos de deuda](./merchant-qr-payment-status-visibility.sp.md), que comparten tablas y estados y cubren las dos modalidades: pago QR comercio y pago a contacto (a persona o a comercio). El contrato del log está en esta última.
- Solo los clientes pagan (W1); comercios y clientes reciben.
- El riesgo de idempotencia está documentado explícitamente con comportamiento de payload duplicado en la evidencia del ecosistema.

## Preguntas abiertas

- ¿Cuál es la ventana de retención de claves de idempotencia para el MVP?
