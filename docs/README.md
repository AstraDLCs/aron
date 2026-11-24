# Pulso Laboral (reconstrucción)

## API (FastAPI + PostgreSQL)

Todo el código de la API está en `rebuild/fastapi`. Los comandos se ejecutan desde esa carpeta.

### Requisitos

- Docker y Docker Compose.
- Una clave de OpenRouter (opcional: sin ella las postulaciones quedan en `Sin IA`, con puntaje por reglas).

### Puesta en marcha

1. Copiar la configuración y completarla:

   ```
   cp .env.example .env
   ```

   Editar `.env`: poner un `JWT_SECRET` aleatorio (mínimo 32 caracteres) y, si se usará la IA,
   `OPENROUTER_API_KEY=<tu clave>`.
2. Levantar los servicios (base de datos, API y worker de la IA):

   ```
   docker compose up -d --build
   ```

   La API queda en `http://localhost:8000` (`GET /api/health`). Las migraciones se aplican al iniciar.
3. Cargar los datos de demostración (solo funciona con la base vacía; si ya hay puestos devuelve 1):

   ```
   docker compose exec api python -m app.seed --demo
   ```

   Carga la empresa Compañía Minera Las Bravas, 28 puestos, 15 requerimientos (32 plazas), 6 fuentes y 2 criterios.
4. Pruebas: `docker compose run --rm api pytest -q`.

### Respaldo y restauración

- `GET /api/datacenter/backup` descarga un JSON con todos los datos de negocio (no incluye cuentas ni bitácora).
- `POST /api/datacenter/restore` con `{"confirm": "RESTAURAR", "backup": {...}}` reemplaza los datos de negocio.
  Marca como faltantes los CV cuyo archivo no está en `data/rrhh`. Las cuentas y la bitácora no se tocan.
- Los archivos de CV viven en `./data/rrhh` (montada en `/data/rrhh`): respaldarla aparte.

### Modelo de IA

Modelo predeterminado: `google/gemma-4-31b-it:free` (OpenRouter, definido el 2026-11-24), con respaldos
`google/gemma-4-26b-a4b-it:free` e `inclusionai/ling-3.2-flash:free`. Se puede cambiar desde la configuración de la app.

### Cupos de OpenRouter y privacidad

- Los modelos gratuitos de OpenRouter tienen un límite diario de solicitudes; el worker clasifica como máximo
  15 postulaciones por minuto y, si recibe el límite diario (429), se pausa hasta el reinicio.
- **Aviso de privacidad:** el texto de cada CV (nombre, documento, contacto, trayectoria) se envía a OpenRouter y al
  proveedor del modelo para clasificarlo. Los modelos gratuitos pueden registrar o usar esos datos. Informe a los
  postulantes y no active la IA si no cuenta con su consentimiento.

### Despliegue en un servidor

1. Usar un `JWT_SECRET` propio y largo, y fijar `REGISTRATION_MODE=invite` con un `INVITE_CODE` secreto:
   solo podrá crear cuenta quien conozca el código.
2. Ajustar `CORS_ORIGINS` al origen de la app de escritorio.
3. Poner la API detrás de HTTPS (proxy inverso) y no exponer el puerto de PostgreSQL.
4. Crear las cuentas, cargar o importar los datos y programar copias del respaldo y de `data/rrhh`.
