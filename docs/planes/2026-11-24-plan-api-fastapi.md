# API FastAPI de Pulso Laboral — Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Construir en `rebuild/fastapi` la API que reemplaza al servidor perdido. Se levanta con Docker Compose e incluye cuentas, organigrama, requerimientos, carpeta de CVs `rrhh/<puesto>/<fuente>`, personas y postulaciones, clasificación con OpenRouter en cola, decisiones humanas, bitácora inmutable, pruebas, informes y respaldo.

**Architecture:** Tres servicios en Docker Compose:
- `db`: PostgreSQL 16.
- `api`: FastAPI con SQLAlchemy 2 síncrono.
- `worker`: la misma imagen; procesa la cola de IA y revisa la carpeta del servidor.

Las rutas de datos están organizadas por recurso. Cada ruta que modifica datos devuelve la "foto" completa (`{state}`) que consume la app. Las reglas del frontend original (`src/utils/recruitment.ts`, `src/utils/cvParser.ts`) se portan a funciones puras de Python.

**Tech Stack:** Python 3.12, FastAPI, Uvicorn, SQLAlchemy 2 + psycopg 3, Alembic, Pydantic v2 + pydantic-settings, PyJWT, pwdlib[argon2], python-multipart, httpx, pypdf, python-docx, openpyxl. Para pruebas: pytest, respx y fpdf2.

**Spec:** `rebuild/docs/diseno-rebuild.md`. El plan de la app, `rebuild/docs/planes/2026-11-24-plan-app-tauri.md`, consume el **Contrato de la foto** definido aquí.

## Global Constraints

- Todo el código nuevo va en `rebuild/`. No se modifica `src/` ni ningún otro archivo del proyecto original.
- **Control de versiones:** si el usuario lo aprobó, `rebuild/` se inicializa como repositorio git en la Tarea 1 y se hace un commit al final de cada tarea. Si no lo aprobó, se omiten los pasos "Commit".
- Imagen `python:3.12-slim`, PostgreSQL `postgres:16-alpine`, API en el puerto `8000`.
- **Comandos:** se ejecutan desde `rebuild/fastapi`. Las pruebas corren con `docker compose run --rm api pytest <ruta> -v`; el `docker-compose.override.yml` monta el código y define `TEST_DATABASE_URL`.
- **JSON:** todo en camelCase, con `alias_generator=to_camel` y `populate_by_name=True`. Los IDs son UUID v4 en forma de string.
- **Autenticación:**
  - Todas las rutas van bajo `/api` y exigen `Authorization: Bearer <JWT>`, salvo `GET /api/health`, `POST /api/auth/register` y `POST /api/auth/login`.
  - JWT HS256 válido por 12 h y contraseñas de al menos 8 caracteres.
  - `REGISTRATION_MODE=open|invite` (por defecto `open`) e `INVITE_CODE`.
- **Respuestas:** toda ruta que modifica datos devuelve `{"state": build_state(...)}`, más los campos propios que indique su tarea.
- **Bitácora:** cada modificación, registro de cuenta, ingreso, ingreso fallido y descarga (de CV, informe, respaldo o bitácora) inserta una fila en `audit_log` **en la misma transacción**. Un trigger impide UPDATE, DELETE y TRUNCATE en esa tabla.
- **Idioma:** los mensajes de error y los resúmenes de la bitácora van en español, con tildes.
- **Constantes** (`app/constants.py`; copiar los textos exactos):
  - `AI_STATUSES = ('En cola','Procesando','Clasificado','Error IA','Sin texto','Sin IA')`
  - `AI_VERDICTS = ('Pre-aprobado','Pre-denegado')`
  - `DECISIONS = ('Pendiente de revisión','Aprobado','Rechazado','Contratado')`
  - `DECISION_TRANSITIONS = {'Pendiente de revisión': {'Aprobado','Rechazado'}, 'Aprobado': {'Contratado','Rechazado'}, 'Rechazado': {'Aprobado'}, 'Contratado': {'Aprobado','Rechazado'}}`
  - `REQUIREMENT_STATUSES = ('Abierto','Cubierto','Cancelado')`
  - `URGENCIES = ('Urgente','Media','Planificada')`
  - `SOURCE_CATEGORIES = ('Portal Minero','Red Profesional','Bolsa Nacional','Referidos Faena')`
  - `TEST_CATEGORIES = ('Psicolaboral','Técnica Minera','Seguridad HSEC','Operación / Maquinaria')`
  - `CV_ORIGINS = ('app','importacion','sync_local','carpeta_servidor')`
  - `ALL_AREAS = 'Todas las áreas'`
  - `SYSTEM_ACTOR = 'Sistema'`
  - `AI_ACTOR = 'Sistema (IA)'`
  - `ALLOWED_CV_EXTENSIONS = ('.pdf','.docx','.txt','.rtf')`
  - `MAX_CV_BYTES = 15 * 1024 * 1024`
  - `CV_TEXT_LIMIT = 12000`
- **Índice Global:** `round(0.30·técnico + 0.25·experiencia + 0.15·formación + 0.30·psicológico + bono)`, acotado a 30-98.
  - Psicológico = promedio de la persona si su evaluación está `Completada`; si no, 64.
  - El bono solo existe cuando no hay IA (máx. 10).
  - `fitVerdict`: ≥85 `'Idoneidad Alta para el Puesto'`, ≥72 `'Idoneidad Sólida (Apto)'`, si no `'Requiere Validación Adicional'`.
- **Umbral de pre-aprobación:** 70 por defecto. Veredicto final `'Pre-aprobado'` solo si el modelo dice Pre-aprobado **y** `puntajeAptitud >= umbral`.
- **Worker:**
  - Máximo 15 clasificaciones por minuto (`WORKER_RATE_PER_MINUTE=15`) y 3 intentos.
  - Espera entre reintentos de `30·2^intentos` s.
  - Pausa hasta el reinicio diario de OpenRouter cuando recibe un 429 diario.
  - Revisa la carpeta del servidor cada 300 s.
- **Carpeta de CVs del servidor:** `RRHH_ROOT=/data/rrhh`, montada desde `./data/rrhh`. Las rutas guardadas son relativas a esa raíz: `<puesto.folder_name>/<fuente.folder_name>/<archivo>`.

## Contrato de la foto (`GET /api/state`)

Esta forma la consume la app y su espejo es `rebuild/tauri/src/types.ts`. Las tareas que agregan datos completan los campos que les tocan. **Los nombres no se pueden cambiar.**

```ts
AppState = {
  catalogVersion: 4; companyName: string;
  hrChiefName: string; hrChiefTitle: string;            // = currentUser.fullName / jobTitle (compatibilidad)
  currentUser: { id; fullName; email; jobTitle; isActive };
  settings: { companyName; aiModel; aiFallbackModels: string[]; aiPreapproveThreshold: number; aiEnabled: boolean; aiConfigured: boolean };
  aiQueue: { queued; processing; errors; sinIa; pausedUntil: string|null; aiEnabled: boolean; model: string };
  positions: { id; name; folderName; area; parentId: string|null; description; requiredSkills; technicalSpecifications;
               minYearsExperience: number; educationProfile; sortOrder: number; openRequirementsCount; candidatesCount }[];
  jobNeeds: { id; positionId; title /*= puesto.name*/; department /*= puesto.area*/; urgency; vacancies /*= quantity*/;
              filledCount /*= nº Contratado*/; requiredSkills /*puesto + extraSkills*/; technicalSpecifications; companyContext;
              publishedBoards: string[] /*nombres*/; publishedSourceIds: string[]; openedAt; targetDaysToFill; createdBy;
              status: 'Abierto'|'Cubierto'|'Cancelado'; extraSkills }[];
  jobBoards: { id; name; folderName; category; proposalsSent; candidatesReceived; shortlistedCount /*Aprobado+Contratado*/;
               hiredCount; avgResponseHours; lastProposalAt: string|null; active }[];
  candidates: Candidate[];           // una por postulación
  blockedCvFiles: { id; sha256; positionId; originalName; deletedBy; deletedAt }[];
  recruitmentCriteria: { id; title; appliesToDepartment; weightLabel; ruleText; isCorrection; wrongAiAssumption?;
                         learnedFromCandidate?; createdBy; createdAt; updatedAt }[];
  testCatalog: TestDefinition[];     // mismos campos que src/types.ts:113-128
  aiConversations: AiReportConversation[];  // mismos campos que src/types.ts:130-152
  kpis: RecruitmentKPIs;             // mismos campos que src/types.ts:203-217 (preselectedOrHired = Aprobado+Contratado)
}
Candidate = {
  id; personId; cvFileId: string|null; positionId; requirementId: string|null; targetNeedId /*requirementId ?? ''*/;
  targetRoleTitle; sourceBoardId; sourceBoardName;
  fullName; firstNames; lastNames; documentId; email; phone; phoneOrEmail /*"email · teléfono"*/; age: number|null;
  originLocation; university; career; yearsWorked: number|null; workHistorySummary; specifications: string[];
  languages: string[]; licenses: string[]; interviewNotes;
  cvFileName?; cvMimeType?; cvUploadedAt?; cvUploadedBy?; cvOrigin?; cvPath?; cvMissing: boolean;
  psychEvaluation: PsychEvaluation /*de la persona; src/types.ts:33-45*/;
  excelTestResults: (ExcelTestResult & { passingScore: number|null; passed: boolean|null })[] /*parsedRows: []*/;
  metricReport: CandidateMetricReport /*src/types.ts:47-56*/;
  aiStatus; aiVerdict: 'Pre-aprobado'|'Pre-denegado'|null; aiAptitudeScore: number|null; aiStrengths: string[];
  aiObservations: string[]; aiReason; aiAppliedCriteria: string[]; aiAppliedCorrectionTitle?; aiModel: string|null;
  aiClassifiedAt: string|null; aiError: string|null; aiSummary; aiObservedScore /*= metricReport.overallScore*/;
  decision; managerScore: number|null; managerNotes; evaluatedBy?; evaluatedAt?;
  possibleSamePersonIds: string[]; otherApplications: { candidateId; positionName; decision }[];
  processDaysElapsed /*días desde createdAt*/; createdAt;
}
```

## Review Focus

