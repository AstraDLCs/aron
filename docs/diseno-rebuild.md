# Diseño y plan: rebuild de Pulso Laboral (API FastAPI + app de escritorio Tauri)

## 1. Contexto e intención

Hoy Pulso Laboral es solo una interfaz React (`src/`). El servidor que atendía `/api/*` no está, y el
proyecto no compila: faltan `package.json`, `vite.config` e `index.html`, y `node_modules` está
truncado. El análisis completo está en `md/rrhh-reclutamiento/informe-objetivo-aplicacion.md`.

El usuario quiere **portar** la aplicación a dos piezas nuevas, ambas dentro de `rebuild/`:

- **`rebuild/fastapi`**: una API en FastAPI que se levanta con **Docker Compose**. Maneja todo: registro
  e inicio de sesión, datos, archivos e IA. Por ahora es una prueba en local; cuando esté lista será la
  API real del proyecto, desplegada en un servidor.
- **`rebuild/tauri`**: una app de escritorio con instalador para Windows, **sin Docker**, que se conecta
  a esa API. La URL del servidor se puede configurar: hoy `localhost`, mañana el servidor real.

Además del port, pidió un **flujo nuevo** centrado en una carpeta de CVs y en IA real:

1. Los usuarios se registran y entran a la app.
2. Arman un **organigrama de puestos de trabajo**.
3. Crean **requerimientos** de personal (por ejemplo, "se necesitan 10 especialistas en perforación").
4. Suben CVs a la carpeta **`rrhh/[puesto]/[fuente]`** (fuente = LinkedIn, Computrabajo, etc.), sin
   repetidos, de cuatro formas:
   - desde la app, subiendo uno o varios CVs y eligiendo a mano el puesto y la fuente;
   - importando una carpeta;
   - sincronizando una carpeta de la PC elegida de antemano;
   - copiando archivos directamente a la carpeta del servidor.
5. Un **modelo de IA de OpenRouter (modelos gratuitos)** clasifica cada CV: extrae los datos personales,
   califica qué tan apto es para el puesto y lo **pre-aprueba o pre-deniega**.
6. **La decisión final es humana.** Cada acción de cada cuenta queda en una **bitácora**: quién aprobó,
   quién subió, quién descargó, etc.

### Decisiones del usuario
| Tema | Decisión |
|---|---|
| Alcance | **Todo junto**: el flujo nuevo más todos los módulos actuales portados (pruebas Excel, KPIs y bolsas, chat IA, informes Word/CSV) |
| Roles | **Todos pueden decidir.** No hay roles con permisos distintos; la bitácora registra quién hizo cada cosa. Los datos son compartidos para todos |
| Decisión | La IA pre-aprueba o pre-deniega. Una persona decide **Aprobado** (pasa a entrevista y pruebas) o **Rechazado**, y luego **Contratado**. **Solo "Contratado" cubre una plaza** |
| Carpeta de la PC | Se sincroniza **al abrir la app** y con el botón **"Sincronizar ahora"**. Los repetidos se detectan por el contenido del archivo |
| CV en varios puestos | **Una postulación por puesto.** El mismo CV puede postular a varios puestos y se evalúa con la IA por separado en cada uno. Solo se considera repetido si se sube **dentro del mismo puesto** |
| Datos a la IA | Se envía el CV completo a OpenRouter, porque se pidió que la IA extraiga los datos personales. El riesgo de privacidad está en la sección 15 |
| IA | OpenRouter con modelos gratuitos |
| Enfoque de datos | **Foto compartida.** La app pide una "foto" (`GET /api/state`) que los módulos actuales usan casi sin cambios. Se refresca después de cada acción y cada ~30 s para ver lo que hicieron otros |
| Ubicación | Todo el código nuevo va en `rebuild/`. El `src/` original no se toca |

### Objetivos
- Que la app de escritorio funcione de punta a punta contra la API local: registro → organigrama →
  requerimiento → CVs → clasificación IA → decisión → contratación → informes y bitácora.
- Que la API quede lista para desplegarse tal cual en un servidor real. La configuración va por `.env`.

### No objetivos (en esta versión)
- Permisos por rol, separar datos por empresa o por usuario, versión web o móvil, OCR de PDFs escaneados.
- Publicar de verdad en portales de empleo: el "envío a bolsa" solo se registra.

### Anti-objetivos (sería un fracaso aunque funcione)
- Que la IA tome decisiones finales o que una decisión no deje rastro en la bitácora.
- Que un CV repetido entre dos veces al mismo puesto, que un CV borrado reaparezca solo, o que se pierda un
  CV que se subió.
- Que el tope diario de OpenRouter bloquee la app. Los CVs deben esperar en cola, no fallar.

---

## 2. Enfoques considerados
- **A. Foto compartida + API organizada por recursos (elegido).** Se reutilizan la interfaz y los módulos
  actuales casi sin cambios y se porta todo rápido. La contra: con miles de candidatos la foto pesa, y
  habrá que optimizarla más adelante.
