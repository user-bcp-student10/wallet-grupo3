# Manejo de fallas de pago y reversos

Como especialista de soporte al cliente (rol interno sin ingreso a la billetera),
quiero que los pagos fallidos y expirados sigan rutas de atención explícitas,
para que los usuarios reciban guía consistente y soporte pueda resolver incidentes de forma predecible.

## Criterios de aceptación

1. Los pagos `FALLIDA` y `EXPIRADA` de ambas modalidades (`QR_COMERCIO` y `CONTACTO`) se clasifican y almacenan con un `codigo_motivo` legible por máquina en `log_transacciones`.
2. La vista de soporte muestra la modalidad y el tipo de pago, y si el pago es elegible para reintento (con nueva clave) o investigación. En `QR_COMERCIO`, un pago `FALLIDA` o `EXPIRADA` libera la deuda a `PENDIENTE`; en `CONTACTO` no hay documento que liberar.
3. La ruta de ayuda al usuario diferencia una falla técnica (`FALLIDA` o `EXPIRADA`, sin movimiento de saldo) de un pago `APROBADA`, que ya movió saldos y no se revierte en el MVP.
4. Las consultas y acciones de soporte se registran en `log_transacciones` con referencia de transacción y estado de resolución.

## Contexto

- Épica: [MVP de wallet en Perú](../epic/peru-wallet-mvp.sp.md).
- Aplica a [W2](./payer-low-value-payment-confirmation.sp.md) y a [Pagos QR de documentos de deuda](./merchant-qr-payment-status-visibility.sp.md), que comparten estados y tablas y cubren pago QR comercio y pago a contacto (a persona o a comercio).
- Extornos, devoluciones y disputas quedan fuera del MVP.

## Supuestos

- Los niveles de escalamiento de soporte y los SLA quedan por definir.

## Preguntas abiertas

- ¿Qué códigos de motivo (`codigo_motivo`) se definen para los pagos `FALLIDA` y `EXPIRADA`?
