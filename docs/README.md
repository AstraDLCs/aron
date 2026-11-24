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
   - IP en la bitácora: por defecto queda la IP de Traefik, no la del usuario. Para guardar la IP real, poner en
     `FORWARDED_ALLOW_IPS` la subred de Traefik, que se obtiene con
     `docker network inspect dokploy-network -f '{{(index .IPAM.Config 0).Subnet}}'`.
   - **Nunca** poner `*` en esa variable: con eso cualquiera podría registrar una IP falsa.
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

Modelo predeterminado (`DEFAULT_AI_MODEL` en `fastapi/app/config.py`): `nvidia/nemotron-3-ultra-550b-a55b:free`,
con respaldos (`DEFAULT_AI_FALLBACK_MODELS`) `google/gemma-4-31b-it:free`, `google/gemma-4-26b-a4b-it:free` e
`inclusionai/ling-3.2-flash:free`.
Se puede cambiar desde la configuración de la app, pero **solo se aceptan modelos gratuitos** (id terminado en `:free`).

- **Modelos saturados:** los gratuitos suelen responder 429 «rate-limited upstream». La API prueba los modelos en
  orden: el elegido, sus respaldos y, al final, la cadena predeterminada (hasta 6). Si todos están saturados, la
  postulación sigue «En cola» y se reintenta sola sin gastar intentos. El límite diario de la cuenta pausa la cola
  hasta el reinicio.
- **Ver qué pasa:** el worker deja su estado cada pocos segundos («Clasificando a…», «Esperando para reintentar…»,
  «Sin clave de OpenRouter…»). La app lo muestra en el indicador de IA de la barra superior y en Configuración →
  Cola de la IA, junto con la última señal, el próximo intento y el último motivo. Si el worker no da señales en
  90 s, la app avisa que el contenedor `worker` puede estar detenido.

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
- [ ] `ALLOW_WIPE=false` cuando la app deje de ser una prueba (desactiva el borrado total con Ctrl+Alt+B).

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

En desarrollo (`npm run tauri dev`) la app usa la API local, `http://localhost:8000`, y el servidor se puede
cambiar en el diálogo «Servidor». El instalador (`.msi`) se conecta siempre al servidor oficial (ver más abajo).

### Prueba de humo de la interfaz (antes de publicar)

Recorre la app real en Edge (sin ventana): inicia sesión, abre las 9 pestañas y los diálogos con «+ Nuevo…», y
falla si alguna pantalla queda en blanco o hay un error de JavaScript. Guarda una captura por paso.

```
npx vite --port 1420          # en otra terminal; la API local debe estar encendida
npm run smoke                 # SEED_OLD_SUMMARY=1 simula datos guardados por una versión anterior
```

Variables: `SMOKE_EMAIL`, `SMOKE_PASSWORD` (por defecto la cuenta demo), `OUT_DIR` (capturas), `BROWSER`.

### Generar el instalador (.msi)

```
npx tauri build --config tauri.release.json --bundles msi
```

`tauri.release.json` compila el frontend en `dist-release` antes de empaquetar. La primera vez, Tauri descarga
WiX Toolset. El instalador queda en:

```
rebuild/tauri/src-tauri/target/release/bundle/msi/Pulso Laboral_<versión>_x64_es-ES.msi
```

Sin `--bundles msi` se generan el `.msi` y el instalador NSIS (`bundle/nsis/…-setup.exe`).

### Publicar una versión en la página de descarga

La API sirve en `/` una página pública para descargar la app, y el instalador en `/descargar/windows`. Ambas
rutas son públicas; las de `/api` siguen pidiendo sesión. La página ofrece el `.msi` de versión más alta que
encuentra en `rebuild/fastapi/downloads/` y muestra su tamaño y su huella SHA-256.

1. Subir `version` en `rebuild/tauri/src-tauri/tauri.conf.json`. Una versión mayor permite que el MSI actualice
   una instalación anterior.
2. Generar el `.msi` (ver arriba).
3. Copiarlo a `rebuild/fastapi/downloads/` con el nombre `PulsoLaboral_<versión>_x64_es-ES.msi`, sin espacios.
   Borrar el anterior para no engordar el repositorio.
4. Hacer commit y push; Dokploy lo publica en el siguiente despliegue.

### Borrado total (solo versión de prueba)

Con la sesión iniciada, **Ctrl + Alt + B** abre un diálogo para borrar todos los datos del servidor. Hay que
escribir `BORRAR` para confirmar.

- **Se borra, para todos los usuarios:**
  - organigrama, requerimientos y fuentes;
  - candidatos, personas y decisiones;
  - todos los CV, incluidos los archivos del servidor;
  - pruebas, criterios y conversaciones con la IA.
- **Se conserva:** las cuentas, la bitácora (el borrado queda registrado con el nombre de quien lo hizo) y la
  configuración (modelo de IA y umbral).
- Una casilla permite volver a cargar los datos de demostración, sin candidatos.
- La carpeta de CV de la PC no se toca. Si se vuelve a sincronizar, los CV se suben de nuevo.
- El servidor lo permite mientras `ALLOW_WIPE=true`, que es el valor por defecto. Con `false`, la API responde
  403.

### Servidor de la API

- El endpoint oficial está en `OFFICIAL_API_BASE_URL`, en `rebuild/tauri/src/api/config.ts`
  (`https://aron.astra-industria.dev`). Si cambia, hay que volver a generar el instalador.
- El instalador usa siempre ese servidor. Ignora cualquier URL guardada de pruebas anteriores, y en la app el
  servidor se muestra pero no se puede editar.
- Solo `npm run tauri dev` permite cambiar el servidor: Configuración → Servidor, o el diálogo «Servidor» de la
  pantalla de inicio de sesión.
- La API acepta siempre los orígenes de la app de escritorio (`http://tauri.localhost`, `https://tauri.localhost`
  y `tauri://localhost`). `CORS_ORIGINS` solo agrega orígenes extra y no hace falta definirla.

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
6. Una persona decide: Aprobado, Rechazado o Contratado, desde cualquier estado y sin pasos obligatorios. La IA
   nunca decide sola.
7. Al marcar Contratado se cubre una plaza del requerimiento. Si no hay requerimiento con plaza libre, se crea uno
   de 1 plaza automáticamente, y queda en la bitácora.
8. Consultar la bitácora (quién hizo qué) y descargar los reportes.

Nada en la interfaz exige ir a otra pantalla primero:
- Cada selección de puesto, fuente o requerimiento tiene «+ Nuevo…» para crearlo ahí mismo: al subir CV, en el alta
  manual, al mover un CV, al crear un requerimiento, al contratar, al mover un puesto en el organigrama y al enviar
  una propuesta a una fuente.
- Al sincronizar o importar una carpeta, si un puesto o una fuente no existe, se crea con el nombre de la carpeta
  (puesto con área «Sin área», fuente «Bolsa Nacional») y sus CV se suben en la misma pasada.