1. **Nombres de archivo con tildes, espacios, paréntesis o `../`** (por ejemplo `CV José Ñuñez (1).pdf`): deben guardarse dentro de la raíz con un nombre seguro y descargarse con el nombre original. → Tarea 4 (`test_storage_safe_paths`) y Tarea 5 (`test_unicode_filename_roundtrip`).
2. **PDF dañado, cifrado o escaneado:** nunca debe dar un 500. Queda `Sin texto` o se rechaza con un mensaje claro. → Tarea 3 (`test_extract_text_bad_inputs`) y Tarea 5 (`test_scanned_pdf_sin_texto`).
3. **Respuesta del modelo desprolija:** JSON dentro de bloques ```` ``` ````, texto alrededor, números como string o un veredicto escrito distinto (`'preaprobado'`). Debe interpretarse y normalizarse. → Tarea 7 (`test_extract_json_object_handles_fences_and_prose` y `test_classification_normalizes_scores_and_verdict`).
4. **El worker se cae a mitad de una clasificación:** el candidato no debe quedar para siempre en `Procesando`. → Tarea 7 (`test_recover_stuck_processing`).
5. **Email con mayúsculas al registrarse o ingresar** (`Ana@Mina.pe` frente a `ana@mina.pe`): debe ser la misma cuenta. → Tarea 2 (`test_register_duplicate_email_case_insensitive` y `test_login_ok_and_failed_logged`).

## Estructura de archivos

```
rebuild/.gitignore                      (data/, .env, node_modules/, target/, __pycache__/)
rebuild/fastapi/
  Dockerfile  docker-compose.yml  docker-compose.override.yml  .env.example  pyproject.toml  alembic.ini
  docker/initdb/01-test-db.sql          CREATE DATABASE pulso_test;
  alembic/env.py  alembic/versions/000N_*.py   (una migración por tarea que agrega tablas)
  app/main.py config.py db.py constants.py security.py deps.py audit.py cli.py seed.py worker.py
  app/models/   user.py audit.py org.py settings.py people.py criteria.py ai.py tests_module.py
  app/schemas/  common.py auth.py org.py people.py ai.py tests_module.py
  app/routers/  health.py auth.py users.py state.py positions.py sources.py requirements.py settings.py
                cv_files.py persons.py candidates.py criteria.py ai_queue.py ai_chat.py tests_module.py
                reports.py audit.py datacenter.py
  app/services/ slugs.py storage.py text_extract.py cv_parser.py scoring.py excel_tests.py snapshot.py
                app_settings.py ingest.py persons.py decisions.py openrouter.py classifier.py
                server_scan.py ai_chat.py reports.py datacenter.py
  tests/conftest.py  tests/fixtures/{legacy.py,cvs.py}  tests/test_*.py
```

---

### Task 1: Esqueleto, Docker Compose, base de datos y arnés de pruebas

**Files:**
- Create: `rebuild/.gitignore`, `rebuild/fastapi/{Dockerfile,docker-compose.yml,docker-compose.override.yml,.env.example,pyproject.toml,alembic.ini}`, `docker/initdb/01-test-db.sql`, `alembic/env.py`, `app/{__init__,main,config,db,constants}.py`, `app/routers/health.py`
- Test: `tests/conftest.py`, `tests/test_health.py`

**Interfaces:**
- Produces:
  - `create_app() -> FastAPI` y `app = create_app()` en `app/main.py`. Incluye los routers bajo `/api` y CORS desde `settings.cors_origins`.
  - `Settings(BaseSettings)` y `get_settings() -> Settings` (con `lru_cache`). Campos:
    - `database_url`, `test_database_url=''`
    - `jwt_secret`, `jwt_expire_hours=12`
    - `registration_mode='open'`, `invite_code=''`
    - `cors_origins=['http://tauri.localhost','tauri://localhost','http://localhost:1420']`
    - `rrhh_root=Path('/data/rrhh')`
    - `openrouter_api_key=''`, `openrouter_base_url='https://openrouter.ai/api/v1'`
    - `worker_rate_per_minute=15`, `server_scan_interval_s=300`
    - `company_name_default='Compañía Minera Las Bravas'`
  - En `app/db.py`: `Base(DeclarativeBase)`, `engine`, `SessionLocal` y `get_db() -> Iterator[Session]`.
  - Fixtures de `conftest.py`:
    - `db`: una Session dentro de una transacción externa (`join_transaction_mode="create_savepoint"`) que se revierte al final de cada prueba; además sobrescribe `get_db`.
    - `client`: un `TestClient`.
    - `settings_override(**kw)`: context manager que parchea `get_settings()`.
    - `rrhh_root`: un `tmp_path` asignado a `settings.rrhh_root`.
  - Antes de la sesión de pruebas, `conftest` ejecuta `DROP SCHEMA public CASCADE; CREATE SCHEMA public` y `alembic upgrade head` contra `TEST_DATABASE_URL`.

- [ ] **Step 1: Escribir la prueba que falla.** `test_health_reports_db`: `r = client.get('/api/health')` → `r.status_code == 200` y `r.json() == {'status': 'ok', 'database': 'ok'}`.
- [ ] **Step 2: Comprobar que falla.** Ejecutar `docker compose run --rm api pytest tests/test_health.py -v`. Se espera un FAIL por error de importación o de compilación.
- [ ] **Step 3: Implementar.**
  - `docker-compose.yml`:
    - `db`: healthcheck con `pg_isready`, volumen `pgdata` y montaje de `./docker/initdb` en `/docker-entrypoint-initdb.d`.
    - `api`: ejecuta `sh -c "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"`, con `env_file: .env`, `./data/rrhh:/data/rrhh`, `depends_on: db (service_healthy)` y healthcheck sobre `/api/health`.
    - `worker`: ejecuta `python -m app.worker`, con los mismos volúmenes y `env_file`, y `depends_on: api (service_healthy)`.
  - `docker-compose.override.yml`: monta `.:/srv`, usa `--reload` y define `TEST_DATABASE_URL=postgresql+psycopg://pulso:pulso@db:5432/pulso_test`.
  - `.env.example`: incluye todas las variables de Settings con valores locales y `OPENROUTER_API_KEY=` vacía.
  - `/api/health` ejecuta `SELECT 1`.
- [ ] **Step 4: Verificar.**
  - El mismo comando del Step 2 da PASS.
  - `docker compose up -d --build` y luego `curl http://localhost:8000/api/health` devuelve `{"status":"ok","database":"ok"}`.
- [ ] **Step 5: Commit.** Si se aprobó git, ejecutar primero `git init` en `rebuild/`. Luego `git add -A && git commit -m "feat(api): esqueleto FastAPI con docker compose y arnés de pruebas"`.

### Task 2: Cuentas, autenticación y bitácora inmutable

**Files:**
- Create: `app/models/{user,audit}.py`, `alembic/versions/0002_users_audit.py`, `app/{security,deps,audit,cli}.py`, `app/schemas/{common,auth}.py`, `app/routers/{auth,users}.py`
- Test: `tests/test_auth.py`, `tests/test_audit_log.py`. En `conftest.py` se agrega `make_user(email='ana@mina.pe', full_name='Ana Torres', job_title='Jefe de RR.HH.') -> tuple[User, dict]`, que devuelve el usuario y sus headers.

**Interfaces:**
- Produces:
  - `User`: `id`, `full_name`, `email` (único, se guarda en minúsculas), `password_hash`, `job_title`, `is_active=True`, `created_at`, `last_login_at`.
  - `AuditLog`: `id` (bigint identity), `at` (timestamptz, por defecto `now()`), `user_id` (`str|None`, **sin FK con cascade**), `user_name`, `action`, `entity_type`, `entity_id` (`str|None`), `summary`, `details` (JSONB, `None` si no hay), `ip` (`str|None`).
  - En `security.py`: `hash_password(pw: str) -> str`, `verify_password(pw: str, h: str) -> bool`, `create_access_token(user_id: str) -> str` y `decode_access_token(token: str) -> str` (lanza `InvalidToken`).
  - En `deps.py`:
    - `get_current_user(...) -> User`. Responde 401 con `'Sesión inválida o vencida'` si falta el token, es inválido o la cuenta está inactiva.
    - `CurrentUser = Annotated[User, Depends(get_current_user)]`.
    - `client_ip(request: Request) -> str | None`.
  - En `audit.py`: `log_action(db, *, actor: User | str | None, action: str, entity_type: str, summary: str, entity_id: str | None = None, details: dict | None = None, ip: str | None = None) -> AuditLog`.
  - `UserOut {id, fullName, email, jobTitle, isActive}`.
  - Rutas:
    - `POST /api/auth/register {fullName, email, password, jobTitle, inviteCode?}` → 201 `{accessToken, user}`.
    - `POST /api/auth/login {email, password}` → `{accessToken, user}`.
    - `GET /api/auth/me` → `UserOut`.
    - `GET /api/users` → `UserOut[]`.
  - CLI: `python -m app.cli users deactivate|activate <email>`, con `main(argv: list[str]) -> int`.
  - Acciones que se registran en la bitácora: `auth.register`, `auth.login`, `auth.login_failed`, `user.deactivate` y `user.activate` (estas dos con actor `'Sistema'`).
- [ ] **Step 1: Escribir las pruebas que fallan.**
  - `test_register_returns_token_and_logs`: 201, `accessToken` presente y una fila de bitácora con `action='auth.register'`.
  - `test_register_duplicate_email_case_insensitive`: se registra `Ana@Mina.pe`; luego `ana@mina.pe` → 409 `'Ya existe una cuenta con ese email'`.
  - `test_login_ok_and_failed_logged`:
    - con contraseña incorrecta → 401 `'Email o contraseña incorrectos'` y bitácora `auth.login_failed`;
    - con `ANA@MINA.PE` y la contraseña correcta → 200 y bitácora `auth.login`.
  - `test_password_min_length`: contraseña de 7 caracteres → 422.
  - `test_invite_mode`: con `registration_mode='invite'` e `invite_code='X1'`:
    - sin código → 403 `'Código de invitación inválido'`;
    - con `'X1'` → 201.
  - `test_protected_requires_token`: `GET /api/users` sin header → 401; con un token basura → 401; con el token de un usuario desactivado → 401.
  - `test_audit_log_is_append_only`: después de `log_action(...)`, cada uno de `UPDATE audit_log SET summary='x'`, `DELETE FROM audit_log` y `TRUNCATE audit_log`, ejecutado dentro de `db.begin_nested()`, lanza `DBAPIError` con un mensaje que contiene `'solo de inserción'`.
  - `test_cli_deactivate`: `main(['users','deactivate','ana@mina.pe']) == 0`, `is_active` queda en False y hay bitácora `user.deactivate`.
