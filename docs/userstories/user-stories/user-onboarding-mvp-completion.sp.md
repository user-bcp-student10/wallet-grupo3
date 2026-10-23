# W1: Registro y activación de billetera de prueba

Como cliente o comercio,
quiero registrarme e ingresar de forma segura desde una web que se adapte a mi celular o computadora responsivo para cualquier dispositivo,
para consultar mis billeteras de prueba cuando mi cuenta esté activa.

Estado: propuesta para revisión; todavía no implementada.

## Criterios de aceptación

1. La web se adapta a cualquier dispositivo sin instalar una aplicación. El registro muestra los pasos, el avance y qué hacer después.

2. Al registrarse se distingue entre persona como cliente, identificada con DNI, y empresa como comercio, identificada con RUC. Ambos deben proporcionar correo y celular peruano; el registro sin Google también pide contraseña.

3. Los datos obligatorios deben estar completos y tener formato válido: DNI de ocho dígitos, RUC de once con dígito de control válido y celular de nueve que empieza con 9, con código de país +51. Si hay errores, no se avanza y se explica qué corregir.

4. Cada DNI o RUC identifica a un solo titular. Correo y celular tampoco pueden repetirse en otro registro; se comparan con un formato uniforme. Un intento duplicado no crea ni modifica cuentas, aunque lleguen dos solicitudes a la vez, y no revela datos de otros usuarios.

5. La verificación de identidad es de prueba: la cuenta comienza pendiente (PENDING) y puede quedar activa (ACTIVE) o rechazada (REJECTED). El resultado se conserva y solo una cuenta activa accede a sus billeteras. Las demás pueden ingresar para ver su situación y el motivo de bloqueo; el ingreso normal no permite cambiar ese resultado.

6. Se ingresa con correo y contraseña para ambos perfiles, o DNI y contraseña para cliente. También se puede usar Google o el acceso del dispositivo previamente habilitado. DNI y RUC no son contraseñas; el RUC no sirve para ingresar. Los intentos fallidos se limitan y el mensaje no revela si existe una cuenta.

7. Google permite registrarse e ingresar sin crear otra contraseña para la billetera. La primera vez se completan los datos faltantes y después se recupera la misma cuenta; no se vinculan cuentas automáticamente. Google no verifica DNI o RUC ni activa la cuenta. Si se cancela o falla, no se crea una cuenta ni una sesión y se permite reintentar.

8. Después de confirmar su identidad con un método de ingreso existente, el usuario puede habilitar el acceso con rostro, huella o PIN del dispositivo, según compatibilidad. Este acceso permite iniciar sesión sin escribir la contraseña de la billetera; no se guardan fotos, huellas ni datos del rostro. Si falla o no está disponible, se ofrece otro método ya habilitado.

9. Toda sesión dura como máximo cinco minutos desde el ingreso, aunque se siga usando la web. No se renueva automáticamente; al vencer se debe ingresar otra vez. Cerrar sesión corta el acceso de inmediato. La cuenta sigue activa aunque termine la sesión.

10. Cada titular tiene una cuenta de acceso y una billetera inicial. Cuando está activo puede crear y consultar otras billeteras propias, con nombres distintos y hasta la cantidad permitida, todas asociadas a su mismo DNI o RUC. No necesita registrarse nuevamente ni puede consultar billeteras ajenas.

11. El titular puede elegir un límite en soles mayor que cero, con hasta dos decimales y sin superar el máximo del producto. Si no elige uno, se usa el máximo. El límite se muestra y conserva, es compartido por sus billeteras y no aumenta al crear otra; no representa dinero disponible.

12. El sistema comprueba en cada acceso que la sesión sea válida y que la información pertenezca al usuario. Las contraseñas y los datos de acceso se protegen y no se muestran ni se incluyen en registros de seguimiento.

13. La demostración usa datos ficticios, sin verificar documentos reales ni consultar RENIEC, SUNAT o proveedores de identidad, y sin enviar mensajes o correos reales. Las simulaciones se identifican claramente como pruebas: un formato válido no demuestra que una identidad sea real.

14. Se registra cuándo empieza el registro, qué pasos se completan y cuál es el resultado, sin guardar datos personales en ese seguimiento. La primera activación se cuenta una sola vez; las cuentas pendientes o rechazadas no se cuentan como activadas.

15. W1 prepara cuentas y permite consultar billeteras de prueba; los pagos y cambios de saldo corresponden a W2/W3, incluida la aplicación del límite a esas operaciones. No incluye recuperación de contraseña, unión de cuentas de Google con otras cuentas, cambio de perfil o límites, varios representantes por comercio, traspaso de billeteras, reapertura de cuentas rechazadas ni ingreso con celular o códigos por SMS.

## Contexto

1. Épica: [MVP de wallet en Perú](../epic/peru-wallet-mvp.sp.md). W1 prepara las cuentas para W2/W3.

2. Objetivos de lanzamiento: reducir el registro de 8 a 3 minutos, mantener entre 1,000 y 2,000 usuarios activos al mes y un costo de adquisición de PEN 10 por nuevo usuario en los primeros tres meses. Se verifican con actividad y gastos reales, no solo con esta demostración.

## Supuestos y decisiones pendientes

1. Aprobar el máximo propuesto de PEN 1,000.00 y hasta tres billeteras por titular para la demostración. Definir si el límite aplica al saldo, a cada operación o al total de un período; no son máximos legales.

2. Confirmar las reglas de contraseña, cuántos intentos fallidos se permiten y quién decide si la verificación de prueba se aprueba o rechaza.

3. Confirmar si Google se conecta con cuentas de prueba autorizadas o se simula, y desde qué momento hasta cuál se mide la duración del registro.