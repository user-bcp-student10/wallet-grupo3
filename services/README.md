# Servicios backend

Cada API backend vive en su propia carpeta. Los frontends acceden por las APIs del producto.
La integración con proveedores externos pertenece al servicio que procesa pagos.
Cada servicio mantiene sus pruebas y migraciones de datos.

## Wallet de prueba

Desde la raíz del repositorio, inicia la web del pagador y su adapter local:

```sh
python services/wallet-payments-api/src/server.py
```

Abre `http://127.0.0.1:8000`. El adapter consulta el mock fijo del grupo 3; el
navegador solo llama a rutas del mismo origen. Incluye lectura de wallet e
historial, creación idempotente de pago, consulta/resolución de estado y lectura
de comprobante. La creación o resolución de pagos modifica datos compartidos del
mock; usa solo datos de prueba.

Registro e ingreso (W1) son una función propia de este servicio, porque el mock
no ofrece login: `POST /api/auth/register`, `POST /api/auth/login`,
`GET /api/auth/me` y `POST /api/auth/logout`. Las cuentas se guardan en SQLite
local (`services/wallet-payments-api/data/`, ignorado por Git) con contraseña
scrypt; la sesión es una cookie `HttpOnly` que vence a los 300 s sin renovarse,
y 5 intentos fallidos bloquean 5 minutos. Registrar una cuenta crea una
verificación KYC en el mock compartido del grupo. Wallet, historial y pagos
exigen sesión, y solo un cliente con cuenta `ACTIVE` puede pagar.

Ejecuta las pruebas del adapter sin hacer llamadas al mock:

```sh
python -m unittest discover -s services/wallet-payments-api/tests -v
```