- [ ] **Step 2: Comprobar que fallan.** `docker compose run --rm api pytest tests/test_auth.py tests/test_audit_log.py -v` → FAIL.
- [ ] **Step 3: Implementar.** La migración 0002 crea las tablas, la función `audit_log_block()` (`RAISE EXCEPTION 'audit_log es solo de inserción'`) y los triggers `BEFORE UPDATE OR DELETE … FOR EACH ROW` y `BEFORE TRUNCATE … FOR EACH STATEMENT`. Las contraseñas se hashean con argon2 vía `pwdlib`.
- [ ] **Step 4: Verificar.** El mismo comando da PASS.
- [ ] **Step 5: Commit.** `feat(api): cuentas, JWT y bitácora inmutable`.

### Task 3: Reglas portadas (funciones puras) y los tests originales

**Files:**
- Create: `app/services/{slugs,text_extract,cv_parser,scoring,excel_tests}.py`, `tests/fixtures/legacy.py`. Este último contiene los 15 puestos de `src/data/seedData.ts:13-286` como dicts `{id, name, area, requiredSkills, technicalSpecifications}`, las 6 bolsas con sus contadores sembrados y el candidato "Roberto Silva Huamán" de `seedData.ts:409-450`.
- Test: `tests/test_ported_rules.py`

**Interfaces** (sin base de datos; cada una es un port de la referencia indicada):
- `slugs.normalize_key(text: str) -> str`: descompone con NFD, quita las marcas diacríticas, pasa a minúsculas, reemplaza cada tramo de caracteres fuera de `[a-z0-9]` por `-` y recorta los `-` de los extremos.
- `slugs.folder_name_for(text: str) -> str`: `normalize_key` recortado a 80 caracteres.
- `text_extract.extract_text(data: bytes, filename: str) -> tuple[str, Literal['ok','empty','error']]`:
  - PDF con pypdf, DOCX con python-docx (párrafos y tablas), TXT en UTF-8 con respaldo latin-1, RTF.
  - `'empty'` si el texto limpio tiene menos de 40 caracteres; `'error'` ante cualquier excepción. **Nunca lanza.**
- `text_extract.strip_rtf_to_text(rtf: str) -> str` y `text_extract.strip_html_to_text(html: str) -> str`: ports de `cvParser.ts:112-156`.
- `cv_parser.ParsedCv` (dataclass): `full_name`, `first_names`, `last_names`, `age`, `origin_location`, `university`, `career`, `years_worked`, `work_history_summary`, `specifications: list[str]`, `email`, `phone`, `document_id`, `suggested_position_id`.
- `cv_parser.parse_cv_text(text: str, positions: list[dict]) -> ParsedCv`: port de `cvParser.ts:179-447` con estos cambios:
  - Recibe puestos en vez de vacantes.
  - El email y el teléfono van en campos separados.
  - `document_id` se obtiene con la regex `(?:DNI|D\.N\.I\.|CE|Carn[eé] de extranjer[ií]a)\s*[:N°º#.\s]*([0-9]{8,12})`.
  - Nombres y apellidos: con 4 palabras o más, las 2 últimas son apellidos; con menos, solo la última.
- `scoring.evaluate_psychometric_battery(scores: dict) -> dict`, con claves `averageScore`, `aptitudeLevel` y `aiPsychObservation`: port de `recruitment.ts:31-70`.
- `scoring.score_psych_answers(answers: dict) -> dict`: port de `recruitment.ts:76-93`.
- `scoring.compute_rule_scores(candidate: dict, position: dict, criteria: list[dict]) -> dict`: devuelve `{technical, experience, education, appliedCriteria: list[str], appliedCorrectionTitle: str|None, criteriaBonus: int}`. Es el port de `recruitment.ts:357-451` con dos correcciones:
  - **H-02:** solo se aplican los criterios con `appliesToDepartment in (position['area'], 'Todas las áreas')`.
  - **H-05:** se quita `'uni'` de las palabras clave de formación.
- `scoring.global_index(technical: int, experience: int, education: int, psych: float | None, bonus: int = 0) -> int`
- `scoring.fit_verdict(overall: int) -> str`
- `scoring.rule_report_text(candidate: dict, position: dict, scores: dict, overall: int) -> str`: port del texto de `recruitment.ts:475-485`.
- `scoring.compute_kpis(requirements: list[dict], sources: list[dict], candidates: list[dict]) -> dict`:
  - Devuelve los campos de `RecruitmentKPIs`.
  - **Acuerdo:** se cuentan los candidatos con `aiVerdict` no nulo y `decision != 'Pendiente de revisión'`. Hay acuerdo si el veredicto es Pre-aprobado y la decisión Aprobado o Contratado, o si el veredicto es Pre-denegado y la decisión Rechazado. Sin casos, 100.
- `excel_tests.extract_excel_test_metadata(rows: list[dict], file_name: str, sheet_name: str | None = None) -> dict`, con `detectedTestName`, `detectedCategory`, `detectedTargetArea` y `questions`: port de `recruitment.ts:95-194`.
- `excel_tests.evaluate_excel_test_rows(rows: list[dict], passing_score: int | None = None) -> dict`:
  - Devuelve `totalQuestions`, `answeredCount`, `autoComputedScore`, `isConcreteResult`, `concreteVerdict`, `parsedRows`, `derivedScores` (las 5 claves psicométricas), `passed` y `aiAnalysis`.
  - Es el port de `recruitment.ts:201-350`.
  - **H-06:** `passed = autoComputedScore >= passing_score` si se pasa `passing_score`; si no, `None`.
- [ ] **Step 1: Escribir las pruebas que fallan.** Usar los valores exactos de `src/utils/recruitment.test.ts`, salvo donde se indica otra cosa:
  - `test_psychometric_battery`: entradas 88/84/92/85/80 → `'Apto Recomendado'`, promedio ≥ 85 y la observación contiene `'Seguridad HSEC'`.
  - `test_psych_answers`: seguridad 5 → 98, equipo 4 → 86.
  - `test_rule_scores_apply_correction_of_same_area`:
    - Datos: Roberto Silva, el puesto "Operador de Planta Concentradora Senior" (área `'Control Metalúrgico'`) y el criterio del test TS, pero con `appliesToDepartment='Control Metalúrgico'`.
    - Se espera `global_index(..., bonus) >= 75` y `appliedCorrectionTitle == 'Priorizar experiencia en altura y planta concentradora'`.
    - `rule_report_text` contiene `'Apliqué la corrección del Jefe de RR.HH.'`.
  - `test_rule_scores_ignore_other_area_criteria` (H-02): con área `'Operaciones Mina'`, `appliedCriteria == []`; con `'Todas las áreas'`, se aplica.
  - `test_education_without_uni_keyword` (H-05): carrera `'Administración'` y universidad `'Universidad Privada del Sur'` → `education == 68`.
  - `test_kpis_top_board_and_agreement`:
    - Con las bolsas de `legacy`: `topBoardName == 'Computrabajo Minería'`, `topBoardCandidates == 42` y la cobertura entre 0 y 100.
    - Con los candidatos `[(Pre-aprobado, Aprobado), (Pre-aprobado, Rechazado), (None, Rechazado), (Pre-denegado, Pendiente de revisión)]`: `aiAgreementRate == 50`.
  - `test_excel_rows_concrete_vs_partial`: mismas filas que en TS → Concretos con `answeredCount == 4` y puntaje ≥ 85, y Parciales con `answeredCount == 1`. Además, con `passing_score=90` se espera `passed is True` y con 95, `passed is False`.
  - `test_excel_metadata_detection`: mismas filas → `'Examen Seguridad HSEC Tajo'`, `'Seguridad HSEC'` y 2 preguntas.
  - `test_parse_cv_peruvian_fields`: el mismo CV de ejemplo →
    - nombre `'Juan Carlos Mendoza Quispe'`, edad 34, procedencia `'Arequipa, Perú'`;
    - universidad que contiene `UNSA`, carrera que contiene `Minas`, 8 años;
    - `email == 'jcmendoza@mineria.pe'` y `'984 321 110' in phone`;
    - especificaciones con HSEC y A-IIIC;
    - `suggested_position_id` pertenece a los puestos de legacy.
    - Además, las aserciones RTF y HTML del test TS.
  - `test_normalize_key_vectors`:
    - `'Perforista y Cargador de Explosivos (Carnet SUCAMEC)' → 'perforista-y-cargador-de-explosivos-carnet-sucamec'`
    - `'  Operación   Mina ' → 'operacion-mina'`
    - `'LinkedIn' → 'linkedin'`
    - `'Referidos de Faena' → 'referidos-de-faena'`
  - `test_extract_text_bad_inputs`:
    - `b'%PDF-1.4 basura'` con `.pdf` → estado `'error'`, sin excepción;
    - un PDF de una página en blanco (generado con fpdf2) → `'empty'`;
    - un `.txt` en latin-1 con `'José Ñuñez'` → `'ok'` y el texto contiene `'José Ñuñez'`.
- [ ] **Step 2: Comprobar que fallan.** `docker compose run --rm api pytest tests/test_ported_rules.py -v` → FAIL.
- [ ] **Step 3: Implementar los ports**, leyendo las líneas citadas de `src/utils/*.ts` y respetando el redondeo de JavaScript.
  - Para el redondeo, usar `math.floor(x + 0.5)`, no `round()`, que redondea al par.
- [ ] **Step 4: Verificar.** El mismo comando da PASS.
- [ ] **Step 5: Commit.** `feat(api): port de reglas de puntuación, lector de CV y pruebas Excel`.

### Task 4: Organigrama, fuentes, requerimientos, configuración, almacenamiento y foto base

**Files:**
- Create: `app/models/{org,settings}.py`, `alembic/versions/0003_org.py`, `app/services/{storage,app_settings,snapshot}.py`, `app/schemas/org.py`, `app/routers/{positions,sources,requirements,settings,state}.py`
- Test: `tests/test_org.py`, `tests/test_storage.py`, `tests/test_state.py`