- **B. Cada pantalla pide sus datos, con paginación.** Escala mejor, pero obliga a reescribir el manejo de
  datos de todos los módulos. Más tiempo y riesgo sumado a "todo junto".
- **C. Guardar toda la app como un único documento JSON, como el servidor original.** Descartado: no
  soporta varios usuarios a la vez, ni la bitácora, ni el organigrama.

---

## 3. Arquitectura

```
App Tauri (Windows)                         rebuild/fastapi  (docker compose)
┌───────────────────────────┐   HTTPS/HTTP  ┌───────────────────────────────────────┐
│ React 19 (UI portada)     │──────────────▶│ api     FastAPI + Uvicorn :8000        │
│ + login, organigrama,     │  Bearer JWT   │ worker  cola IA → OpenRouter (free)    │
│   carpeta CVs, bitácora   │◀──────────────│ db      PostgreSQL 16 (volumen)        │
│ Rust: escanear carpeta    │  {state}      │ ./data/rrhh  ⇄  /data/rrhh (bind mount)│
│ local, hash, guardar      │               └───────────────────────────────────────┘
│ descargas                 │
└───────────────────────────┘
```

- **API:** Python 3.12, FastAPI, SQLAlchemy 2 + Alembic, Pydantic v2 (JSON en camelCase para calzar
  con `src/types.ts`), PyJWT y argon2 (`pwdlib`), httpx para OpenRouter, pypdf y python-docx para leer
  CVs, openpyxl para las pruebas Excel.
- **Worker:** usa la misma imagen que la API y corre otro comando (`python -m app.worker`). Procesa la
  cola de IA y cada 5 min revisa la carpeta del servidor.
- **App:** Tauri v2 + Vite + React 19 + TypeScript + Tailwind 4, con la UI copiada desde `src/`.
  - Plugins: `dialog`, `store`, `opener`.
  - Comandos Rust para leer la carpeta local y guardar archivos.
  - Instalador NSIS para Windows.
- **CORS:** permite `http://tauri.localhost` y `tauri://localhost` (la app instalada) y
  `http://localhost:1420` (desarrollo). Se configura por `.env`.

---

## 4. Modelo de dominio (PostgreSQL)

| Tabla | Qué guarda | Campos clave |
|---|---|---|
| `users` | Cuentas | nombre completo, email (único), hash de contraseña, cargo (informativo), activo, último ingreso |
| `positions` | **Organigrama** | nombre (único), `folder_name` (carpeta, único), área, `parent_id` (reporta a), descripción y **perfil del puesto** (competencias clave, especificaciones técnicas, años mínimos, formación esperada) que usa la IA |
| `sources` | **Fuentes / bolsas** (lo que hoy es `JobBoardChannel`) | nombre, `folder_name` (p. ej. `linkedin`, `computrabajo`), categoría, activa, propuestas enviadas, horas de respuesta. *Candidatos recibidos, preseleccionados y contratados se **calculan***, ya no se guardan como contadores |
| `requirements` | **Requerimientos** (lo que hoy es `JobNeed`) | puesto, cantidad de plazas, urgencia, plazo objetivo, contexto, fuentes donde se publicó, estado (Abierto / Cubierto / Cancelado). *Plazas cubiertas = candidatos "Contratado"* |
| `cv_files` | Archivos de la carpeta | sha256, puesto, **único por (sha256, puesto)**, nombre original, ruta relativa `rrhh/<puesto>/<fuente>/<archivo>`, tipo, tamaño, origen (app / importación / sincronización local / carpeta del servidor), texto extraído y su estado. El mismo archivo en dos puestos ocupa dos copias en disco, una en la carpeta de cada puesto |
| `persons` | **Personas** (datos personales, uno por persona) | nombres, apellidos, documento (DNI/CE), email, teléfono, edad, procedencia, universidad, carrera, años de experiencia, trayectoria, certificaciones y licencias, idiomas; **evaluación psicológica y resultados de pruebas Excel**, que son de la persona y valen para todas sus postulaciones; "posible misma persona que…" |
| `candidates` | **Postulaciones** (persona × puesto; equivalen al `Candidate` de la UI actual) | persona, archivo de CV, puesto, requerimiento (opcional), fuente; **resultado de la IA** para ese puesto (estado de cola, veredicto, puntaje de aptitud, puntajes por pilar, fortalezas, observaciones, criterios aplicados, modelo, fecha, intentos, error); Índice Global (usa la prueba psicológica de la persona); **decisión humana** (estado, nota 1-5, observación, quién decidió y cuándo) |
| `deleted_cv_hashes` | Archivos eliminados a propósito | sha256, puesto, quién y cuándo. Evita que la sincronización o la revisión de la carpeta del servidor los vuelvan a importar. Se puede "permitir reimportar" |
| `recruitment_criteria` | Criterios aprendidos | los mismos campos de hoy; ahora **sí se filtran por área** |
| `test_definitions`, `excel_test_results` | Pruebas | los mismos campos de hoy |
| `ai_conversations`, `ai_messages` | Informe y chat con la IA | los mismos campos de hoy, con voto y nota de retroalimentación |
| `audit_log` | **Bitácora** | fecha y hora, usuario (id y nombre), acción, tipo y id de la entidad, resumen legible, detalles (antes/después), IP. **Solo se agregan filas:** no hay rutas para editar o borrar, y un *trigger* de PostgreSQL impide UPDATE y DELETE |
| `app_settings` | Configuración compartida | nombre de la empresa, modelo de IA, modelos de respaldo, umbral, IA activa, "pausada hasta" |

