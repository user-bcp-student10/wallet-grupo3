# Conciliación operativa de transacciones

Como analista de operaciones (rol interno sin ingreso a la billetera),
quiero una conciliación diaria entre transacciones, eventos del mock y movimientos de saldo,
para detectar descalces temprano y mantener la integridad financiera del MVP.

## Criterios de aceptación

1. La salida diaria de conciliación compara `transacciones` y `log_transacciones` contra los eventos del mock (`evento_mock_id`) y verifica que los saldos de `cuentas_individuales` coincidan con los pagos `APROBADA`.
2. Cada descalce se marca con referencia de transacción, tipo de descalce y estado actual de investigación.
3. Los reportes de conciliación se pueden filtrar por fecha, estado de pago, modalidad (`QR_COMERCIO` o `CONTACTO`) y tipo (`PERSONA_A_PERSONA` o `PERSONA_A_COMERCIO`).
4. Se genera un resumen diario con totales de registros conciliados, no conciliados y resueltos, y de reintentos `DUPLICADO`, desglosado por modalidad.

## Contexto

- Épica: [MVP de wallet en Perú](../epic/peru-wallet-mvp.sp.md).
- Concilia los pagos de [W2](./payer-low-value-payment-confirmation.sp.md) y de [Pagos QR de documentos de deuda](./merchant-qr-payment-status-visibility.sp.md) (pago QR comercio y pago a contacto), que comparten las cuatro tablas del MVP. En pagos a persona el crédito va a la billetera de un cliente; en pagos a comercio, a la del comercio.
- Hay un único mock; no se concilia contra un banco ni un libro de movimientos.

## Supuestos

- Las herramientas de conciliación se definirán durante la implementación.

## Preguntas abiertas

- ¿Cuál es la tasa máxima diaria de descalce aceptable para preparación del lanzamiento del MVP?