**Interfaces:**
- Produces:
  - `Position`: `id`, `name` (único), `folder_name` (único), `area`, `parent_id` (FK self, nullable), `description`, `required_skills`, `technical_specifications`, `min_years_experience=0`, `education_profile`, `sort_order=0`, `created_by_id`, `created_at`, `updated_at`.
  - `Source`: `id`, `name` (único), `folder_name` (único), `category`, `active=True`, `proposals_sent=0`, `avg_response_hours=0`, `last_proposal_at`.
  - `Requirement`: `id`, `position_id`, `quantity` (≥1), `urgency`, `target_days_to_fill=30`, `context`, `extra_skills`, `published_source_ids` (JSONB, `[]`), `status='Abierto'`, `opened_at`, `closed_at`, `created_by_id`, `created_by_name`.
  - `AppSettings` (una sola fila, `id=1`): `company_name`, `ai_model`, `ai_fallback_models` (JSONB), `ai_preapprove_threshold=70`, `ai_enabled=True`, `ai_paused_until` (nullable).
  - `app_settings.get_app_settings(db) -> AppSettings`: crea la fila si no existe.
  - `RrhhStorage(root: Path)`:
    - `safe_filename(name: str) -> str`: quita separadores de ruta, caracteres de control y `..`; conserva tildes y espacios; máximo 120 caracteres.
    - `save_bytes(position_folder: str, source_folder: str, filename: str, data: bytes, sha256: str) -> str`: devuelve la ruta relativa. Si el nombre ya existe, agrega el sufijo `-<sha256[:8]>` antes de la extensión.
    - `abs_path(rel: str) -> Path`: lanza `ValueError` si la ruta sale de la raíz.
    - `move(rel: str, position_folder: str, source_folder: str) -> str`
    - `delete(rel: str) -> None`
    - `rename_position_folder(old: str, new: str) -> None`
    - `iter_files() -> Iterator[tuple[str, str, str]]`: tuplas `(position_folder, source_folder, rel)`, solo a profundidad 3.
    - Dependencia `get_storage() -> RrhhStorage`.
  - `snapshot.build_state(db, user) -> dict`: devuelve **todas** las claves del contrato. Las colecciones que todavía no existen van vacías (`candidates=[]`, `blockedCvFiles=[]`, `testCatalog=[]`, `aiConversations=[]`).
  - `snapshot.state_response(db, user, **extra) -> dict`
  - Rutas (todas registran en la bitácora con `entity_type` `position`, `source`, `requirement` o `settings`):
    - `POST /api/positions {name, folderName?, area, parentId?, description?, requiredSkills?, technicalSpecifications?, minYearsExperience?, educationProfile?, sortOrder?}` → 201 `{position, state}`.
      - 409 `'Ya existe un puesto con ese nombre'` o `'Ya existe un puesto con esa carpeta'`.
    - `PATCH /api/positions/{id}` con los mismos campos.
      - Si `parentId` crea un ciclo → 422 `'No se puede mover un puesto debajo de sí mismo o de un subordinado'`.
      - Si cambia `folderName` → `storage.rename_position_folder`.
      - Acciones: `position.update` o `position.move`.
    - `DELETE /api/positions/{id}` → 409 `'El puesto tiene subordinados, requerimientos o candidatos'`.
    - `POST /api/sources {name, folderName?, category, avgResponseHours?}` y `PATCH /api/sources/{id}`.
    - `POST /api/sources/{id}/proposals {requirementId}`: suma 1 a `proposals_sent`, actualiza `last_proposal_at` y agrega la fuente a `published_source_ids`. Acción `source.proposal`.
    - `POST /api/requirements {positionId, quantity, urgency, targetDaysToFill?, context?, extraSkills?, publishedSourceIds?}` → 201.
    - `PATCH /api/requirements/{id}`: admite `quantity`, `urgency`, `targetDaysToFill`, `context`, `extraSkills`, `publishedSourceIds` y `status` (solo los cambios `Abierto`↔`Cancelado`).
      - Si `quantity` es menor que el número de contratados → 422.
      - Acciones: `requirement.update` o `requirement.cancel`.
    - `GET /api/settings`, `PATCH /api/settings {companyName?, aiModel?, aiFallbackModels?, aiPreapproveThreshold?, aiEnabled?}`. La bitácora guarda `details={'before':…,'after':…}`.
    - `GET /api/state`
- [ ] **Step 1: Escribir las pruebas que fallan.**
  - `test_create_position_tree_and_folder_name`:
    - Se crea "Gerencia General" y debajo "Superintendencia de Mina" → `folderName == 'superintendencia-de-mina'` y `parentId` correcto.
    - Hay 2 filas de bitácora `position.create` y `len(state['positions']) == 2`.
  - `test_position_cycle_rejected`: con A→B→C, `PATCH A {parentId: C}` → 422.
  - `test_delete_position_restrictions`: con un hijo → 409; con un requerimiento → 409; una hoja → 200 y bitácora `position.delete`.
  - `test_storage_safe_paths`:
    - `save_bytes('p','s','../../etc/x.pdf',…)` queda dentro de la raíz con el nombre `x.pdf`.
    - `CV José Ñuñez (1).pdf` conserva su nombre.
    - Un segundo archivo con el mismo nombre y otro hash recibe el sufijo `-<8hex>`.
    - `abs_path('../fuera')` lanza `ValueError`.
  - `test_rename_position_folder_moves_dir`.
  - `test_requirement_crud_and_state_shape`:
    - `state['jobNeeds'][0]` tiene exactamente las claves del contrato.
    - `status == 'Abierto'`, `filledCount == 0` y `title` es el nombre del puesto.
    - Cancelar → `'Cancelado'` y bitácora `requirement.cancel`.
  - `test_source_proposal`: 0→1 propuestas; el id de la fuente aparece en `publishedSourceIds` del requerimiento; bitácora `source.proposal`.
  - `test_settings_patch_logged`: el umbral pasa de 70 a 75 y la bitácora registra `details['before']['aiPreapproveThreshold'] == 70`.
  - `test_state_contract_keys`: `set(state.keys())` es igual a las claves del contrato, y `currentUser.fullName == hrChiefName == 'Ana Torres'`.
- [ ] **Step 2: Comprobar que fallan.** `docker compose run --rm api pytest tests/test_org.py tests/test_storage.py tests/test_state.py -v` → FAIL.
- [ ] **Step 3: Implementar.** Para detectar ciclos, recorrer los `parent_id` hacia arriba desde el nuevo padre.
- [ ] **Step 4: Verificar.** PASS.
- [ ] **Step 5: Commit.** `feat(api): organigrama, fuentes, requerimientos, configuración y foto base`.

### Task 5: Ingesta de CVs, personas y postulaciones

**Files:**
- Create: `app/models/people.py`, `alembic/versions/0004_people.py`, `app/services/{ingest,persons}.py`, `app/schemas/people.py`, `app/routers/{cv_files,persons,candidates}.py`
- Modify:
  - `app/services/snapshot.py`: agregar `candidates`, `blockedCvFiles`, los conteos de `positions` y `jobBoards`, y `filledCount`.
  - `app/routers/positions.py`: al renombrar la carpeta, actualizar `cv_files.stored_path`.
- Test: `tests/fixtures/cvs.py`, que define `make_cv_pdf(full_name, dni, email, phone, body='…') -> bytes` con fpdf2, con datos **ficticios**, y `make_blank_pdf() -> bytes`. Pruebas en `tests/test_cv_ingest.py` y `tests/test_persons.py`.

**Interfaces:**
- Consumes:
  - De la Tarea 3: `extract_text`, `parse_cv_text`, `compute_rule_scores`, `normalize_key`.
  - De la Tarea 4: `RrhhStorage`, `get_app_settings`, `build_state`.
  - De la Tarea 2: `log_action`.
