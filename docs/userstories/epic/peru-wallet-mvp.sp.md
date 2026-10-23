# Épica: MVP de wallet en Perú para pagos cotidianos

## Resumen

Construir durante la hackatón una demostración de wallet en modo prueba, enfocada en Perú y desarrollada con apoyo de IA. Una web adaptable a celular y computadora debe cubrir registro e ingreso (W1), pago a una persona o comercio con confirmación e historial (W2) y pago de documentos de deuda de comercios mediante QR (historia de pagos QR), con estados y mensajes claros, sin dinero ni documentos de personas. Los pagos se envían a un proveedor de pagos de prueba (mock) y se protegen con idempotencia, manejo de fallas y conciliación. Los objetivos de lanzamiento siguientes se conservan como referencias de negocio para una evolución posterior, no como compromisos medibles durante la hackatón.

## Problema y oportunidad

La caída en checkout es alta y el onboarding es lento para personas que hacen transferencias pequeñas frecuentes y pagos con QR. La línea base local de pagos muestra una adopción fuerte de interoperabilidad y un comportamiento claro en flujos basados en alias, lo que abre una oportunidad para lanzar ahora una propuesta de wallet enfocada.

## Objetivos

Como referencia para un futuro lanzamiento en un trimestre:

- Reducir la caída en checkout de 30% a 8%.
- Reducir el tiempo de finalización de onboarding de 8 minutos a 3 minutos.
- Mantener usuarios activos mensuales (MAU) entre 1,000 y 2,000 durante los primeros 3 meses posteriores al lanzamiento.
- Lograr un costo de adquisición de cliente (CAC) de PEN 10 por cada usuario nuevo durante los primeros 3 meses posteriores al lanzamiento.

## Usuarios objetivo

- Usuarios de smartphone (clientes) que pagan con QR montos bajos: necesitan un recorrido rápido y de baja fricción desde el escaneo hasta la confirmación del pago.
- Pequeños comercios que generan el QR y reciben el pago: necesitan aceptación predecible, confirmación confiable y estabilidad operativa diaria.

## Alcance

### Incluye

- [W1: Registro y activación](../user-stories/user-onboarding-mvp-completion.sp.md): registro e ingreso de clientes (DNI) y comercios (RUC) eligiendo el rol, con contraseña o Google conectado mediante cuentas de prueba autorizadas, activación manual por el facilitador, billeteras con saldo de prueba y límite por operación en PEN, y sesión de 300 segundos. Solo cliente y comercio ingresan. La verificación de documentos y la biometría son de prueba, se identifican como tales y no sustituyen el ingreso ni activan cuentas.
- [W2: Pago al comercio por QR, confirmación e historial](../user-stories/payer-low-value-payment-confirmation.sp.md): el cliente paga en PEN a un comercio escaneando su QR, con intención y confirmación explícita, envío al proveedor de prueba, débito y crédito atómicos solo si el pago es `APROBADA`, comprobante e historial (enviados para el cliente, recibidos para el comercio).
- [Pagos QR de documentos de deuda](../user-stories/merchant-qr-payment-status-visibility.sp.md): el comercio genera el único QR del MVP, por documento (comercio, documento y hash); monto fijo leído de la base de datos, reserva de la deuda, pago mediante el mock externo, persistencia atómica del resultado con movimiento de saldos y consulta responsive del estado. Define el contrato de datos compartido.
- [Idempotencia en pagos](../user-stories/payment-idempotency-protection.sp.md): clave de idempotencia por intento, resultado original ante reintentos y registro `DUPLICADO` en `log_transacciones`. Aplica a W2 y a los pagos de deuda.
- [Manejo de fallas de pago](../user-stories/payment-failure-reversal-handling.sp.md): clasificación de pagos `FALLIDA` y `EXPIRADA` con `codigo_motivo`, ruta de ayuda y vista de soporte con elegibilidad de reintento o investigación. Sin disputas.
- [Conciliación operativa](../user-stories/operations-transaction-reconciliation.sp.md): reporte diario que compara transacciones, log y saldos con los eventos del mock, con descalces, filtros por fecha y estado, y resumen diario.
- Soporte y operaciones son roles internos que consumen vistas y reportes; no ingresan a la billetera.
- Datos compartidos por todos los pagos: `cuentas_individuales`, `documentos_deuda`, `transacciones` y `log_transacciones`, con estados de pago `PENDIENTE_CONFIRMACION`, `PENDIENTE`, `APROBADA`, `FALLIDA` y `EXPIRADA`.
- Instrumentación básica del onboarding (W1, criterio 14); el funnel de checkout y la activación al mes 3 quedan como referencia de negocio.

### Fuera de alcance

- Despliegue multipaís amplio dentro de esta épica.
- Programas avanzados de lealtad o mecánicas de crecimiento no esenciales.
- Paridad funcional completa entre todos los proveedores/bancos externos desde el día uno.
- Exposición de APIs de pago abiertas y autoservicio para terceros.
- Para la hackatón: lanzamiento comercial, uso de dinero o documentos de personas, captura biométrica e integración de proveedores para verificar identidad. Una API biométrica no es una dependencia de W1.
- Para la hackatón: proveedor de pagos real, extornos, devoluciones, reclamos y disputas, pagos entre personas, pagos parciales, administración de comercios, deudas y QR, y pantallas de administración del mock.
- Recuperación de contraseña, unión de cuentas con Google, cambio de perfil o límites, ingreso con celular o SMS y varios representantes por comercio (W1).