### Estados
- **Cola de IA:** `En cola` → `Procesando` → `Clasificado` | `Error IA` (se puede reintentar) | `Sin texto`
  (PDF escaneado: se cargan los datos a mano) | `Sin IA` (no hay clave de OpenRouter: solo hay puntaje
  preliminar por reglas).
- **Veredicto de la IA:** `Pre-aprobado` | `Pre-denegado`.
- **Decisión humana:** `Pendiente de revisión` → `Aprobado` → `Contratado`. Desde cualquier estado se puede
  pasar a `Rechazado`, y de `Rechazado` se puede volver a `Aprobado`. Para pasar a `Contratado` hace falta
  un requerimiento abierto con plazas libres; al llenarse, el requerimiento pasa a `Cubierto`
  automáticamente y la bitácora lo registra como acción del sistema. Deshacer una contratación vuelve el
  estado a `Aprobado` y también queda registrado.
- **Acuerdo IA/RR.HH.:** se recalcula. Hay acuerdo cuando un Pre-aprobado termina en Aprobado o
  Contratado, o un Pre-denegado termina en Rechazado. Corrige el hallazgo H-04 del informe.

---

## 5. Carpeta de CVs `rrhh/<puesto>/<fuente>/`

- **En el servidor:** `/data/rrhh` dentro del contenedor, montado desde `rebuild/fastapi/data/rrhh` en la
  máquina. Es la copia oficial.
  - Cada puesto tiene un **nombre de carpeta** que se fija al crearlo y se puede editar; si se edita, el
    servidor mueve los archivos. Cambiar el nombre visible del puesto **no** mueve nada.
  - Si dos archivos distintos se llaman igual, se agrega al nombre un sufijo con parte del hash.
- **Sin repetidos dentro de un puesto:** la clave es SHA-256 + puesto.
  - Si se sube un archivo que ya está en ese puesto, se omite y se informa dónde está, quién lo subió y
    cuándo.
  - El mismo archivo en **otro** puesto crea una **nueva postulación** de la misma persona.
- **Identificar a la misma persona:**
  - Un mismo archivo, o el mismo documento o email, enlaza automáticamente a la persona existente. El
    enlace queda en la bitácora.
  - Si solo coinciden el teléfono o el nombre completo, se marca **"posible misma persona"**. Es un aviso
    con el botón "Unir", no un bloqueo.
  - Si la persona ya fue contratada en otro puesto, sus demás postulaciones lo muestran.
- **Eliminar un CV:**
  - Borra el archivo del servidor y la postulación (decisiones, chat). Si la persona no tiene otras
    postulaciones, también borra sus datos personales: así se cumple una solicitud de eliminación.
  - El hash queda en `deleted_cv_hashes`. La sincronización y la revisión del servidor lo informan como
    "eliminado previamente" en vez de volver a subirlo.
  - La bitácora conserva un resumen: nombre, puesto, quién lo borró y cuándo.
  - Rechazar a un candidato **no** borra nada.
- **Formatos:** PDF, DOCX, TXT y RTF, hasta 15 MB. Se rechazan DOC antiguos e imágenes (no hay OCR en esta
  versión). Un PDF sin texto queda en estado `Sin texto`.
- **Formas de cargar CVs:**
  1. **Subir desde la app:** se elige puesto, fuente y (si hay varios abiertos) requerimiento, y luego uno
     o varios archivos.
  2. **Importar carpeta:** se elige una carpeta con la estructura `puesto/fuente/archivos`; acepta tanto la
     carpeta `rrhh` como su contenido. Es una carga única.
  3. **Sincronizar la carpeta de la PC:** se configura una vez y se ejecuta al abrir la app y con
     "Sincronizar ahora". Usa la misma lógica que la importación.
  4. **Carpeta del servidor:** el worker la revisa cada 5 min y registra los archivos que alguien copió
     directamente.