- Produces:
  - `Person`: `id`, `first_names`, `last_names`, `full_name`, `document_id`, `email`, `phone`, `age`, `origin_location`, `university`, `career`, `years_worked`, `work_history_summary`, `specifications` / `languages` / `licenses` (JSONB), `field_sources` (JSONB `{campo: 'user'|'ia'|'reglas'}`), `psych_evaluation` (JSONB; por defecto `{testBatteryName:'Pendiente de prueba', accessCode:'', status:'Sin enviar', scores:null, averageScore:null, aptitudeLevel:'Pendiente', aiPsychObservation:''}`), `possible_same_person_ids` (JSONB), `created_at`.
  - `CvFile`: `id`, `sha256`, `position_id`, `source_id`, `original_name`, `stored_path`, `mime`, `size`, `origin`, `text`, `text_status`, `missing=False`, `uploaded_by_id`, `uploaded_by_name`, `uploaded_at`. Restricción `UNIQUE(sha256, position_id)`.
  - `DeletedCvHash`: `id`, `sha256`, `position_id`, `original_name`, `deleted_by_name`, `deleted_at`. Restricción `UNIQUE(sha256, position_id)`.
  - `Candidate`, la postulación:
    - Relaciones y datos: `id`, `person_id`, `cv_file_id` (único, nullable), `position_id`, `requirement_id` (nullable), `source_id`, `interview_notes`, `created_by_name`, `created_at`.
    - Resultado de las reglas: `rule_technical`, `rule_experience`, `rule_education`, `rule_bonus`, `rule_applied_criteria` (JSONB), `rule_report`.
    - Resultado de la IA: `ai_status`, `ai_verdict`, `ai_aptitude_score`, `ai_technical`, `ai_experience`, `ai_education`, `ai_strengths` (JSONB), `ai_observations` (JSONB), `ai_reason`, `ai_applied_criteria` (JSONB), `ai_summary`, `ai_detailed_report`, `ai_model`, `ai_classified_at`, `ai_attempts=0`, `ai_next_attempt_at`, `ai_error`.
    - Decisión humana: `decision='Pendiente de revisión'`, `manager_score`, `manager_notes`, `decided_by_id`, `decided_by_name`, `decided_at`.
  - `ingest.IngestResult` (dataclass): `status: Literal['created','duplicate','deleted_before','unsupported','too_large','invalid_target']`, `message`, `candidate_id`, `cv_file_id`, `person_id`, `existing: dict | None`.
  - `ingest.ingest_cv(db, storage, *, data: bytes, filename: str, position_id: str, source_id: str, requirement_id: str | None, origin: str, actor: User | str, existing_rel_path: str | None = None) -> IngestResult`. El orden es este:
    1. Validar la extensión y el tamaño.
    2. Calcular el sha256.
    3. Si el archivo está bloqueado para ese puesto → `deleted_before`, bitácora `cv.rejected_deleted`.
    4. Si ya existe `(sha, puesto)` → `duplicate`, bitácora `cv.duplicate_rejected`, con `existing={path, uploadedBy, uploadedAt}`.
    5. Guardar el archivo, salvo que venga `existing_rel_path`.
    6. Extraer el texto.
    7. Ejecutar `parse_cv_text`.
    8. Enlazar o crear la persona.
    9. Elegir el requerimiento.
    10. Calcular el puntaje por reglas.
    11. Fijar `ai_status`: `'Sin texto'` si `text_status != 'ok'`; si no, `'En cola'` cuando `ai_available(db)` es verdadero, o `'Sin IA'` cuando no.
    12. Registrar `cv.upload` con el resumen `"Subió el CV de {nombre} a {carpeta_puesto}/{carpeta_fuente}"`.
  - `ingest.ai_available(db) -> bool`: devuelve `settings.ai_enabled and bool(get_settings().openrouter_api_key)`.
  - `ingest.pick_requirement(db, position_id: str, requirement_id: str | None) -> Requirement | None`: lanza `ValueError` si el requerimiento indicado no está Abierto o es de otro puesto. Si no se indica ninguno, elige el más antiguo con estado Abierto.
  - `persons.link_or_create_person(db, *, sha256: str, values: dict, source: str, actor) -> Person`. El orden de búsqueda es este:
    1. el mismo sha en otro puesto;
    2. el mismo `document_id`;
    3. el mismo email, sin distinguir mayúsculas;
    4. si nada coincide, crea una persona nueva.

    Después, `refresh_possible_same`, que marca coincidencias por teléfono o por `normalize_key(full_name)`.
  - `persons.apply_person_fields(person, values: dict, source: Literal['user','ia','reglas']) -> list[str]`: la prioridad es user > ia > reglas, y un valor vacío no sobrescribe a uno lleno.
  - `persons.merge_persons(db, keep_id: str, drop_id: str, actor) -> Person`: mueve las postulaciones, los resultados y la evaluación psicológica a la persona que se conserva y borra la otra.
  - Rutas:
    - `POST /api/cv-files/check {items:[{sha256, positionId}]}` → `{results:[{sha256, positionId, status:'new'|'duplicate'|'deleted_before'}]}`.
    - `POST /api/cv-files` (multipart: `file`, `positionId`, `sourceId`, `requirementId?`, `origin='app'|'importacion'|'sync_local'`) → 201 `{result:{status,message,candidateId,cvFileId,personId}, state}`. Errores:
      - 409 `{detail:{code:'duplicate'|'deleted_before', message, existing}}`
      - 415 `'Formato no soportado: usa PDF, DOCX, TXT o RTF'`
      - 413 `'El archivo supera 15 MB'`
      - 422 si el requerimiento no corresponde.
    - `GET /api/cv-files/{id}/download`: `Content-Disposition` con `filename*=UTF-8''…` del nombre original. Bitácora `cv.download`.
    - `PATCH /api/cv-files/{id} {positionId?, sourceId?}`:
      - Mueve el archivo; si hay conflicto de duplicado → 409.
      - Si cambia el puesto, se vuelve a elegir el requerimiento y la postulación vuelve a `'En cola'` si hay IA.
      - Bitácora `cv.move`.
    - `DELETE /api/cv-files/{id}`:
      - Borra el archivo y la postulación. Si la persona se queda sin postulaciones, también la borra.
      - Crea el registro en `DeletedCvHash`.
      - Bitácora `cv.delete` con el resumen `"Eliminó el CV de {nombre} ({puesto})"`.
    - `DELETE /api/cv-files/blocked/{blockedId}`: bitácora `cv.unblock`.
    - `PATCH /api/persons/{id}`: actualiza campos personales con `source='user'`. La bitácora `person.update` guarda solo `details={'fields':[…]}`.
    - `POST /api/persons/{id}/merge {otherPersonId}`: bitácora `person.merge`.
    - `POST /api/candidates {fullName, career, positionId, sourceId, requirementId?, age?, originLocation?, university?, yearsWorked?, workHistorySummary?, specifications?, email?, phone?, documentId?, interviewNotes?}` → 201 `{candidateId, state}`. Para que la IA pueda clasificarla, se arma un texto a partir de los campos. Bitácora `candidate.create_manual`.
- [ ] **Step 1: Escribir las pruebas que fallan.**
  - `test_upload_creates_candidate_person_and_file`:
    - 201 y el archivo existe en `rrhh_root/<puesto>/<fuente>/`.
    - La postulación queda en `'Pendiente de revisión'` y `aiStatus == 'Sin IA'` (las pruebas corren sin clave).
    - La persona tiene `fullName` y `documentId` leídos del PDF ficticio, y hay bitácora `cv.upload`.
  - `test_duplicate_same_position_409`: `code == 'duplicate'`, `existing.uploadedBy == 'Ana Torres'` y bitácora `cv.duplicate_rejected`.
  - `test_same_file_other_position_new_application_same_person`: 201, el mismo `personId`, 2 archivos en disco y `otherApplications` de largo 1 en ambas postulaciones.
  - `test_link_by_document_or_email`:
    - Dos PDFs distintos con el mismo DNI → la misma persona.
    - Si solo coincide el teléfono → personas distintas, con `possibleSamePersonIds` que se apuntan entre sí.
  - `test_check_endpoint_statuses`: se obtienen los tres estados (`new`, `duplicate`, `deleted_before`).
  - `test_delete_blocks_reimport_and_removes_personal_data`:
    - Tras borrar, no quedan el archivo, la postulación ni la persona.
    - Volver a subirlo → 409 `deleted_before`; tras desbloquear → 201.
    - El resumen de la bitácora contiene el nombre y el puesto.
  - `test_delete_keeps_person_with_other_applications`.
  - `test_move_cv_between_positions`: el archivo se mueve, `stored_path` se actualiza y el requerimiento se vuelve a elegir.
  - `test_unsupported_and_too_large`: un `.doc` → 415; 16 MB → 413.
  - `test_scanned_pdf_sin_texto`: un PDF en blanco → `aiStatus == 'Sin texto'`.
  - `test_requirement_assignment`: con dos requerimientos abiertos se asigna el más antiguo; si se indica otro, se usa ese; si el indicado está cancelado → 422.
  - `test_person_field_precedence`: tras una edición del usuario, las reglas no la pisan; un valor de la IA sí reemplaza uno de las reglas.
  - `test_merge_persons`.
  - `test_unicode_filename_roundtrip`: se sube `CV José Ñuñez (1).pdf` y la descarga lo devuelve con ese nombre en `filename*`, con el contenido idéntico.
  - `test_manual_candidate`.
  - `test_rename_position_folder_updates_paths`.
- [ ] **Step 2: Comprobar que fallan.** `docker compose run --rm api pytest tests/test_cv_ingest.py tests/test_persons.py -v` → FAIL.
- [ ] **Step 3: Implementar** según las interfaces. En la foto, `metricReport` se calcula en el momento:
  - Se usan los pilares de la IA si el estado es `Clasificado`; si no, los de las reglas.
  - El valor psicológico es el de la persona.
  - Se aplican `global_index` y `fit_verdict`.
  - `aiDetailedReport` toma el texto de la IA o, si no hay, `rule_report`.
- [ ] **Step 4: Verificar.** PASS.
- [ ] **Step 5: Commit.** `feat(api): carpeta de CVs, personas y postulaciones sin repetidos`.

### Task 6: Decisiones humanas, cobertura de requerimientos y criterios

**Files:**
- Create: `app/models/criteria.py`, `alembic/versions/0005_criteria.py`, `app/services/decisions.py`, `app/routers/criteria.py`
- Modify:
  - `app/routers/candidates.py`: agregar la ruta de decisión.
  - `app/services/snapshot.py`: agregar los criterios y los kpis.
  - `app/services/ingest.py`: pasar los criterios a `compute_rule_scores`.
- Test: `tests/test_decisions.py`, `tests/test_criteria.py`

**Interfaces:**
- Produces:
  - `RecruitmentCriterion`: `id`, `title`, `applies_to_department`, `weight_label` (`'Prioritario'|'Importante'|'Deseable'`), `rule_text`, `is_correction=False`, `wrong_ai_assumption`, `learned_from_candidate`, `created_by_name`, `created_at`, `updated_at`.
  - `decisions.DecisionError(status: int, message: str)`
  - `decisions.apply_decision(db, candidate, *, decision: str, manager_score: int | None, manager_notes: str, requirement_id: str | None, actor: User) -> None`:
    - Valida la transición con `DECISION_TRANSITIONS`.
    - Bloquea la fila del requerimiento con `with_for_update()`.
    - **Contratado** exige un requerimiento `Abierto` del mismo puesto con plazas libres. Si al contratar se completan las plazas, el requerimiento pasa a `Cubierto` y se registra `requirement.covered` con actor `'Sistema'`.
    - **Salir de Contratado** vuelve a abrir el requerimiento si estaba Cubierto y queda una plaza libre (`requirement.reopened`).
    - Bitácora `candidate.decision`. Resúmenes:
      - `"Aprobó a {n} para {puesto}"`, `"Rechazó a…"` o `"Contrató a…"`;
      - `"Deshizo la contratación de {n} ({puesto})"` al salir de Contratado.
    - Los detalles guardan `{from, to, managerScore}`.
  - Rutas:
    - `POST /api/candidates/{id}/decision {decision, managerScore?, managerNotes?, requirementId?, teachAi?, criterionTitle?, criterionRule?, criterionWeight?, isCorrection?, wrongAiAssumption?}` → `{state}`. Si `teachAi` es verdadero, se crea un criterio con `appliesToDepartment = área del puesto` y `learnedFromCandidate = nombre completo` (bitácora `criterion.create`).
    - `GET /api/criteria`, `POST /api/criteria` y `PATCH /api/criteria/{id}`, con bitácora `criterion.create` y `criterion.update`.
  - La foto de las postulaciones incluye `decision`, `managerScore`, `managerNotes`, `evaluatedBy` y `evaluatedAt`. `kpis = compute_kpis(...)`.
