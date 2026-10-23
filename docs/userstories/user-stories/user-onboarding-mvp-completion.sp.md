# W1: Registro y activación de billetera de prueba

Como cliente o comercio,
quiero registrarme e ingresar desde una web adaptable a mi celular o computadora en modo prueba,
para consultar mis billeteras de prueba cuando mi cuenta esté activa.

Estado: definición para la hackatón; todavía no implementada. La entrega demostrará lo aprendido con apoyo de IA, sin dinero ni documentos de personas.

## Criterios de aceptación

1. La web permite completar registro, ingreso y consulta sin instalar una aplicación, en pantallas de celular de 360 píxeles y computadora de 1280 píxeles de ancho, sin ocultar campos ni botones. Muestra los pasos y qué hacer después.

2. Al registrarse se distingue entre persona como cliente, identificada con DNI, y empresa como comercio, identificada con RUC. Ambos deben proporcionar correo y celular peruano; el registro sin Google también pide contraseña.

3. Se valida correo con formato válido, DNI de ocho dígitos, RUC de once con dígito de control válido y celular de nueve que empieza con 9. El celular admite +51, espacios o guiones y se guarda con +51 y sin separadores. Si falta un dato obligatorio o es inválido, no se crea la cuenta y se indica qué corregir.

4. Cada DNI identifica un cliente y cada RUC un comercio. Si el documento, correo o celular ya existe, se rechaza el nuevo registro sin modificar ni vincular cuentas. El correo se compara sin espacios externos ni diferencias de mayúsculas y el celular con el formato del punto anterior. Dos registros simultáneos con un mismo dato solo pueden crear una cuenta. El mensaje no revela qué dato existe.

5. La cuenta comienza pendiente (PENDING). El facilitador de la hackatón usa un control reservado de prueba para dejarla pendiente, aprobarla (ACTIVE) o rechazarla (REJECTED). Solo se resuelven cuentas pendientes. El resultado se conserva; el registro y el ingreso del usuario no permiten cambiarlo. Las cuentas no activas pueden ingresar para consultar su estado, pero ven un mensaje de billetera bloqueada.

6. Al ingresar se elige el rol: Cliente (persona) o Comercio. El cliente ingresa con DNI y contraseña, o con correo y contraseña, y el comercio con RUC y contraseña, o con correo y contraseña; ambos pueden usar Google. En el ingreso local se pide un solo identificador (DNI o RUC según el rol, o correo), no varios a la vez. El documento del otro rol no sirve para ingresar y ningún documento sustituye la contraseña. Una cuenta creada solo con Google no recibe otra contraseña automáticamente. Los errores son genéricos y se aplica el límite de intentos aprobado para la prueba. Solo cliente y comercio ingresan a la billetera; el cliente paga y el comercio genera el QR y recibe el pago. Soporte y operaciones no tienen ingreso.

7. «Continuar con Google» se conecta con Google usando cuentas de prueba autorizadas, sin pedir su contraseña en la billetera. Se comprueba la respuesta de Google antes de abrir sesión. En el primer acceso se completan perfil, celular y DNI o RUC antes de crear la cuenta pendiente; después se recupera la misma cuenta. No se duplican ni vinculan cuentas automáticamente. Cancelación, fallo o respuesta inválida no crean cuenta ni sesión y permiten reintentar. Google no verifica documentos ni activa la billetera; mostrar éxito sin consultar Google no cumple este criterio.

8. «Probar biometría» es una simulación identificada como tal, disponible solo en modo prueba y después de ingresar a una cuenta de demostración. Permite elegir éxito, fallo o cancelación y muestra ese resultado, sin usar cámara, huellas ni API externa. No abre otra sesión, activa cuentas ni amplía la sesión vigente. No se presenta como comprobación facial o de huella del dispositivo.

9. Toda sesión de billetera, incluido Google, vence a los 300 segundos desde el ingreso, aunque haya actividad. No se renueva automáticamente ni al cambiar de billetera o probar biometría. Al vencer se bloquean las consultas y se solicita ingresar otra vez. Cerrar sesión corta el acceso de inmediato, incluso si se reutilizan sus datos de acceso. El estado de la cuenta no cambia y la sesión de Google no amplía este plazo.