- **Cómo se sincroniza la carpeta de la PC:**
  1. Un comando Rust (`scan_cv_folder`) recorre la carpeta y calcula el SHA-256 de cada archivo.
  2. La app pregunta al servidor qué hashes ya existen (`POST /api/cv-files/check`).
  3. Relaciona los nombres de carpeta con puestos y fuentes, ignorando mayúsculas y acentos.
  4. Sube los nuevos de a 3 a la vez.
  5. Muestra un resumen: nuevos, repetidos, carpetas que no coinciden con ningún puesto o fuente,
     formatos no soportados y errores.
  - Botón **"Crear estructura de carpetas"** en la carpeta local: crea `puesto/fuente` para los puestos que
    tienen requerimientos abiertos.
- **Asignación al requerimiento:** si el puesto tiene **un** requerimiento abierto, el CV se asigna a ese.
  Si tiene varios, al más antiguo (o al que se eligió al subir). Si no tiene ninguno, el candidato queda
  en la cartera del puesto sin requerimiento.
- **Al subir un CV**, en la misma petición:
  1. Se extrae el texto.
  2. Se ejecuta el **lector por reglas** (port de `cvParser.ts`) y el **puntaje preliminar** (port de
     `recruitment.ts`). Así el candidato aparece de inmediato con datos básicos.
  3. El candidato queda `En cola` para la IA.

---

## 6. Clasificación con IA (OpenRouter, modelos gratuitos)

- **Cliente:** `POST https://openrouter.ai/api/v1/chat/completions` con la clave de `.env`
  (`OPENROUTER_API_KEY`).
  - El modelo y los modelos de respaldo se eligen en **Configuración** desde la lista de modelos gratuitos,
    que el servidor obtiene de `GET /api/v1/models` filtrando los de precio 0.
  - El modelo por defecto se escoge durante la implementación, según la lista vigente ese día.
- **Qué recibe el modelo:**
  - El perfil del puesto y el contexto del requerimiento.
  - **Los criterios aprendidos de su área**: las correcciones del jefe primero, con el supuesto que se
    corrigió. Así las correcciones de RR.HH. llegan de verdad a la IA, como instrucciones.
  - El texto del CV, recortado a unos 12.000 caracteres.
- **Qué debe devolver: un JSON con:**
  - datos personales;
  - formación;
  - experiencia (años, resumen y empleos);
  - certificaciones, licencias e idiomas;
  - puntajes técnico, experiencia y formación (0-100);
  - puntaje de aptitud (0-100);
  - **veredicto** `Pre-aprobado` / `Pre-denegado`;
  - fortalezas, observaciones, motivo y los criterios que aplicó.

  Se pide `response_format: json_object`, se valida con Pydantic y, si el JSON viene mal, se reintenta una
  vez pidiendo la corrección. Si vuelve a fallar, queda en `Error IA`.
- **Veredicto final:** solo queda `Pre-aprobado` si el modelo dice Pre-aprobado **y** el puntaje de
  aptitud es mayor o igual al **umbral** (configurable, 70 por defecto). En cualquier otro caso queda
  `Pre-denegado`.
  - El umbral se incluye en el prompt.
  - El modelo puede denegar aunque el puntaje sea alto si falta un requisito excluyente, por ejemplo una
    licencia.
  - Los candidatos `Sin IA` **no tienen veredicto** y no cuentan para el % de acuerdo.
- **Orden:** la bandeja de selección se ordena por puntaje de aptitud (en empate, por Índice Global). La
  terna del informe ejecutivo, por Índice Global.
- **Los datos personales que extrae la IA** completan o corrigen los de la persona (prioridad: lo que
  editó un usuario > IA > reglas). Cada postulación guarda su propio resultado de IA.
- **Índice Global:** se mantiene la fórmula actual (30 % técnico, 25 % experiencia, 15 % formación y 30 %
  psicológico, con 64 provisional mientras no haya prueba) usando los puntajes que da el modelo. El bono
  por palabras clave solo se usa cuando no hay IA.
- **Worker:**
  - Toma de a uno los candidatos `En cola`, con `FOR UPDATE SKIP LOCKED`.
  - Hace **como máximo 15 por minuto**: el tope de OpenRouter es 20.
  - Si OpenRouter responde 429 por tope diario, **pausa la cola hasta las 00:00 UTC** (19:00 en Perú). La
    app muestra "Límite diario de IA alcanzado; se reanuda a las 19:00".
  - Si hay otros errores, reintenta con espera creciente hasta 3 veces y luego deja el candidato en
    `Error IA`.
  - Cada clasificación queda en la bitácora con el usuario "Sistema (IA)" y el modelo usado.
- **Reclasificar:** hay botones "Reclasificar con IA" (un candidato) y "Reclasificar puesto" (todos los del
  puesto). **No** se reclasifica automáticamente al cambiar un criterio, para no gastar el cupo diario.
  Este cambio de comportamiento respecto a la app actual queda documentado.