- [ ] **Step 1: Escribir las pruebas que fallan.**
  - `test_transitions_matrix`, parametrizada con las 16 combinaciones origen→destino. Las permitidas devuelven 200; las demás, 409 `'Transición no permitida: {origen} → {destino}'`.
  - `test_hire_requires_open_requirement_with_room`:
    - Sin requerimiento → 409 `'La postulación no tiene un requerimiento abierto asignado'`.
    - Con `quantity=1`, contratar a A → el requerimiento queda `Cubierto`, con bitácora `requirement.covered` y `user_name == 'Sistema'`.
    - Contratar a B en el mismo requerimiento → 409 `'El requerimiento ya está cubierto'`.
  - `test_undo_hire_reopens_requirement`.
  - `test_decision_audit_records_actor`: si decide el usuario B, la bitácora tiene `user_name == B` y la foto `evaluatedBy == B`.
  - `test_teach_ai_creates_area_criterion`.
  - `test_kpis_in_state`: `filledCount` y `aiAgreementRate` cambian después de las decisiones.
- [ ] **Step 2: Comprobar que fallan.** `docker compose run --rm api pytest tests/test_decisions.py tests/test_criteria.py -v` → FAIL.
- [ ] **Step 3: Implementar.**
- [ ] **Step 4: Verificar.** PASS.
- [ ] **Step 5: Commit.** `feat(api): decisiones humanas, cobertura y criterios por área`.

### Task 7: Cliente de OpenRouter, clasificador y worker

**Files:**
- Create: `app/services/{openrouter,classifier}.py`, `app/worker.py`, `app/routers/ai_queue.py`
- Modify: `app/config.py` (agregar `DEFAULT_AI_MODEL` y `DEFAULT_AI_FALLBACK_MODELS`), `app/routers/settings.py` (agregar `GET /api/settings/ai-models`) y `app/services/snapshot.py` (agregar `aiQueue` y los campos `ai*`)
- Test: `tests/test_openrouter.py`, `tests/test_classifier.py`, `tests/test_worker.py`

**Interfaces:**
- Consumes: `apply_person_fields`, `link_or_create_person` y `merge_persons` (Tarea 5), `get_app_settings`, `log_action`.
- Produces:
  - `OpenRouterClient(api_key: str, base_url: str = 'https://openrouter.ai/api/v1', http: httpx.Client | None = None, timeout: float = 90)`.
  - `.chat(messages: list[dict], *, model: str, fallback_models: list[str] = [], json_mode: bool = False, max_tokens: int = 2000) -> ChatResult(content: str, model: str)`:
    - El cuerpo de la petición lleva `model`, `models: [model, *fallback]` (solo si hay modelos de respaldo), `messages`, `response_format: {"type": "json_object"}` (si `json_mode`), `max_tokens` y `temperature: 0.2`.
    - Headers: `Authorization` y `X-Title: Pulso Laboral`.
  - `.list_free_models() -> list[dict]`: devuelve `{id, name, contextLength}` de los modelos con `pricing.prompt == "0"` y `pricing.completion == "0"`.
  - Excepciones:
    - `OpenRouterError(message)`.
    - `PerMinuteRateLimit(retry_after_s: int)`: se usa el header `Retry-After`; por defecto, 60.
    - `DailyLimitReached(reset_at: datetime)`: se lanza ante un 429 cuyo mensaje, en minúsculas, contiene `per-day`, `per day` o `free-models-per-day`. `reset_at` sale del header `X-RateLimit-Reset` (epoch en ms) o, si falta, es las 00:00 UTC siguientes.
  - `classifier.extract_json_object(content: str) -> dict`: quita los bloques ```` ``` ```` y toma el primer objeto `{…}` balanceado. Si no lo hay, lanza `ValueError`.
  - `classifier.ClassificationResult`, un modelo Pydantic con estas claves:
    - `datosPersonales{nombres, apellidos, documento, email, telefono, edad, procedencia}`
    - `formacion{universidad, carrera}`
    - `experiencia{anios, resumen, empleos[{empresa, cargo, desde, hasta}]}`
    - `certificaciones`, `licencias`, `idiomas`
    - `puntajes{tecnico, experiencia, formacion}`
    - `puntajeAptitud`, `veredicto`, `fortalezas`, `observaciones`, `motivo`, `criteriosAplicados`

    Los validadores convierten los números que vienen como string, acotan los puntajes a 0-100 y normalizan el veredicto: si `normalize_key` da `pre-aprobado`, `preaprobado` o `aprobado`, queda `'Pre-aprobado'`; cualquier otro valor queda `'Pre-denegado'`.
  - `classifier.build_classification_messages(position: dict, requirement: dict | None, criteria: list[dict], cv_text: str, threshold: int) -> list[dict]`:
    - El prompt de sistema va en español y describe el esquema JSON y el umbral.
    - Solo incluye los criterios del área del puesto o de `'Todas las áreas'`, con las correcciones primero e incluyendo `"Supuesto corregido: …"`.
    - El CV se recorta a `CV_TEXT_LIMIT`.
  - `classifier.classify_candidate(db, candidate: Candidate, client: OpenRouterClient) -> None`:
    - Llama a `chat` en modo JSON. Si el JSON es inválido, reintenta una vez con el mensaje de usuario `'Tu respuesta anterior no era JSON válido según el esquema. Devuelve solo el JSON.'`. Si vuelve a fallar, lanza `ClassificationFormatError`.
    - Si funciona:
      - aplica la regla del umbral y guarda los campos `ai_*`;
      - aplica los datos personales con `source='ia'`;
      - si el documento o el email coinciden con otra persona, `merge_persons` y bitácora `person.link`;
      - registra `ai.classify` con actor `'Sistema (IA)'`, resumen `"IA clasificó a {n} para {puesto}: {veredicto} ({puntaje})"` y `details={'model':…}`.
  - `worker.recover_stuck(db) -> int`: pasa de `Procesando` a `En cola`.
  - `worker.process_one(db, client: OpenRouterClient | None, now: datetime) -> Literal['idle','processed','paused','error']`. Toma una postulación con `SELECT … WHERE ai_status='En cola' AND (ai_next_attempt_at IS NULL OR ai_next_attempt_at <= now) ORDER BY created_at FOR UPDATE SKIP LOCKED LIMIT 1`. Ante cada fallo:
    - **Límite diario:** guarda `settings.ai_paused_until` y devuelve la postulación a `En cola`. Registra `ai.daily_limit` solo cuando cambia la fecha de pausa.
    - **Límite por minuto:** `ai_next_attempt_at = now + retry_after`, sin sumar un intento.
    - **Otro error:** suma un intento. Al tercero queda en `Error IA`, con `ai_error` y bitácora `ai.classify_error`; antes de eso, el siguiente intento va a `now + 30·2^intentos` s.
  - `worker.run_forever() -> None`:
    1. Al iniciar, ejecuta `recover_stuck`.
    2. Espera `60/worker_rate_per_minute` s después de cada `processed` y 5 s en los estados idle o paused.
    3. Llama a `server_scan` cada `server_scan_interval_s` (hasta la Tarea 8 la llamada queda protegida con `if` por import opcional).
  - Rutas:
    - `GET /api/ai/queue` → `{queued, processing, errors, sinIa, pausedUntil, aiEnabled, model}`.
    - `POST /api/ai/queue/retry-errors`: vuelve a poner en cola las postulaciones en `Error IA` y, si hay IA disponible, también las `Sin IA`, y reinicia sus intentos. Bitácora `ai.requeue`.
    - `POST /api/candidates/{id}/reclassify` (`candidate.reclassify`) y `POST /api/positions/{id}/reclassify` (`position.reclassify`).
    - `GET /api/settings/ai-models`: guarda el resultado en memoria durante 1 h. Si falta la clave → 503 `'La IA no está configurada (falta OPENROUTER_API_KEY)'`.
- [ ] **Step 1: Elegir el modelo por defecto.** Ejecutar `curl -s https://openrouter.ai/api/v1/models`, elegir un modelo `:free` de instrucciones con contexto ≥ 32k y 2 de respaldo, y fijarlos en `config.py`. Dejar la elección y la fecha para el README (Tarea 12).
- [ ] **Step 2: Escribir las pruebas que fallan,** con respx simulando `https://openrouter.ai/api/v1/...`:
  - `test_chat_sends_models_and_json_mode`.
  - `test_429_daily_vs_per_minute`:
    - Un cuerpo `{"error":{"message":"Rate limit exceeded: free-models-per-day"}}` con `X-RateLimit-Reset: 1795046400000` lanza `DailyLimitReached` con `reset_at` igual a ese instante.
    - Un mensaje con `per-min` y `Retry-After: 20` lanza `PerMinuteRateLimit(20)`.
  - `test_list_free_models_filters_price`.
  - `test_extract_json_object_handles_fences_and_prose`: ```` '```json\n{"a":1}\n```' ```` → `{'a':1}` y `'Aquí está: {"a": {"b": 2}} gracias'` → `{'a':{'b':2}}`.
  - `test_classification_normalizes_scores_and_verdict`: `"85"` → 85, 150 → 100 y `'preaprobado'` → `'Pre-aprobado'`.
  - `test_final_verdict_threshold`, con umbral 70:
    - el modelo dice Pre-aprobado con 65 → `'Pre-denegado'`;
    - Pre-aprobado con 75 → `'Pre-aprobado'`;
    - Pre-denegado con 90 → `'Pre-denegado'`.
  - `test_prompt_area_criteria_corrections_first_and_truncation`.
  - `test_classify_retries_once_on_bad_json` y `test_classify_two_bad_json_raises`.
  - `test_worker_processes_and_audits`: el estado pasa de `En cola` a `Clasificado`; la bitácora tiene `user_name == 'Sistema (IA)'`; el email que extrajo la IA llena el campo vacío, pero no pisa el teléfono que editó un usuario.
  - `test_worker_daily_limit_pauses_queue`: se fija `pausedUntil`; antes del reinicio `process_one` devuelve `'paused'`, y después procesa.
  - `test_worker_retries_then_error_and_requeue`.
  - `test_recover_stuck_processing`: una postulación en `Procesando` pasa a `En cola` y la función devuelve 1.
  - `test_ai_links_person_by_extracted_dni`.
  - `test_upload_with_ai_available_is_queued`: con una clave configurada, la subida deja la postulación `'En cola'`.
