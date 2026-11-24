# Pulso Laboral (reconstrucción)

## API (FastAPI + PostgreSQL)

El código de la API está en `rebuild/fastapi`. El `docker-compose.yml` está en la **raíz del repositorio**
(`rebuild/`), y los comandos `docker compose` se ejecutan desde ahí.

| Archivo | Para qué |
|---|---|
| `docker-compose.yml` | Producción (Dokploy u otro servidor): sin puertos publicados, base y CVs en volúmenes con nombre |
| `docker-compose.dev.yml` | Solo local: puerto 8000, código montado con recarga, base de pruebas y CVs en `fastapi/data/rrhh` |
| `.env.example` | Variables; copiar a `.env` (ignorado por git) junto al compose |

### Requisitos

- Docker y Docker Compose.
- Una clave de OpenRouter (opcional: sin ella las postulaciones quedan en `Sin IA`, con puntaje por reglas).

### Desarrollo local

1. Copiar la configuración y completarla:

   ```
   cp .env.example .env
   ```

   Editar `.env`:

   - `JWT_SECRET`: valor aleatorio de al menos 32 caracteres. Para generarlo:

     ```
     python -c "import secrets;print(secrets.token_urlsafe(48))"
     ```

   - `POSTGRES_PASSWORD`: en local puede quedar `pulso`.
   - `REGISTRATION_MODE=open` para registrarse sin código.
   - `OPENROUTER_API_KEY=<tu clave>`, si se usará la IA (se obtiene en https://openrouter.ai/keys).
   - Para no escribir los dos `-f` en cada comando, descomentar `COMPOSE_FILE` y `COMPOSE_PATH_SEPARATOR`
     (en Windows el separador es `;`; en Linux y Mac, `:`).
2. Levantar los servicios (base de datos, API y worker de la IA):

   ```
   docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build
   ```

   La API queda en `http://localhost:8000` (`GET /api/health`). Las migraciones se aplican al iniciar.
3. Cargar los datos de demostración (solo funciona con la base vacía; si ya hay puestos devuelve 1):

   ```
   docker compose exec api python -m app.seed --demo
   ```

   Carga la empresa Compañía Minera Las Bravas, 28 puestos, 15 requerimientos (32 plazas), 6 fuentes y 2 criterios.
4. Pruebas: `docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm api pytest -q`.

### Despliegue con Dokploy (Docker Compose)

1. Crear un servicio **Compose** que apunte a este repositorio, rama `main`, con **Compose Path**
   `./docker-compose.yml`.
2. En **Environment**, cargar las variables de `.env.example`. Como mínimo:
   - `JWT_SECRET`, de 32 caracteres o más;
   - `POSTGRES_PASSWORD`, solo con letras, números, `-` o `_`;
   - `REGISTRATION_MODE=invite` con un `INVITE_CODE` secreto;
   - `OPENROUTER_API_KEY`.

   Dokploy escribe esas variables en un `.env` junto al compose, y el compose se las pasa a los contenedores. Si
   falta `JWT_SECRET`, el despliegue se detiene con el mensaje «Falta JWT_SECRET».
3. En **Domains**, agregar el dominio al servicio `api`, puerto `8000`, con HTTPS (Let's Encrypt). La app de
   escritorio exige `https://` para servidores que no sean `localhost`.
4. Desplegar. Las migraciones se aplican solas al iniciar la API.
5. Datos de demostración (opcional, solo con la base vacía): en la terminal del contenedor `api`, ejecutar
   `python -m app.seed --demo`.
6. Hacer **Volume Backups** de los volúmenes `pgdata` (base de datos) y `rrhh_data` (archivos de CV). Dokploy solo
   respalda volúmenes con nombre.

Avisos:

- No usar `docker-compose.dev.yml` en el servidor.
- Al eliminar el servicio en Dokploy, si se marca borrar volúmenes, se pierden la base y los CVs.

### Respaldo y restauración

- `GET /api/datacenter/backup` descarga un JSON con todos los datos de negocio (no incluye cuentas ni bitácora).
- `POST /api/datacenter/restore` con `{"confirm": "RESTAURAR", "backup": {...}}` reemplaza los datos de negocio.
  Marca como faltantes los CV cuyo archivo no está en la carpeta de CVs. Las cuentas y la bitácora no se tocan.
- Los archivos de CV viven en `/data/rrhh` dentro de los contenedores. En el servidor están en el volumen
  `rrhh_data`; en local, en `fastapi/data/rrhh`. Hay que respaldarlos aparte.

### Modelo de IA

Modelo predeterminado (`DEFAULT_AI_MODEL` en `fastapi/app/config.py`): `google/gemma-4-31b-it:free`
(OpenRouter, elegido el 2026-11-24), con respaldos (`DEFAULT_AI_FALLBACK_MODELS`)
`google/gemma-4-26b-a4b-it:free` e `inclusionai/ling-3.2-flash:free`.
Se puede cambiar desde la configuración de la app, pero **solo se aceptan modelos gratuitos** (id terminado en `:free`).

### Cupos de OpenRouter y privacidad

- Cupos de los modelos gratuitos de OpenRouter: 20 solicitudes por minuto y, por día, 50 solicitudes si la cuenta
  tiene menos de USD 10 en créditos o 1000 si tiene USD 10 o más.
- El worker clasifica como máximo 15 postulaciones por minuto (`WORKER_RATE_PER_MINUTE`) y, si recibe el límite
  diario (429), se pausa hasta el reinicio.
- **Aviso de privacidad:** el texto de cada CV (nombre, documento, contacto, trayectoria) se envía a OpenRouter y al
  proveedor del modelo para clasificarlo. Los CV son datos personales (Ley 29733, de Protección de Datos Personales).
  Algunos proveedores gratuitos pueden registrar o usar esos datos para entrenar modelos: configure la privacidad en
  su cuenta de OpenRouter (https://openrouter.ai/settings/privacy). Informe a los postulantes y no active la IA si no
  cuenta con su consentimiento.

### Despliegue en un servidor (lista de verificación)

- [ ] `JWT_SECRET` propio, largo y secreto (no reutilizar el de pruebas).
- [ ] `REGISTRATION_MODE=invite` y un `INVITE_CODE` secreto: solo podrá crear cuenta quien conozca el código.
- [ ] `CORS_ORIGINS` ajustado al origen de la app de escritorio.
- [ ] `POSTGRES_PASSWORD` propio (no `pulso`).
- [ ] API detrás de un proxy inverso con HTTPS (en Dokploy, el dominio con Let's Encrypt), con límite de
      peticiones (rate limiting) en `/api/auth/*`. No exponer el puerto de PostgreSQL.
- [ ] Copias de seguridad periódicas de los volúmenes `pgdata` (base de datos) y `rrhh_data` (archivos de CV).
- [ ] Probar la restauración de una copia al menos una vez.
- [ ] Baja de cuentas: `docker compose exec api python -m app.cli users deactivate <email>`.

## App de escritorio (Tauri)

Todo el código está en `rebuild/tauri`. Los comandos se ejecutan desde esa carpeta.

### Requisitos

- Node 20 o superior.
- Rust estable (https://rustup.rs).
- WebView2 en Windows 11 (viene instalado; en Windows 10 se descarga de Microsoft).

### Desarrollo

```
npm install
npm run tauri dev
```

Por defecto la app apunta a `http://localhost:8000` (la API de Docker Compose en la misma PC).

### Generar el instalador

```
npx tauri build --config tauri.release.json
```

`tauri.release.json` compila el frontend en `dist-release` antes de empaquetar. El instalador queda en:

```
rebuild/tauri/src-tauri/target/release/bundle/nsis/Pulso Laboral_0.1.0_x64-setup.exe
```

### Servidor de la API

- Para fijar el endpoint oficial en el instalador, cambiar `DEFAULT_API_BASE_URL` en
  `rebuild/tauri/src/api/config.ts` (hoy `http://localhost:8000`) y volver a generar el instalador.
- Cada usuario también puede cambiarlo sin recompilar: Configuración → Servidor, o el diálogo «Servidor» de la
  pantalla de inicio de sesión. Los servidores remotos deben usar `https` (`http` solo se admite para localhost).

### Carga de CV

Estructura de carpetas (en la PC o en el servidor):

```
rrhh/<carpeta del puesto>/<carpeta de la fuente>/archivo.pdf
```

- Formatos aceptados: `.pdf`, `.docx`, `.txt`, `.rtf`. Tamaño máximo: 15 MB.
- Los duplicados dentro de un mismo puesto se detectan por contenido y se rechazan.
- Un CV eliminado no se vuelve a importar, salvo que se active «Permitir reimportar».

Cuatro formas de cargar CV:

1. **Subir en la app**: botón de subir CV dentro del puesto.
2. **Importar carpeta**: elegir una carpeta con la estructura anterior.
3. **Sincronizar la carpeta de la PC**: se configura una vez; se sincroniza al abrir la app y con «Sincronizar ahora».
4. **Copiar en el servidor**: dejar los archivos en la carpeta de CVs del servidor (en local,
   `rebuild/fastapi/data/rrhh`; en Dokploy, el volumen `rrhh_data`). El servidor revisa esa carpeta cada 5 minutos
   (`SERVER_SCAN_INTERVAL_S=300`).

### Flujo de uso

1. Registrarse (con el código de invitación si el servidor lo exige).
2. Armar el organigrama (áreas y puestos).
3. Crear los requerimientos (plazas por puesto).
4. Cargar los CV por cualquiera de las cuatro vías.
5. La IA pre-aprueba o pre-deniega cada postulación (o queda `Sin IA` con puntaje por reglas).
6. Una persona decide: Aprobado o Rechazado. La IA nunca decide sola.
7. Al marcar Contratado se cubre una plaza del requerimiento.
8. Consultar la bitácora (quién hizo qué) y descargar los reportes.