- **Informe IA, chat y votos** (`evaluate-candidate`, `assistant-chat`, `vote-response`):
  - Llaman a OpenRouter en el momento, sin pasar por la cola, y consumen el mismo cupo.
  - Si OpenRouter falla, la pantalla muestra el error.
  - "Retroalimentar" con una nota crea un criterio, igual que hoy.
- **Sin clave o con la IA desactivada:** los candidatos quedan `Sin IA`, con datos y puntaje por reglas, y
  la app sigue funcionando.

---

## 7. Autenticación y bitácora

- **Registro** con `POST /api/auth/register` (nombre, email, contraseña de al menos 8 caracteres y
  cargo).
  - Lo controla la variable `REGISTRATION_MODE` del `.env`:
    - `open`: cualquiera se registra. Es el valor por defecto en local.
    - `invite`: el registro pide el código `INVITE_CODE`. **Se recomienda para el servidor real.**
  - Para desactivar o reactivar cuentas hay un comando de servidor:
    `python -m app.cli users deactivate <email>`. **Ingreso** con `POST /api/auth/login`, que devuelve un JWT HS256 válido
  por 12 h. `GET /api/auth/me` devuelve el usuario actual.
- **Todas** las demás rutas exigen `Authorization: Bearer`, incluidas las descargas. Un 401 lleva a la
  pantalla de ingreso.
- **Quién firma:** "evaluado por" y "subido por" salen del usuario con sesión iniciada. Ya no se usa el
  nombre fijo "Elena Vargas".
- **La bitácora registra:**
  - ingresos, ingresos fallidos y registros de cuentas;
  - **toda** acción que modifica datos;
  - descargas de CVs, informes y respaldos, porque contienen datos personales;
  - acciones del sistema: clasificación de la IA, requerimiento cubierto, archivos detectados en la
    carpeta del servidor.