- [ ] **Step 3: Comprobar que fallan.** `docker compose run --rm api pytest tests/test_openrouter.py tests/test_classifier.py tests/test_worker.py -v` → FAIL.
- [ ] **Step 4: Implementar.**
- [ ] **Step 5: Verificar.** PASS.
- [ ] **Step 6: Commit.** `feat(api): clasificación con OpenRouter en cola con límites`.

### Task 8: Revisión de la carpeta del servidor

**Files:**
- Create: `app/services/server_scan.py`
- Modify: `app/worker.py` (conectar el escaneo)
- Test: `tests/test_server_scan.py`

**Interfaces:**
- Consumes: `RrhhStorage.iter_files`, `ingest_cv(existing_rel_path=…)`, `normalize_key`.
- Produces: `scan_server_folder(db, storage) -> ScanSummary`. El resultado es un dataclass con `ingested`, `duplicates`, `blocked`, `unsupported` y `unmatched_folders: list[str]`. La función:
  - Relaciona las carpetas con puestos y fuentes por `folder_name` y, si no coincide, por `normalize_key(name)`.
  - Omite las rutas relativas que ya están registradas.
  - Ingresa las demás con `origin='carpeta_servidor'` y actor `'Sistema'`.
- [ ] **Step 1: Escribir las pruebas que fallan.**
  - `test_scan_ingests_new_files_once`: se copia un PDF ficticio a la carpeta y se escanea → `ingested == 1` y `origin == 'carpeta_servidor'`, sin copiar el archivo; un segundo escaneo da `ingested == 0`.
  - `test_scan_skips_blocked_and_reports_unmatched`: un archivo bloqueado da `blocked == 1`; la carpeta `desconocido/linkedin` aparece en `unmatched_folders`.
  - `test_scan_counts_same_sha_other_name_as_duplicate`.
- [ ] **Step 2: Comprobar que fallan.** `docker compose run --rm api pytest tests/test_server_scan.py -v` → FAIL.
- [ ] **Step 3: Implementar.**
- [ ] **Step 4: Verificar.** PASS.
- [ ] **Step 5: Commit.** `feat(api): registro automático de CVs copiados a la carpeta del servidor`.

### Task 9: Informe de IA, chat y votos

**Files:**
- Create: `app/models/ai.py` (`AiConversation`, `AiMessage`), `alembic/versions/0006_ai_chat.py`, `app/services/ai_chat.py`, `app/routers/ai_chat.py`
- Modify: `app/services/snapshot.py` (agregar `aiConversations`)
- Test: `tests/test_ai_chat.py`

**Interfaces:**
- Produces:
  - `AiConversation`: `id`, `candidate_id` (FK con borrado en cascada), `title`, `created_by_name`, `created_at` y `structured_report` (JSONB `{recommendation, strengths, watchouts, concreteSummary}`).
  - `AiMessage`: `id`, `conversation_id`, `role` (`'assistant'|'user'`), `content`, `created_at`, `vote` (`'up'|'down'|None`), `feedback_note`.
  - `ai_chat.evaluate_candidate(db, candidate, client, actor) -> AiConversation`
  - `ai_chat.assistant_reply(db, conversation_id: str | None, candidate, message: str, client, actor) -> AiConversation`: envía al modelo los datos de la postulación, el texto del CV y los mensajes anteriores.
  - `ai_chat.apply_vote(db, conversation_id, message_id, vote, feedback_note, actor) -> RecruitmentCriterion | None`. Con un voto `down` y una nota, crea un criterio:
    - `title`: los primeros 80 caracteres de la nota;
    - `ruleText`: la nota;
    - `weightLabel='Importante'` e `isCorrection=True`;
    - `appliesToDepartment`: el área del puesto;
    - `wrongAiAssumption`: los primeros 200 caracteres de la respuesta de la IA.
  - Rutas:
    - `POST /api/ai/evaluate-candidate {candidateId}` → `{conversation, state}`.
    - `POST /api/ai/assistant-chat {conversationId?, candidateId, message}` → `{conversation, state}`.
    - `POST /api/ai/vote-response {conversationId, messageId, vote, feedbackNote?}` → `{criterion?, state}`.
    - Bitácora: `ai.evaluate`, `ai.chat` y `ai.vote`.
  - Errores:
    - Límite diario → 429 `'Límite diario de IA alcanzado; se reanuda a las {HH:MM} (hora de Perú)'`, con la hora convertida a America/Lima.
    - Otros errores de OpenRouter → 502 `'No se pudo consultar la IA: {mensaje}'`.
    - Sin IA → 503 `'La IA no está configurada (falta OPENROUTER_API_KEY o está desactivada)'`.
- [ ] **Step 1: Escribir las pruebas que fallan.**
  - `test_evaluate_creates_structured_conversation`.
  - `test_chat_appends_and_sends_history`: se verifica que el cuerpo de la petición contiene el mensaje anterior.
  - `test_vote_down_with_note_creates_criterion`.
  - `test_vote_up_no_criterion`.
  - `test_daily_limit_returns_429_message`.
  - `test_ai_unavailable_503`.
  - `test_conversations_in_state_and_cascade_on_cv_delete`.
- [ ] **Step 2: Comprobar que fallan.** `docker compose run --rm api pytest tests/test_ai_chat.py -v` → FAIL.
- [ ] **Step 3: Implementar.**
- [ ] **Step 4: Verificar.** PASS.
- [ ] **Step 5: Commit.** `feat(api): informe, chat y votos con IA`.

### Task 10: Pruebas psicológicas y Excel (port)

**Files:**
- Create: `app/models/tests_module.py` (`TestDefinition`, `ExcelTestResult`), `alembic/versions/0007_tests.py`, `app/schemas/tests_module.py`, `app/routers/tests_module.py`
- Modify: `app/services/excel_tests.py` (agregar `read_excel_rows` y `build_excel_template`) y `app/services/snapshot.py`
- Test: `tests/test_tests_module.py`

**Interfaces:**
- Produces:
  - `TestDefinition`: los campos de `src/types.ts:113-128`.
  - `ExcelTestResult`: `id`, `person_id`, `test_id` (nullable), `test_name`, `file_name`, `uploaded_at`, `uploaded_by_name`, `total_questions`, `answered_count`, `auto_computed_score`, `is_concrete_result`, `concrete_verdict`, `ai_analysis`, `parsed_rows` (JSONB), `passing_score`, `passed`.
  - `read_excel_rows(data: bytes, filename: str) -> tuple[list[dict], str]`: lee la primera hoja con openpyxl (o un CSV) y devuelve las filas y el nombre de la hoja.
  - `build_excel_template(test: dict | None, candidate_name: str | None) -> bytes`:
    - Una hoja `Prueba` con las columnas exactas `['Prueba Evaluada','Candidato','Pregunta','Respuesta','Escala Máxima']`.
    - Una fila por pregunta, con `Respuesta` vacía y `Escala Máxima` 5.
    - Sin prueba, usa las preguntas por defecto: `'Estabilidad operativa bajo presión en faena'`, `'Cumplimiento estricto de normas HSEC y PETAR'`, `'Dominio técnico del puesto minero'` y `'Coordinación efectiva en guardia 14x7'`.
  - Rutas (mismos caminos que hoy; los archivos ahora van en multipart):
    - `POST /api/recruitment/psych-tests/send {candidateId, testBatteryName}`: actualiza la evaluación de **la persona** a `status='Enviada'`, con `accessCode=f'PL-PS-{n:04d}'` (secuencial), `sentAt` y `sentBy`. Bitácora `psych.send`.
    - `POST /api/recruitment/psych-tests/{candidateId}/submit {answers:{estabilidad,tolerancia,seguridad,equipo,razonamiento}}`: aplica `score_psych_answers` y `evaluate_psychometric_battery`, y deja la evaluación en `Completada`. Bitácora `psych.submit`.
    - `POST /api/recruitment/tests {name, category, targetArea, durationMinutes, passingScore, questions}` → `{test, state}`.
    - `POST /api/recruitment/tests/import-excel` (multipart: `file`, `customTestName?`, `candidateId?`) → `{test, isNewTest, excelResult?, state}`.
    - `POST /api/recruitment/tests/upload-excel` (multipart: `file`, `candidateId`, `testId?`, `testName`) → `{excelResult?, registeredOnly?, test?, message?, state}`.
    - `DELETE /api/recruitment/tests/{id}`.
    - `GET /api/tests/excel-template?testId=&candidateId=`: devuelve un `.xlsx` llamado `Prueba_{folder_name_for(nombre)}[_{folder_name_for(candidato)}].xlsx`.
    - Bitácora: `test.create`, `test.import`, `test.upload_result` y `test.delete`.
  - **Regla:** si la prueba es de categoría `'Psicolaboral'` y el veredicto no es `'Inconsistencia Detectada'`, la evaluación psicológica de la persona se reemplaza con `derivedScores` evaluados (`Completada`, con `testBatteryName` igual al nombre de la prueba).
- [ ] **Step 1: Escribir las pruebas que fallan.**
  - `test_send_and_submit_psych`: aptitud calculada, el Índice Global de la postulación usa el promedio real y hay bitácora.
  - `test_template_roundtrip`: plantilla de una prueba con 3 preguntas, se completan las respuestas 5/4/5 con openpyxl, se sube → `'Resultados Concretos'` y `answeredCount == 3`.
  - `test_upload_empty_template_registered_only`.
  - `test_import_excel_detects_name_category`: archivo `examen_hsec.xlsx` con las filas del test de la Tarea 3.
  - `test_psicolaboral_result_updates_person_psych`.
  - `test_passed_uses_passing_score`.
  - `test_delete_test_logged`.
- [ ] **Step 2: Comprobar que fallan.** `docker compose run --rm api pytest tests/test_tests_module.py -v` → FAIL.
- [ ] **Step 3: Implementar.**
- [ ] **Step 4: Verificar.** PASS.
- [ ] **Step 5: Commit.** `feat(api): pruebas psicológicas y Excel`.

### Task 11: Informes, bitácora consultable y exportaciones

**Files:**
- Create: `app/services/reports.py`, `app/routers/{reports,audit}.py`
- Test: `tests/test_reports.py`, `tests/test_audit_api.py`

