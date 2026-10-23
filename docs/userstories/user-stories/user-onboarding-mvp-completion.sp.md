# W1: Registro y activación de billetera de prueba

Como cliente o comercio,
quiero registrarme e ingresar de forma segura desde mi celular o computadora,
para consultar mis billeteras de prueba cuando mi cuenta esté activa.

Estado: propuesta para revisión; todavía no implementada.

## Criterios de aceptación

1. La web funciona en smartphone y computadora, sin instalar una app, con pasos guiados y mensajes claros.
2. El registro solicita rol cliente o comercio, correo, celular peruano y DNI para cliente o RUC para comercio.
3. Se validan datos obligatorios y formatos en pantalla y servidor: DNI de ocho dígitos, RUC de once con dígito verificador y celular de nueve que empieza con 9, normalizado con +51. Los errores indican qué corregir.
4. Correo, celular y documento son únicos por titular. Si cualquiera existe, se rechaza el registro sin duplicar, modificar ni vincular cuentas, incluso ante solicitudes simultáneas. Se normalizan los datos antes de comparar y no se revela qué dato existe.
5. Se ingresa con correo y contraseña, DNI y contraseña para cliente, Google o una passkey registrada. DNI y RUC no son contraseñas; el RUC no permite ingresar. Los errores son genéricos y se limitan los intentos.
6. Google permite registrarse e ingresar sin otra contraseña de wallet, completando los datos faltantes y recuperando siempre la misma cuenta. Usa OpenID Connect/OAuth2 con PKCE y validación del proveedor; no verifica DNI/RUC ni activa la cuenta automáticamente.
7. La opción «Ingresar con passkey» permite usar rostro, huella o PIN del dispositivo tras registrar la credencial con reautenticación. El servidor valida la respuesta WebAuthn antes de abrir sesión; la wallet no guarda biometría. Si falla, se cancela o no es compatible, se ofrece otro método registrado sin crear sesión.
8. La verificación de identidad (KYC) es simulada: comienza en PENDING y puede resolverse como ACTIVE o REJECTED mediante un control exclusivo de demo. El resultado se conserva; solo ACTIVE habilita billeteras. Los demás estados pueden ingresar y consultar su situación, con un mensaje claro de bloqueo.
9. Existe una cuenta de acceso por DNI o RUC, con una billetera inicial y otras asociadas al mismo titular. Solo ACTIVE permite añadirlas, listarlas o seleccionarlas, con alias distintos y hasta el máximo configurable, sin crear otros usuarios ni dejar registros parciales.
10. El titular elige un límite positivo en PEN, con hasta dos decimales y sin superar el máximo del producto; si lo omite se usa ese máximo. Se muestra y conserva, es compartido entre sus billeteras y no aumenta al crear otra ni agrega dinero.
11. Todos los métodos generan un JWT propio para la API por HTTPS, válido solo cinco minutos desde el ingreso, sin renovación automática. El servidor valida firma, emisor, destinatario, vigencia y sesión en cada petición; no acepta tokens de Google como acceso propio. Al vencer exige ingresar otra vez; cerrar sesión revoca inmediatamente incluso las copias del token. Vencer la sesión no cambia el estado ACTIVE de la cuenta.
12. Cada usuario solo accede a sus datos y billeteras, con permisos comprobados por el servidor. Token inválido, vencido o revocado recibe 401; una sesión válida sin permiso recibe 403. Contraseñas con hash, tokens solo en memoria del navegador y secretos fuera del repositorio; no se exponen datos sensibles en tokens ni registros.
13. La demo usa datos ficticios, sin KYC real, consultas RENIEC/SUNAT ni envío real de SMS o correos. La simulación de Google y el autenticador virtual se identifican como pruebas, no integraciones reales. Validar formato no acredita identidad ni propiedad.
14. Se registran inicio, pasos, resultado y primera activación con fecha e identificador interno, sin datos personales. No se duplican activaciones ni se cuentan pendientes o rechazos como exitosos.
15. W1 solo prepara cuentas y permite consultar billeteras. Pagos y cambios de saldo, incluida la aplicación monetaria del límite, corresponden a W2/W3. No incluye recuperación de contraseña, vinculación de Google con cuentas locales, cambio de rol o límites, representantes múltiples, transferencia de billeteras, reapertura de KYC rechazado ni ingreso con celular/OTP.

## Contexto

1. Épica: [MVP de wallet en Perú](../epic/peru-wallet-mvp.sp.md). W1 prepara las cuentas para W2/W3.
2. Objetivos de lanzamiento: bajar el onboarding de 8 a 3 minutos, MAU de 1,000 a 2,000 y CAC de PEN 10 en meses 1-3. Requieren medir actividad y gasto reales; activar una cuenta no demuestra MAU ni CAC.

## Supuestos y decisiones pendientes

1. Aprobar los valores propuestos para demo: PEN 1,000.00 y hasta tres billeteras por titular. Definir si el límite aplica a saldo, operación o acumulado; no son máximos regulatorios.
2. Confirmar reglas de contraseña, límite de intentos y revisión humana del KYC (HITL).
3. Confirmar Google real con cuentas de prueba autorizadas o simulado, y los eventos de inicio y fin para medir el onboarding.