## Métricas de éxito

Para la hackatón se debe demostrar el recorrido en modo prueba y los criterios de cada historia: W1 exige registro persistente, ingreso, acceso por estado, rechazo de duplicados y sesión máxima de cinco minutos; W2 y los pagos de deuda exigen resultado persistido, sin duplicar transacciones ni movimientos; la conciliación debe mostrar descalces y totales diarios. Los siguientes son objetivos de negocio para una evolución posterior, no evidencia de resultados de la demostración:

- MVP de wallet lanzado dentro de un trimestre.
- La caída en checkout baja de 30% a 8%.
- El tiempo de finalización de onboarding baja de 8 minutos a 3 minutos.
- El MAU se mantiene entre 1,000 y 2,000 en los meses 1-3 posteriores al lanzamiento.
- El CAC es de PEN 10 por usuario nuevo en los meses 1-3 posteriores al lanzamiento.

## Supuestos y restricciones

- El ecosistema es multirriel; el MVP no debe asumir un único riel de procesamiento de extremo a extremo.
- Para un futuro lanzamiento comercial, las integraciones de pago son contractuales y requieren habilitaciones operativas; no son requisito de la demostración en modo prueba.
- Los límites por proveedor pueden estar por debajo del máximo regulatorio; el producto y los mensajes UX deben contemplarlo.
- El producto debe sostener la expectativa operativa de pagos inmediatos con alias (24x7x365).
- El rango de MAU (1,000-2,000) y el objetivo de CAC (PEN 10) son umbrales de negocio definidos por el Product Owner.

## Dependencias y riesgos

- Dependencia: los partners de adquirencia/gateway seleccionados para QR y procesamiento wallet son necesarios para preparar el lanzamiento.
- Dependencia de W1: configuración de Google, cuentas de prueba autorizadas y direcciones de retorno permitidas, con claves fuera del repositorio. Cancelaciones y fallos no deben crear sesión; la sesión de Google no amplía los cinco minutos de la billetera.
- Dependencia: W1 provee las cuentas activas que usan W2 y los pagos de deuda; la idempotencia, el manejo de fallas y la conciliación consumen el mismo registro de `transacciones` y `log_transacciones`.
- Riesgo: reintentos sin idempotencia robusta pueden generar duplicidad financiera y desvíos de conciliación.
- Riesgo: transiciones asíncronas del estado de pago pueden deteriorar la confianza si la confirmación no es clara.
- Riesgo: sin reversos ni disputas en el MVP, un pago `APROBADA` es definitivo; los mensajes deben dejarlo claro y el manejo operativo/legal de reversos queda para una evolución posterior.

## Historias y entrega de la épica

| Historia | Entrega esperada | Dependencias |
|---|---|---|
| [W1: Registro y activación](../user-stories/user-onboarding-mvp-completion.sp.md) | Registro, ingreso, activación y billeteras con límite persistidos; sesión de 300 segundos. | Google de prueba, facilitador. |
| [W2: Pago al comercio por QR](../user-stories/payer-low-value-payment-confirmation.sp.md) | Intención, confirmación, resultado, comprobante e historial con saldos atómicos. | W1, proveedor de prueba. |
| [Pagos QR de deuda](../user-stories/merchant-qr-payment-status-visibility.sp.md) | QR por documento, reserva de deuda, resultado persistido y consulta de estado. | W1, mock, tablas compartidas con W2. |
| [Idempotencia](../user-stories/payment-idempotency-protection.sp.md) | Clave por intento y resultado original ante reintentos, en W2 y en pagos de deuda. | W2, pagos de deuda. |
| [Fallas de pago](../user-stories/payment-failure-reversal-handling.sp.md) | Código de motivo, ruta de ayuda y vista de soporte. | W2, pagos de deuda. |
| [Conciliación](../user-stories/operations-transaction-reconciliation.sp.md) | Reporte diario de descalces con filtros y resumen. | `transacciones`, `log_transacciones`, idempotencia. |

Orden sugerido: W1, luego W2 y pagos de deuda en paralelo sobre las tablas compartidas, y después idempotencia, fallas y conciliación.

## Decisiones de alineación entre historias

- Un solo QR: por documento de deuda, generado por el comercio.
- Roles: `CLIENTE` (paga, ingresa con DNI) y `COMERCIO` (genera el QR y recibe, ingresa con RUC), con la autenticación de W1. Soporte y operaciones no ingresan.
- Estados de pago: `PENDIENTE_CONFIRMACION`, `PENDIENTE`, `APROBADA`, `FALLIDA` y `EXPIRADA`; estados de cuenta de W1: `PENDING`, `ACTIVE` y `REJECTED`.
- Saldos: un pago `APROBADA` debita y acredita de forma atómica; los demás estados no mueven saldo.
- Límite de W1: máximo por operación de pago.
- Disputas, extornos y devoluciones: fuera del MVP.
- Idempotencia: los duplicados se registran como `DUPLICADO` en `log_transacciones`.

## Preguntas abiertas

- Vigencia de una intención sin confirmar, monto máximo por operación, ventana de retención de claves de idempotencia, tasa máxima de descalce, `codigo_motivo` de fallas y si el comercio registra documentos de deuda desde la web.