**Interfaces:**
- Consumes: `build_state` (los informes se generan desde la foto).
- Produces:
  - `build_candidates_csv(candidates: list[dict]) -> str`: port de `recruitment.ts:573-634`. Usa BOM `﻿` y saltos `\r\n`. Cambios de columnas:
    - `'Propuesta IA'` se reemplaza por `'Estado IA'`, `'Veredicto IA'` y `'Puntaje Aptitud IA'`;
    - la columna de decisión se llama `'Decisión'`;
    - se agrega `'Decidido por'`.
  - `build_kpis_csv(state: dict) -> str`: port de `recruitment.ts:639-690`. La empresa sale de `state['companyName']`.
  - `build_candidate_doc_html(candidate: dict, company_name: str) -> str`: port de `recruitment.ts:710-805`. Agrega el veredicto de la IA, la decisión y quién decidió, y conserva el título `'Dictamen Consolidado de la IA para Gerencia General'`.
  - `build_admin_doc_html(state: dict) -> str`: port de `recruitment.ts:811-924`. La terna son los 3 primeros por `overallScore` y se conserva `'Ranking de Bolsas de Trabajo'`.
  - `build_audit_csv(rows: list[dict]) -> str`
  - Rutas de informes (cada descarga deja bitácora `report.download` con `details={'report':…}`):
    - `GET /api/reports/admin-doc`: `application/msword`, archivo `Informe_Ejecutivo_{AAAA-MM-DD}.doc`.
    - `GET /api/reports/candidate/{id}/doc`: archivo `Ficha_{folder_name_for(nombre)}.doc`.
    - `GET /api/reports/candidates-csv`: archivo `Candidatos_{fecha}.csv`.
    - `GET /api/reports/kpis-csv`: archivo `KPIs_Procesos_{fecha}.csv`.
  - Rutas de bitácora:
    - `GET /api/audit?userId&action&entityType&entityId&dateFrom&dateTo&q&limit=100&offset=0` → `{items:[{id, at, userId, userName, action, entityType, entityId, summary, details, ip}], total}`.
      - `action` filtra por prefijo (`cv.` coincide con todas las `cv.*`).
      - `q` busca con `ILIKE` en el resumen.
      - `limit` admite como máximo 500.
    - `GET /api/audit/export.csv`: acepta los mismos filtros y registra `audit.export`.
- [ ] **Step 1: Escribir las pruebas que fallan.**
  - `test_candidates_csv_and_admin_doc` (port del test TS 5): el CSV empieza con BOM y contiene `'Universidad / Instituto'` y `'Seguridad HSEC'`; el documento contiene `'Compañía Minera Las Bravas'` y `'Ranking de Bolsas de Trabajo'`.
  - `test_candidate_doc_shows_decider`.
  - `test_report_downloads_are_logged`.
  - `test_audit_filters`: por usuario, por prefijo de acción, por rango de fechas y por `q`, con `total` correcto.
  - `test_audit_export_csv_bom_and_logged`.
- [ ] **Step 2: Comprobar que fallan.** `docker compose run --rm api pytest tests/test_reports.py tests/test_audit_api.py -v` → FAIL.
- [ ] **Step 3: Implementar.**
- [ ] **Step 4: Verificar.** PASS.
- [ ] **Step 5: Commit.** `feat(api): informes Word/CSV y consulta de bitácora`.

### Task 12: Respaldo y restauración, datos demo, README y verificación completa

**Files:**
- Create: `app/services/datacenter.py`, `app/routers/datacenter.py`, `app/seed.py`, `rebuild/docs/README.md` (sección API)
- Test: `tests/test_datacenter.py`, `tests/test_seed.py`

**Interfaces:**
- Produces:
  - `export_business_data(db) -> dict`: devuelve `{'version': 1, 'exportedAt': iso, 'data': {positions, sources, requirements, persons, cvFiles, deletedCvHashes, candidates, criteria, tests, excelResults, conversations, messages, settings}}`. No incluye usuarios ni bitácora.
  - `restore_business_data(db, payload: dict, actor: User, storage: RrhhStorage) -> dict`:
    - Valida `version == 1`.
    - En una sola transacción borra las tablas de negocio en orden de dependencias e inserta los datos del respaldo.
    - Marca `missing=True` en los `cv_files` cuyo archivo no está en disco.
    - Registra `datacenter.restore` con los conteos.
    - Devuelve `{counts, missingFiles}`.
  - Rutas:
    - `GET /api/datacenter/status` → `{mode:'PostgreSQL', storagePath, totalRecords, candidatesCount, vacanciesCount, boardsCount, criteriaCount, psychCompletedCount, lastSavedAt}`.
    - `GET /api/datacenter/backup`: archivo `Respaldo_Pulso_Laboral_{fecha}.json`; bitácora `datacenter.backup`.
    - `POST /api/datacenter/restore {confirm, backup}`. Si `confirm` no es `'RESTAURAR'` → 422 `'Escribe RESTAURAR para confirmar'`.
  - `python -m app.seed --demo`, con `main(argv) -> int`:
    - Si ya hay puestos, devuelve 1 con el mensaje `'La base ya tiene datos; no se cargó la demo'`.
    - Si la base está vacía, carga:
      - la empresa `'Compañía Minera Las Bravas'`;
      - el organigrama de abajo (28 puestos); los 15 puestos de vacantes copian `requiredSkills` y `technicalSpecifications` de `seedData.ts:13-286`;
      - 15 requerimientos, con urgencia, plazas y plazo objetivo de `seedData.ts`;
      - 6 fuentes (nombre, carpeta, categoría, propuestas, horas de respuesta):
        - Computrabajo Minería / `computrabajo` / Bolsa Nacional / 9 / 6
        - LinkedIn Talento Minero / `linkedin` / Red Profesional / 7 / 14
        - Bumeran Perú / `bumeran` / Bolsa Nacional / 6 / 11
        - Referidos de Faena / `referidos-faena` / Referidos Faena / 4 / 4
        - Portal Talento Las Bravas / `portal-las-bravas` / Portal Minero / 5 / 9
        - Indeed Operaciones / `indeed` / Bolsa Nacional / 3 / 18
      - los 2 criterios de `seedData.ts:306-332`.
    - Actor `'Sistema'` y bitácora `seed.demo`.
  - **Organigrama de la demo** (área entre paréntesis; los hijos heredan el área del padre si no se indica):

```
Gerencia General (Gerencia)
├ Gerencia de Operaciones Mina (Operaciones Mina)
│ ├ Superintendencia de Mina
│ │ └ Jefe de Guardia Mina (Subterránea / Tajo Abierto)
│ │   ├ Operador de Maquinaria Pesada Mina (Scooptram / Volquete / Camión)
│ │   ├ Perforista y Cargador de Explosivos (Carnet SUCAMEC)  (Perforación y Voladura)
│ │   └ Técnico de Sostenimiento y Ventilación Mina
│ └ Superintendencia de Geología y Planeamiento (Geología y Planeamiento)
│   ├ Geólogo de Mina y Control de Leyes (Ore Control)
│   └ Ingeniero de Planeamiento Mina (Corto y Mediano Plazo)
├ Gerencia de Planta (Control Metalúrgico)
│ ├ Superintendencia de Planta Concentradora
│ │ └ Operador de Planta Concentradora Senior
│ └ Jefe de Laboratorio Metalúrgico
│   └ Analista de Laboratorio Metalúrgico
├ Gerencia de Mantenimiento (Mantenimiento Mina)
│ ├ Mecánico de Mantenimiento Equipo Pesado (Trackless / Flota)
│ └ Electricista Industrial de Alta Tensión y Subestaciones Mina
├ Gerencia de Seguridad HSEC (Seguridad HSEC)
│ ├ Ingeniero Supervisor de Seguridad HSEC
│ └ Paramédico / Médico Ocupacional de Tópico Minero
├ Gerencia de Medio Ambiente y Relaciones Comunitarias (Medio Ambiente y RR.CC.)
│ ├ Supervisor de Medio Ambiente y Recursos Hídricos
│ └ Especialista de Relaciones Comunitarias y Gestión Social
├ Gerencia de Logística (Logística y Campamento)
│ └ Coordinador de Bodega, Explosivos y Campamento Minero
└ Gerencia de Recursos Humanos (Recursos Humanos)
  └ Jefe de Recursos Humanos
```

- [ ] **Step 1: Escribir las pruebas que fallan.**
  - `test_backup_restore_roundtrip`: después de restaurar, los conteos son iguales.
  - `test_restore_never_touches_users_or_audit`: la cantidad de usuarios no cambia y la bitácora solo crece.
  - `test_restore_marks_missing_files`.
  - `test_restore_requires_confirm`.
  - `test_seed_demo_counts`: 28 puestos, 15 requerimientos con suma de `quantity` igual a 32, 6 fuentes y 2 criterios.
  - `test_seed_refuses_non_empty`.
- [ ] **Step 2: Comprobar que fallan.** `docker compose run --rm api pytest tests/test_datacenter.py tests/test_seed.py -v` → FAIL.
- [ ] **Step 3: Implementar,** y escribir la sección API del README:
  - requisitos;
  - cómo copiar `.env.example` y poner `OPENROUTER_API_KEY`;
  - `docker compose up -d --build`;
  - cargar la demo;
  - el modelo elegido y su fecha;
  - los cupos de OpenRouter y el aviso de privacidad;
  - cómo desplegar en un servidor con `REGISTRATION_MODE=invite`.
- [ ] **Step 4: Verificación completa.**
  1. `docker compose down -v && docker compose up -d --build`
  2. `docker compose exec api python -m app.seed --demo` (debe salir 0)
  3. `docker compose run --rm api pytest -q`: todo debe pasar.
  4. Prueba rápida con curl contra `http://localhost:8000`, en este orden:
     1. registrar una cuenta;
     2. llamar a `GET /api/state` con el token: 28 puestos;
     3. subir `tests/fixtures` con un PDF generado: 201;
     4. confirmar que `GET /api/state` trae `candidates` de largo 1;
     5. confirmar que `GET /api/audit` incluye `cv.upload`.
  5. Si el usuario ya puso la clave real de OpenRouter, confirmar en `docker compose logs worker` que la postulación pasa a `Clasificado`.
- [ ] **Step 5: Commit.** `feat(api): respaldo/restauración, datos demo y README`.
