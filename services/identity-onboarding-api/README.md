# Identity Onboarding API

Adaptador Quarkus que consume solo los cuatro endpoints W1 del mock KYC configurado.

## Arranque en la red local

Desde la raíz del repositorio, con Docker:

```sh
docker compose -f infra/compose.yaml up --build -d identity-onboarding-api
```

Con Podman:

```sh
podman compose -f infra/compose.yaml up --build -d identity-onboarding-api
```

Puerto publicado solo en localhost: `http://127.0.0.1:8081`.
Swagger UI: `http://127.0.0.1:8081/q/swagger-ui`.

## Rutas

- `GET /api/v1/health`
- `POST /api/v1/kyc/verifications`
- `GET /api/v1/kyc/verifications/{id}`
- `POST /api/v1/kyc/verifications/{id}/decision`
- `GET /api/v1/wallets/{id}`

Importa `postman/identity-onboarding.postman_collection.json`; su `baseUrl` predeterminada es `http://localhost:8081`. La colección guarda automáticamente los IDs KYC y wallet al crear la verificación.

El upstream exige `documentType: TEST` y `document` con prefijo `TEST-`. Crear KYC modifica datos persistentes compartidos del grupo 3; no uses el endpoint de reset. La decisión humana requiere `IDENTITY_OPERATOR_KEY` configurada fuera de Git y el header `X-Operator-Key`. Este microservicio no implementa registro/login porque esos endpoints no existen en el contrato compartido.