10. Cada titular tiene una cuenta de acceso y una billetera inicial bloqueada hasta estar activo. Cada billetera es una fila de `cuentas_individuales` con un saldo de prueba en PEN y estado `PENDING`, `ACTIVE` o `REJECTED`. Solo ACTIVE permite añadir, listar y seleccionar billeteras propias, con nombres distintos dentro de la cuenta y hasta el máximo aprobado, contando la inicial. Todas se asocian al mismo DNI o RUC, sin registrar otro usuario. No se admiten billeteras ajenas, registros incompletos ni superar el máximo con solicitudes simultáneas.

11. El titular puede elegir un límite en soles mayor que cero, con hasta dos decimales y sin superar el máximo aprobado. Si lo omite, se usa el máximo. Se rechazan texto, cero, negativos, exceso de decimales y montos superiores al permitido. El límite se muestra y conserva, se comparte entre sus billeteras, no aumenta al crear otra y se aplica a cada operación de pago; no representa dinero disponible.

12. Cada consulta comprueba que la sesión sea válida y que la información pertenezca al usuario, aunque se intente cambiar el identificador de la billetera. Cuenta, estado, billeteras y límite se conservan al cerrar sesión o reiniciar la aplicación. Las contraseñas y los datos de acceso se protegen y no se muestran ni se incluyen en registros de seguimiento.

13. Todo el recorrido se identifica como «Modo prueba». Se usan DNI, RUC y celulares ficticios, sin consultar RENIEC, SUNAT o proveedores de verificación de documentos ni enviar SMS o correos desde la billetera. Google utiliza sus cuentas de prueba y sus correos autorizados. La verificación de documentos y la biometría son simuladas; validar formatos no demuestra identidad ni propiedad.

14. Se guardan fecha y hora del inicio del formulario, pasos completados, resultado de verificación y primera activación, con un identificador interno y sin datos personales. Para la prueba, la duración exitosa va desde abrir el formulario hasta la primera activación. No se duplican activaciones ni se cuentan pendientes o rechazos como exitosos.

15. W1 permite registrar, guardar, ingresar y consultar cuentas y billeteras de prueba; no basta mostrar pantallas de éxito. Pagos y cambios de saldo corresponden a [W2](./payer-low-value-payment-confirmation.sp.md) y a [Pagos QR de documentos de deuda](./merchant-qr-payment-status-visibility.sp.md), incluida la aplicación del límite por operación a esos pagos. Quedan fuera la biometría del dispositivo, recuperación de contraseña, unión de cuentas con Google, cambio de perfil o límites, varios representantes por comercio, traspaso de billeteras, reapertura de rechazados e ingreso con celular o códigos por SMS.

## Contexto

1. Épica: [MVP de wallet en Perú](../epic/peru-wallet-mvp.sp.md). W1 prepara las cuentas, billeteras y la sesión para W2 y los pagos QR de deuda.

2. La hackatón busca demostrar un recorrido funcional en modo prueba y la aplicación de lo aprendido con IA; no supone un lanzamiento comercial. Los objetivos de la épica (registro de 8 a 3 minutos, entre 1,000 y 2,000 usuarios activos al mes y costo de adquisición de PEN 10) son referencias de negocio, no resultados que esta demostración pueda acreditar.

## Supuestos y decisiones pendientes

1. Aprobar el máximo propuesto de PEN 1,000.00 y hasta tres billeteras por titular para la demostración. El límite es máximo por operación de pago; no es un máximo legal.

2. Aprobar las reglas de contraseña y el límite de intentos antes de desarrollar. Se propone un mínimo de ocho caracteres y hasta cinco intentos fallidos por cuenta en cinco minutos; alcanzado el límite, bloquear nuevos intentos durante cinco minutos. Son valores para la prueba, no decisiones aprobadas. El facilitador y la protección de su control de revisión también deben definirse.

3. Preparar la configuración de Google, las cuentas de prueba autorizadas y las direcciones de retorno permitidas; sus claves no se guardan en el repositorio. Google se utiliza conectado en modo prueba; la biometría se simula sin depender de una API gratuita.

4. Antes de aceptar W1, demostrar ambos perfiles en los tres estados, rechazo de duplicados, límites válidos e inválidos, ingreso y cancelación con Google, los tres resultados biométricos simulados y bloqueo de sesión a los 300 segundos o al cerrarla. Son comprobaciones pendientes, no resultados ya obtenidos.