- Cada entrada tiene un resumen legible, por ejemplo "Aprobó a Juan Pérez Quispe para Perforista
  (Requerimiento #12)".
- **Pantalla Bitácora:** filtros por usuario, acción, entidad, rango de fechas y texto, y exportación a
  CSV. La ficha del candidato muestra su historial.

---

## 8. API (grupos de rutas)

Todo va con JSON en camelCase. Las rutas que modifican datos devuelven `{ state }`, la foto actualizada,
como hoy.

| Grupo | Rutas |
|---|---|
| Salud | `GET /api/health` (sin sesión) |
| Auth | `POST /api/auth/register`, `POST /api/auth/login`, `GET /api/auth/me`, `GET /api/users` |
| Foto | `GET /api/state` → `AppStatePayload` ampliado (ver abajo) |
| Organigrama | `POST /api/positions`, `PATCH /api/positions/{id}` (incluye mover de padre, sin permitir ciclos), `DELETE /api/positions/{id}` (solo si no tiene hijos, requerimientos ni candidatos) |
| Fuentes | `POST/PATCH /api/sources`, `POST /api/sources/{id}/proposals` (reemplaza `job-boards/send`) |
| Requerimientos | `POST /api/requirements`, `PATCH /api/requirements/{id}` (cantidad, urgencia, cancelar) |
| CVs | `POST /api/cv-files/check` (hashes), `POST /api/cv-files` (multipart: archivo, puesto, fuente, requerimiento y origen; responde 409 si es repetido), `GET /api/cv-files/{id}/download`, `PATCH /api/cv-files/{id}` (reclasificar puesto o fuente: mueve el archivo), `DELETE /api/cv-files/{id}` |
| Personas | `PATCH /api/persons/{id}` (corregir datos personales), `POST /api/persons/{id}/merge` (unir con "posible misma persona") |
| Postulaciones | `POST /api/candidates` (alta manual sin CV: crea persona y postulación), `POST /api/candidates/{id}/decision` (decisión, nota, observación y, si se quiere, enseñar un criterio), `POST /api/candidates/{id}/reclassify` |
| Criterios | `GET/POST/PATCH /api/criteria` |
| IA | `POST /api/ai/evaluate-candidate`, `POST /api/ai/assistant-chat`, `POST /api/ai/vote-response`, `GET /api/ai/queue`, `POST /api/ai/queue/retry-errors`, `POST /api/positions/{id}/reclassify` |
| Pruebas (port) | `POST /api/recruitment/psych-tests/send`, `POST /api/recruitment/psych-tests/{id}/submit`, `POST /api/recruitment/tests`, `POST /api/recruitment/tests/import-excel`, `POST /api/recruitment/tests/upload-excel`, `DELETE /api/recruitment/tests/{id}`, `GET /api/tests/excel-template` |
| Informes (port) | `GET /api/reports/admin-doc`, `GET /api/reports/candidate/{id}/doc`, `GET /api/reports/candidates-csv`, `GET /api/reports/kpis-csv` |
| Bitácora | `GET /api/audit` (filtros, paginado), `GET /api/audit/export.csv` |
| Configuración | `GET/PATCH /api/settings`, `GET /api/settings/ai-models` |
| Respaldo | `GET /api/datacenter/status`, `GET /api/datacenter/backup` (JSON de los datos de negocio, sin archivos), `POST /api/datacenter/restore` (hay que escribir "RESTAURAR" para confirmar; queda en la bitácora). **La restauración reemplaza solo los datos de negocio:** organigrama, fuentes, requerimientos, personas, postulaciones, registros de archivos, criterios, pruebas, conversaciones y configuración. **Nunca toca usuarios ni bitácora**: el trigger impide UPDATE, DELETE y TRUNCATE en la bitácora. Si un registro del respaldo apunta a un archivo que ya no está en disco, se marca "archivo faltante". Si hay archivos en disco que no figuran en el respaldo, el worker los registra como nuevos y lo deja en la bitácora |

- **Rutas originales que se eliminan:**
  - `POST /api/state/reset`: los datos demo se cargan con un comando del servidor.
  - `/api/download/windows-installer` y `/api/download/datacenter-kit`: Tauri ya es el instalador.
  - `POST /api/ai/parse-cv`: ahora la lectura ocurre al subir el CV.
- **Foto (`AppStatePayload` ampliado):**
  - `companyName`, `currentUser`, `positions`, `requirements` (en forma compatible con `jobNeeds`, más
    `positionId`) y `jobBoards` (fuentes con conteos calculados).
  - `candidates`: una por postulación, versión liviana sin el texto del CV ni las filas del Excel. Trae
    los **datos de la persona incrustados**, igual que el `Candidate` actual, más `personId` y
    `otherApplications`, para que los módulos actuales sigan funcionando.
  - `recruitmentCriteria`, `testCatalog`, `aiConversations`, `kpis` (calculados en el servidor) y
    `aiQueue` (pendientes, en proceso, con error, pausada hasta).
  - El tipo vive en `rebuild/tauri/src/types.ts` y su espejo en los esquemas Pydantic.

---

## 9. App Tauri

**Pantallas** (el menú agrupa las secundarias; la distribución exacta la decide quien implemente):

- **Ingreso / Registro.** Desde aquí se accede a "Servidor" para cambiar la URL antes de entrar.
- **Candidatos:** el actual, adaptado. Hay una fila por postulación.
  - Muestra el veredicto de la IA, el estado en la cola y "posible misma persona".
  - La ficha muestra los datos de la persona (editables), sus **otras postulaciones** y su historial en la
    bitácora.
  - "Nuevo candidato" queda para altas manuales.
- **Organigrama** (nuevo):
  - Árbol plegable para editar, con una vista gráfica en CSS.
  - Por puesto: agregar subordinado, editar el perfil, mover a otro jefe, eliminar.
  - Cada nodo muestra sus requerimientos abiertos y la cantidad de candidatos.
- **Requerimientos y Selección:** el actual "Vacantes y Selección", adaptado.
  - El requerimiento se crea eligiendo un puesto del organigrama.
  - La bandeja se ordena por puntaje de la IA.
  - Decisión: Aprobar / Rechazar / Contratar.
  - Se mantienen la corrección de criterios, el informe y el chat de IA.
- **Carpeta de CVs** (nuevo):
  - Explorador `rrhh/puesto/fuente` con conteos.
  - Lista de archivos con candidato, estado de IA, veredicto, decisión, quién lo subió y cuándo.
  - Acciones: subir, importar carpeta, sincronizar, crear estructura local, ver CV, reclasificar,
    eliminar.
- **Pruebas y Resultados, Procesos KPI, Reportes:** portados. Bolsas pasan a ser fuentes; las vacantes,
  requerimientos.
- **Bitácora** (nuevo).
- **Configuración** (nuevo): URL del servidor (con "Probar conexión"), carpeta local de CVs, sincronizar
  al abrir, nombre de la empresa, modelo de IA y respaldos, umbral, estado de la cola y aviso del cupo
  gratuito.

**Cambios transversales a la UI copiada:**
- `src/api/client.ts`:
  - URL base guardada con `plugin-store`; token; `apiFetch` que agrega el `Bearer` y ante un 401 cierra
    la sesión.
  - `downloadFile(ruta, nombreSugerido)`: descarga con fetch, abre el diálogo "Guardar como" y guarda con
    el comando Rust `save_file`.
  - `openFile`: guarda en una carpeta temporal y abre con el programa predeterminado.
  - Los **19 enlaces `<a href="/api/...">`** pasan a usar estas funciones.
- `App.tsx`:
  - Agrega la sesión y refresca la foto cada 30 s.
  - Reemplaza `hrChiefName` por `currentUser`.
  - Quita "Restaurar datos demo", `AppInstallModal`, `usePWAInstall`, `vite-plugin-pwa` y
    `MobileBottomNav`.
  - `OfflineIndicator` pasa a indicar si hay conexión con el servidor.
- `types.ts`:
  - Nueva `CandidateDecision`: Pendiente de revisión / Aprobado / Rechazado / Contratado.
  - Nuevos tipos `AiVerdict`, `Position`, `Requirement` y `CvFile`.
  - Se ajustan los componentes que usaban "Preseleccionado", "En prueba práctica" o "No apto".
- **Rust (`src-tauri/src/lib.rs`):**
  - `scan_cv_folder(root)` devuelve puesto, fuente, ruta, tamaño y sha256 de cada archivo.
  - `read_file_bytes(path)`.
  - `save_file(path, bytes)`.
  - `create_folder_structure(root, carpetas)`.
- **CSP de Tauri:** `connect-src http: https:`, porque la URL del servidor se puede configurar.

---

## 10. Reglas portadas (TypeScript → Python) y correcciones

- `src/utils/recruitment.ts` pasa a `app/services/scoring.py`, `excel_tests.py` y `reports.py`.
  - `cvParser.ts` pasa a `cv_parser.py` y las funciones `stripRtfToText` y `stripHtmlToText`, a
    `text_extract.py`.
  - **Los 8 tests de `src/utils/recruitment.test.ts` se portan a pytest** como pruebas de aceptación del
    port.
- **Correcciones de los hallazgos del informe** que se aplican al portar:
  - **H-02:** los criterios se filtran por área.
  - **H-04:** el % de acuerdo se calcula de nuevo (ver la sección 4).
  - **H-05:** se quita la palabra clave "uni".
  - **H-06:** `passingScore` define si una prueba se aprueba.
  - **H-12:** los días de proceso se calculan desde la fecha de alta.
  - **H-03** deja de aplicar: con el flujo nuevo, la IA pre-aprueba por el CV y las pruebas vienen después
    de "Aprobado".

## 11. Datos demo

Se cargan con `docker compose exec api python -m app.seed --demo`, solo si la base está vacía.

- Empresa: "Compañía Minera Las Bravas".
- **Organigrama** de unos 25 puestos que cuelgan de Gerencia General:
  - Operaciones Mina
  - Planta
  - Seguridad HSEC
  - Mantenimiento
  - Geología y Planeamiento
  - Medio Ambiente y RR.CC.
  - Logística y Campamento
  - RR.HH.

  Incluye los 15 puestos de las vacantes actuales.
- **15 requerimientos** con las cantidades de `seedData.ts`.
- **6 fuentes:** `computrabajo`, `linkedin`, `bumeran`, `referidos-faena`, `portal-las-bravas`, `indeed`.
- Los 2 criterios actuales.
- Sin candidatos: llegan con los CVs. Para las pruebas hay **CVs ficticios** en `tests/fixtures`, marcados
  como ficticios.

## 12. Estructura de archivos

```
rebuild/
  docs/            diseno-rebuild.md (este diseño), README.md (cómo levantar y compilar)
  fastapi/
    docker-compose.yml  Dockerfile  .env.example  pyproject.toml  alembic.ini  alembic/
    app/  main.py config.py db.py models/ schemas/ auth/ audit.py routers/ services/ worker.py seed.py
    tests/  (pytest + fixtures con CVs ficticios)
    data/rrhh/  (carpeta de CVs del servidor; fuera del control de versiones)
  tauri/
    package.json vite.config.ts tsconfig.json index.html
    src/  (copia adaptada de ../../src + api/ auth/ y módulos nuevos)
    src-tauri/  Cargo.toml tauri.conf.json capabilities/ src/lib.rs src/main.rs icons/
```

## 13. Fases de implementación

Al aprobar el diseño, se arma un plan detallado con `superpowers:writing-plans` y luego se ejecuta.

1. **Base de la API:** compose (db, api, worker), modelos, Alembic, auth, bitácora con trigger,
   configuración y salud.
2. **Organigrama, fuentes, requerimientos y foto** (`/api/state`), más los datos demo.
3. **CVs:** almacenamiento `rrhh/`, subida, control de repetidos por puesto, personas y postulaciones
   (enlazar y unir), eliminación con hash bloqueado, extracción de texto, port del lector y del puntaje
   por reglas, revisión de la carpeta del servidor.
4. **IA:** cliente OpenRouter, worker con tope y pausa, clasificador, informe, chat, votos y criterios.
5. **Port de pruebas Excel, informes, KPIs y respaldo.**
6. **Base de la app Tauri:** proyecto, cliente de API, sesión, descargas, copia de la UI y nuevos tipos.
7. **Módulos nuevos y adaptados:** organigrama, carpeta de CVs (con sincronización en Rust), requerimientos
   y selección, bitácora, configuración.
8. **Verificación de punta a punta, instalador y README.**

## 14. Verificación

- **API:** `docker compose up -d --build`, luego `docker compose run --rm api pytest`, que usa una base de
  prueba. Se prueba:
  - Auth: un 401 sin token.
  - La bitácora: cada acción deja su entrada, y UPDATE o DELETE fallan.
  - Repetidos:
    - El mismo archivo dos veces en el mismo puesto devuelve 409.
    - En otro puesto crea una nueva postulación de la misma persona.
    - Un archivo eliminado no se reimporta.
  - La restauración no toca usuarios ni bitácora.
  - Rutas de carpeta y movimiento de archivos.
  - Organigrama: no permite ciclos y respeta las restricciones para borrar.
  - Cobertura: "Contratado" llena una plaza y el requerimiento pasa solo a Cubierto.
  - Las transiciones de decisión.
  - El clasificador **con OpenRouter simulado** (`respx`): JSON válido, JSON mal formado con reintento,
    y 429 por tope diario con pausa.
  - La forma de la foto.
  - Los 8 tests portados, las pruebas Excel y los informes.
- **App:** `npm run build` (TypeScript + Vite), tests con vitest de la relación carpeta↔puesto y del plan
  de sincronización, y `npm run tauri build`, que genera el instalador NSIS.
- **De punta a punta, manual con `npm run tauri dev` contra la API local:**
  1. Registrar dos usuarios.
  2. Cargar datos demo.
  3. Crear un puesto y un requerimiento.
  4. Subir un CV por la app y comprobar que el repetido se rechaza.
  5. Sincronizar una carpeta local de prueba.
  6. Ver la clasificación con la **clave real de OpenRouter**, que el usuario pone en `.env`.
  7. Aprobar con el usuario A y contratar con el usuario B.
  8. Revisar en la bitácora las acciones de ambos.
  9. Descargar informes y el CV.
  10. Probar el instalador.

## 15. Riesgos y avisos

- **Cupo gratuito de OpenRouter** (según la documentación y fuentes públicas a noviembre de 2026):
  - 20 solicitudes por minuto.
  - **50 por día** si la cuenta compró menos de USD 10 en créditos; **1.000 por día** si compró al menos
    USD 10 en total.
  - Cada CV usa una solicitud, igual que cada mensaje del chat o informe.
  - La cola lo maneja, pero 200 CVs pueden tardar 4 días con el cupo de 50.
- **Privacidad:** varios proveedores de modelos gratuitos pueden registrar las consultas o usarlas para
  entrenar. Los CVs tienen datos personales (Ley 29733 del Perú). Conviene ajustar la privacidad en la
  cuenta de OpenRouter.
- Los modelos gratuitos cambian o desaparecen; por eso el modelo y sus respaldos se configuran.
- **Datos compartidos sin roles:** cualquiera puede restaurar un respaldo y borrar todo. Para mitigarlo se
  exige confirmación escrita y queda en la bitácora.
- La foto crece con el volumen; está fuera del alcance de esta versión (enfoque B a futuro).
- Los PDFs escaneados no se leen: no hay OCR.

## 16. Decisiones del constructor (tomadas por Claude, revisables)

- PostgreSQL en lugar de SQLite.
- Worker como servicio aparte.
- Un JWT de 12 h, sin token de renovación.
- argon2 para las contraseñas.
- Multipart en lugar de base64 para los archivos.
- Lectura de la carpeta local en Rust.
- CORS en lugar del plugin HTTP de Tauri.
- Nombre de carpeta fijo al crear el puesto.
- Asignación automática al requerimiento abierto más antiguo.
- Aviso de "posible duplicado" sin bloquear.
- No reclasificar automáticamente al cambiar criterios.
- Las pruebas Excel siguen evaluándose por reglas, sin gastar cupo de IA.
- Datos demo por comando, no con un botón.
- Instalador NSIS solo para Windows.
- Nombre de la empresa configurable.
- **Tomadas a partir de la revisión del diseño:**
  - **Borrar un CV:** elimina el archivo y los datos, y deja el hash bloqueado para que no se reimporte.
  - **Restaurar un respaldo:** solo reemplaza los datos de negocio; usuarios y bitácora nunca se tocan.
  - **Veredicto:** solo es Pre-aprobado si lo dice el modelo y el puntaje supera el umbral.
  - **Registro de cuentas:** se controla con `REGISTRATION_MODE` (open en local, invite en el servidor
    real) y hay un comando para desactivar cuentas.
  - **Pruebas psicológicas y Excel:** son de la persona y valen para todas sus postulaciones.
  - **Deshacer una contratación:** vuelve a abrir el requerimiento si quedó cubierto.
  - **Límite de OpenRouter:** el 429 por minuto y el 429 diario se distinguen por el mensaje y las
    cabeceras de la respuesta.
- **Siguiente paso tras aprobar:** se guarda este diseño en `rebuild/docs/diseno-rebuild.md` y se escribe
  el plan detallado de implementación con `superpowers:writing-plans`.
