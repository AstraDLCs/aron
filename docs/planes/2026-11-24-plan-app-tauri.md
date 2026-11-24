# App de escritorio Tauri de Pulso Laboral — Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Construir en `rebuild/tauri` una app de escritorio para Windows, con instalador NSIS, que reutiliza la interfaz React de `src/` y se conecta a la API FastAPI con inicio de sesión. Suma cuatro módulos nuevos: organigrama, carpeta de CVs con sincronización local, bitácora y configuración.

**Architecture:**
- **Interfaz:** Tauri v2 empaqueta una app de Vite + React 19. Mantiene en memoria la foto `GET /api/state`, que se refresca después de cada acción y cada 30 s.
- **Rust:** se encarga del sistema de archivos local: recorrer y calcular hashes de la carpeta de CVs, guardar descargas y abrir archivos.
- **Configuración:** la URL de la API y el token se guardan con `plugin-store`.

**Tech Stack:** Tauri 2 (`plugin-dialog`, `plugin-store`, `plugin-opener`), Rust (sha2, walkdir), React 19, TypeScript (strict), Vite, Tailwind CSS 4, lucide-react, @fontsource y Vitest.

**Spec:** `rebuild/docs/diseno-rebuild.md`. **Depende de** `rebuild/docs/planes/2026-11-24-plan-api-fastapi.md`, y en particular de su sección "Contrato de la foto" y de sus rutas. Este plan se ejecuta después del de la API o en paralelo a partir de su Tarea 7.

## Global Constraints

- Todo va en `rebuild/tauri`. No se modifica `src/` original; se **copia**.
- Los comandos se ejecutan desde `rebuild/tauri`. Las pruebas de TypeScript con `npm run test`, las de Rust con `cargo test --manifest-path src-tauri/Cargo.toml` y el build con `npm run build`.
- Los commits siguen la misma regla que en el plan de la API: solo si el usuario aprobó git.
- Plataforma objetivo: Windows 11 con WebView2. El bundle es solo `nsis`.
- `productName` es `"Pulso Laboral"`, `identifier` es `"com.pulsolaboral.desktop"` y `version` es `"0.1.0"`.
- Todo el texto de la interfaz va en español, con tildes.
- Se mantiene la paleta de `src/index.css` (`#B26337`, `#23272E`, `#F7F7F8`, etc.) y las fuentes Plus Jakarta Sans, Public Sans y JetBrains Mono, servidas con @fontsource.
- URL de la API por defecto: `http://localhost:8000`. Se guarda en `config.json` (plugin-store).
- El token va en `session.json`. **No** puede quedar ningún `fetch('/api` ni `href="/api` directo; todo pasa por `src/api/client.ts`.
- La foto se refresca cada 30 000 ms (y no mientras `document.hidden`), además de después de cada acción.
- **Subidas:** como máximo 3 a la vez. Extensiones `.pdf .docx .txt .rtf` y tamaño máximo 15 MB.
- **`normalizeKey`** (TS) da exactamente el mismo resultado que `normalize_key` (Python). Se verifica con los mismos vectores de prueba.
- **Decisiones:** `Pendiente de revisión | Aprobado | Rechazado | Contratado`. Transiciones iguales a `DECISION_TRANSITIONS` del plan de la API.
- **Veredicto:** `Pre-aprobado | Pre-denegado | null`.
- **Estados de IA:** `En cola | Procesando | Clasificado | Error IA | Sin texto | Sin IA`.
- **Se eliminan:** la PWA (`vite-plugin-pwa`, `virtual:pwa-register`), `AppInstallModal`, `usePWAInstall`, `MobileBottomNav`, "Restaurar datos demo" y los instaladores `.cmd`.
- **CSP:** `default-src 'self'; connect-src 'self' ipc: http://ipc.localhost http: https:; img-src 'self' data: blob:; style-src 'self' 'unsafe-inline'; font-src 'self' data:`.

## Review Focus

1. **La API no responde o la URL está mal al ingresar:** debe mostrarse un mensaje claro en español con la URL usada, no una pantalla en blanco. → Tarea 2 (`maps network error to spanish message`).
2. **El token vence en medio de la sesión** (un 401 durante el refresco de 30 s): se vuelve una sola vez a la pantalla de ingreso, sin bucles ni errores encadenados. → Tarea 2 (`401 calls onUnauthorized once`).
3. **La carpeta local se borró, se movió o era un USB que ya no está:** la sincronización informa el error y la app sigue funcionando. → Tarea 1 (`scan_missing_root_errors`) y Tarea 7 (`runSync reports scan error`).
4. **El mismo archivo dos veces dentro de un mismo puesto en la carpeta local** (por ejemplo, en `Perforista/linkedin` y en `Perforista/computrabajo`): se sube una sola vez y la segunda copia se informa como repetida. → Tarea 7 (`dedupes same sha within same position`).
5. **El usuario cancela "Guardar como"** en una descarga: no debe aparecer ningún error ni aviso. → Tarea 2 (`downloadFile returns null on cancel`).

## Estructura de archivos

```
rebuild/tauri/
  package.json  tsconfig.json  vite.config.ts  vitest.config.ts  index.html
  src/main.tsx  src/App.tsx  src/index.css  src/types.ts
  src/api/{config,session,client}.ts            src/api/client.test.ts
  src/auth/{AuthProvider,LoginScreen,RegisterScreen,ServerDialog}.tsx
  src/utils/{labels,decisions,orgTree,auditQuery,backup}.ts (+ *.test.ts)
  src/sync/{folderMatch,syncPlan,runSync}.ts    (+ *.test.ts)
  src/components/…  (copiados de ../../src/components y adaptados)
  src/components/common/{DownloadButton,Toast,ServerStatusIndicator}.tsx
  src/components/cv/{UploadCvDialog,CvFolderModule,SyncSummaryDialog}.tsx
  src/components/org/{OrgChartModule,OrgTree,OrgChartView,PositionForm}.tsx
  src/components/{RequirementsSelectionModule,AuditLogModule,SettingsModule,PersonPanel,CandidateHistory}.tsx
  src-tauri/Cargo.toml build.rs tauri.conf.json capabilities/default.json icons/
  src-tauri/src/{main,lib,files,cv_folder}.rs
```

---

### Task 1: Proyecto Tauri con la interfaz copiada y comandos de archivos en Rust

**Files:**
- Create: `package.json`, `tsconfig.json`, `vite.config.ts`, `vitest.config.ts`, `index.html`, `src/main.tsx`, `src-tauri/**`
- Copy: `../../src/**` → `src/`, **excepto** `hooks/usePWAInstall.ts`, `components/AppInstallModal.tsx`, `components/MobileBottomNav.tsx`, `word-extractor.d.ts`, `utils/cvParser.ts` y `utils/recruitment.test.ts`.
- Modify: `src/App.tsx` (quitar las referencias a lo excluido) y `src/main.tsx` (sin `registerSW`)
- Test: pruebas `#[cfg(test)]` en `src-tauri/src/cv_folder.rs` y `files.rs`

**Interfaces** (comandos registrados en `lib.rs::run()`; las estructuras usan `#[serde(rename_all = "camelCase")]`):
- `scan_cv_folder(root: String) -> Result<ScanResult, String>`:
  - `ScanResult { root_used, entries: Vec<ScanEntry>, skipped: Vec<SkippedEntry> }`
  - `ScanEntry { position_folder, source_folder, path, file_name, size: u64, sha256, extension }`
  - `SkippedEntry { path, reason }`, con `reason` igual a `"estructura"`, `"formato"` o `"tamaño"`.
  - Si `root` contiene una subcarpeta llamada `rrhh` (sin distinguir mayúsculas), usa esa.
  - Solo acepta archivos a profundidad `puesto/fuente/archivo`.
  - Error: `"La carpeta {root} no existe o no es accesible"`.
- `create_folder_structure(root: String, folders: Vec<(String, String)>) -> Result<u32, String>`: devuelve cuántas carpetas creó, sin contar las que ya existían.
- `save_file(request: tauri::ipc::Request) -> Result<(), String>`: el cuerpo trae los bytes en crudo y el header `x-path`, codificado con percent-encoding.
- `open_temp_file(request: tauri::ipc::Request) -> Result<String, String>`: recibe el header `x-file-name`, escribe en `%TEMP%/pulso-laboral/`, abre con `OpenerExt::open_path` y devuelve la ruta.
- `open_path(path: String) -> Result<(), String>`
- `read_file_bytes(path: String) -> Result<tauri::ipc::Response, String>`

- [ ] **Step 1: Crear el proyecto.**
  - `npm init -y`
  - `npm i react@19 react-dom@19 lucide-react @tauri-apps/api@^2 @tauri-apps/plugin-dialog@^2 @tauri-apps/plugin-store@^2 @tauri-apps/plugin-opener@^2 @fontsource/plus-jakarta-sans @fontsource/public-sans @fontsource/jetbrains-mono`
  - `npm i -D vite @vitejs/plugin-react typescript tailwindcss@^4 @tailwindcss/vite vitest jsdom @types/react @types/react-dom @tauri-apps/cli@^2`
  - Scripts:
    - `dev: vite`
    - `build: tsc --noEmit && vite build`
    - `test: vitest run`
    - `tauri: tauri`
  - `vite.config.ts`: puerto `1420` con `strictPort`, `clearScreen: false` y los plugins de React y Tailwind.
  - `tsconfig.json`: `strict`, `noEmit`, `jsx: react-jsx`, `moduleResolution: bundler` y `allowImportingTsExtensions: true`. Esta última hace falta porque `seedData.ts` y `recruitment.ts` importan con extensión `.ts` hasta que la Tarea 2 los borra.
  - `src-tauri`:
    - dependencias: `tauri@2`, `tauri-plugin-dialog`, `tauri-plugin-store`, `tauri-plugin-opener`, `serde`, `sha2`, `hex`, `walkdir` y `percent-encoding`; en desarrollo, `tempfile`;
    - la CSP de las restricciones globales;
    - capabilities `core:default`, `dialog:default`, `store:default` y `opener:default`;
    - iconos generados con `npx tauri icon ../../public/pwa-512x512.png`.
- [ ] **Step 2: Escribir las pruebas de Rust que fallan.**
  - `scan_finds_entries_and_hashes`: con un tempdir `rrhh/Perforista/LinkedIn/a.pdf` cuyo contenido es `abc` → `root_used` termina en `rrhh`, la entrada tiene `position_folder == "Perforista"` y `sha256 == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"`.
  - `scan_skips_wrong_depth_and_formats`: `x.pdf` en la raíz → `"estructura"`; `P/S/a.doc` → `"formato"`.
  - `scan_missing_root_errors`.
  - `create_folder_structure_is_idempotent`: la primera llamada devuelve 2 y la segunda 0.
- [ ] **Step 3: Comprobar que fallan.** `cargo test --manifest-path src-tauri/Cargo.toml` → FAIL.
- [ ] **Step 4: Implementar** los comandos y copiar la interfaz.
- [ ] **Step 5: Verificar.**
  - `cargo test …` da PASS.
  - `npm run build` termina sin errores. La interfaz copiada compila tal cual.
  - `npm run tauri dev` abre la ventana "Pulso Laboral".
- [ ] **Step 6: Commit.** `feat(app): proyecto Tauri con interfaz copiada y comandos de archivos`.

### Task 2: Contrato, cliente de API, sesión y pantallas de ingreso

**Files:**
- Create: `src/api/{config,session,client}.ts`, `src/auth/{AuthProvider,LoginScreen,RegisterScreen,ServerDialog}.tsx`, `src/components/common/{ServerStatusIndicator,Toast}.tsx`, `src/utils/labels.ts`
- Modify:
  - `src/types.ts`: se reescribe según el "Contrato de la foto" del plan de la API.
  - `src/App.tsx`: se reescribe como el armazón de la app.
  - Componentes copiados: solo los ajustes mecánicos para que compilen. `aiProposedDecision` pasa a `aiVerdict`, y las decisiones viejas a las nuevas usando `labels.ts`.
- Delete: `src/data/seedData.ts`, `src/utils/recruitment.ts` y `src/components/OfflineIndicator.tsx`
- Test: `src/api/client.test.ts`

**Interfaces:**
- Produces:
  - `type AppConfig = { apiBaseUrl: string; cvFolder: string | null; syncOnOpen: boolean }`
  - `loadConfig(): Promise<AppConfig>` y `saveConfig(patch: Partial<AppConfig>): Promise<AppConfig>`. Valores por defecto: `{ apiBaseUrl: 'http://localhost:8000', cvFolder: null, syncOnOpen: true }`.
  - `getToken(): Promise<string | null>` y `setToken(t: string | null): Promise<void>`.
  - `class ApiError extends Error { status: number; code?: string; detail?: unknown }`
  - `apiFetch<T>(path: string, opts?: { method?: string; json?: unknown; form?: FormData; signal?: AbortSignal }): Promise<T>`:
    - Agrega el header `Bearer`.
    - Un error de red se convierte en `ApiError(0, 'No se pudo conectar con el servidor ({apiBaseUrl}). Revisa la URL en "Servidor" y que la API esté encendida.')`.
    - Si `detail` es un string, se usa como mensaje. Si es `{code, message}`, se toman los dos. Si es una lista de 422, se usa el `msg` del primer elemento.
    - Ante un 401, llama a los listeners de `onUnauthorized` **una sola vez** hasta el próximo `setToken`.
  - `onUnauthorized(cb: () => void): () => void`
  - `apiBlob(path: string): Promise<{ blob: Blob; fileName: string | null }>`: toma el nombre de `filename*=UTF-8''…` o, si no está, de `filename=`.
  - `downloadFile(path: string, suggestedName: string): Promise<string | null>`:
    - Abre el diálogo `save({ defaultPath: suggestedName })`.
    - Si el usuario cancela, devuelve `null` sin errores.
    - Si no, ejecuta `invoke('save_file', bytes, { headers: { 'x-path': encodeURIComponent(p) } })` y devuelve la ruta.
  - `openRemoteFile(path: string, fallbackName: string): Promise<void>`: usa `apiBlob` y luego `invoke('open_temp_file', …)`.
  - `errorMessage(e: unknown): string`
  - `AuthProvider` y `useAuth()`, que exponen `{ status: 'loading'|'anonymous'|'authenticated'; user: UserOut | null; login(email, password); register({fullName, email, password, jobTitle, inviteCode?}); logout() }`.
  - `AppSection = 'candidatos'|'organigrama'|'requerimientos'|'carpeta'|'psicologicas'|'procesos'|'reportes'|'bitacora'|'configuracion'`
  - `App.tsx`:
    - Sin sesión → `LoginScreen` o `RegisterScreen`, con un enlace a `ServerDialog` para editar y probar la URL contra `GET /api/health`.
    - Con sesión → carga la foto con `refreshState()` y monta un `setInterval` de 30 000 ms.
    - La barra de contexto muestra `Sesión: {fullName} ({jobTitle})`, "Cerrar sesión", "Texto Grande", `ServerStatusIndicator` y una insignia de la cola de IA: `queued` y, si existe, `pausedUntil` en hora local.
  - En `labels.ts`: `decisionTone(d: CandidateDecision): 'success'|'danger'|'neutral'|'warning'`, `verdictLabel(v: AiVerdict | null): string` y `aiStatusTone(s: AiStatus)`.
- [ ] **Step 1: Escribir las pruebas que fallan,** con Vitest, `fetch` simulado y `vi.mock` de `@tauri-apps/plugin-store`, `plugin-dialog` y `api/core`:
  - `maps network error to spanish message`: `fetch` lanza `TypeError` → `ApiError` con `status 0` y un mensaje que contiene `'http://localhost:8000'`.
  - `401 calls onUnauthorized once`: dos llamadas con 401 → el listener se llama una sola vez.
  - `parses detail object code`: un 409 con `{detail: {code: 'duplicate', message: 'x'}}` → `code === 'duplicate'` y mensaje `'x'`.
  - `parses 422 list`: el mensaje es el `msg` del primer elemento.
  - `apiBlob parses utf8 filename`: `filename*=UTF-8''CV%20Jos%C3%A9.pdf` → `'CV José.pdf'`.
  - `downloadFile returns null on cancel`: `save` simulado devuelve `null` → `null` y `invoke` no se llama.
- [ ] **Step 2: Comprobar que fallan.** `npm run test -- src/api/client.test.ts` → FAIL.
- [ ] **Step 3: Implementar,** incluidos los ajustes mecánicos de los componentes.
- [ ] **Step 4: Verificar.**
  - `npm run test` da PASS y `npm run build` no muestra errores.
  - Manual, con la API de compose levantada:
    1. `npm run tauri dev`;
    2. registrar una cuenta;
    3. comprobar que se ve la foto vacía o la de la demo;
    4. detener la API y comprobar que el indicador muestra "Sin conexión con el servidor".
- [ ] **Step 5: Commit.** `feat(app): sesión, cliente de API y contrato de la foto`.

### Task 3: Descargas y apertura de archivos en todos los módulos

**Files:**
- Create: `src/components/common/DownloadButton.tsx`
- Modify: los enlaces `/api` de los componentes copiados:
  - `CandidatesDashboard.tsx` (líneas originales 314, 858, 867)
  - `HeaderNav.tsx` (72)
  - `ProcessesKPIModule.tsx` (65)
  - `PsychTestsModule.tsx` (583, 694, 1129, 1352, 1587)
  - `ReportsExportModule.tsx` (221, 243, 265, 302, 346, 401; los bloques de 442 y 450 se **eliminan**)
  - `VacanciesSelectionModule.tsx` (676)

**Interfaces:**
- Consumes: `downloadFile`, `openRemoteFile` e `invoke('open_path')` (Tarea 2).
- Produces: `<DownloadButton path={string} fileName={string} label={string} variant?="primary"|"ghost" />`. Muestra un estado de "ocupado" y, al terminar, el aviso "Guardado en {ruta}" con un botón "Abrir".
  - Rutas y nombres sugeridos:
    - `/api/reports/admin-doc` → `Informe_Ejecutivo.doc`
    - `/api/reports/candidate/{id}/doc` → `Ficha_{fullName}.doc`
    - `/api/reports/candidates-csv` → `Candidatos.csv`
    - `/api/reports/kpis-csv` → `KPIs_Procesos.csv`
    - `/api/datacenter/backup` → `Respaldo_Pulso_Laboral.json`
    - `/api/tests/excel-template?…` → `Plantilla_Prueba.xlsx`
  - El CV usa `/api/cv-files/{cvFileId}/download`: "Ver CV" lo abre con `openRemoteFile` y "Descargar CV" lo guarda con `DownloadButton`.
- [ ] **Step 1: Escribir la verificación que falla.** `grep -rnE "href=\{?[\"'\`]/api|fetch\(['\"\`]/api" src` → hoy encuentra coincidencias.
- [ ] **Step 2: Reemplazar** cada enlace por `DownloadButton` u `openRemoteFile`.
- [ ] **Step 3: Verificar.**
  - El mismo `grep` no devuelve ninguna coincidencia.
  - `npm run build` termina sin errores.
  - Manual: descargar el informe ejecutivo, cancelar un "Guardar como" (no debe aparecer ningún aviso) y abrir un CV.
- [ ] **Step 4: Commit.** `feat(app): descargas autenticadas con diálogo Guardar como`.

### Task 4: Candidatos y Requerimientos y Selección

**Files:**
- Create: `src/components/cv/UploadCvDialog.tsx`, `src/components/RequirementsSelectionModule.tsx` (a partir de `VacanciesSelectionModule.tsx`, que se borra), `src/components/{PersonPanel,CandidateHistory}.tsx`, `src/utils/decisions.ts`
- Modify: `src/components/CandidatesDashboard.tsx`
- Test: `src/utils/decisions.test.ts`

**Interfaces:**
- Consumes:
  - De la API: `POST /api/cv-files` (multipart), `POST /api/candidates`, `PATCH /api/persons/{id}`, `POST /api/persons/{id}/merge`, `POST /api/candidates/{id}/decision`, `POST /api/candidates/{id}/reclassify`, `POST/PATCH /api/requirements`, `GET /api/audit?entityType=candidate&entityId=…` y `POST /api/ai/{evaluate-candidate,assistant-chat,vote-response}`.
  - De la Tarea 1, `invoke('read_file_bytes')`.
- Produces:
  - `DECISION_TRANSITIONS: Record<CandidateDecision, CandidateDecision[]>`: copia exacta de la del plan de la API.
  - `allowedNextDecisions(d: CandidateDecision): CandidateDecision[]`
  - `agreeWithAi(v: AiVerdict | null): CandidateDecision | null`: `'Pre-aprobado'` da `'Aprobado'`, `'Pre-denegado'` da `'Rechazado'` y `null` da `null`.
  - `sortSelectionQueue(c: Candidate[]): Candidate[]`: ordena por `aiAptitudeScore` descendente (los `null` al final) y, en empate, por `metricReport.overallScore` descendente.
  - `<UploadCvDialog open positions sources requirements initialPositionId? initialSourceId? onDone(state) onClose />`:
    - El usuario elige el puesto, la fuente y, si el puesto tiene más de un requerimiento abierto, el requerimiento.
    - Para elegir archivos usa `open({ multiple: true, filters: [{ name: 'CV', extensions: ['pdf','docx','txt','rtf'] }] })`.
    - Lee cada archivo con `read_file_bytes` y lo sube uno a uno.
    - Muestra el resultado por archivo: creado, repetido (con `existing`), eliminado antes, o un error con su mensaje.
  - **CandidatesDashboard:**
    - Una fila por postulación, con nuevas columnas "IA" (estado, veredicto y aptitud) y filtros por estado de IA y por veredicto.
    - "Subir CV" abre `UploadCvDialog`.
    - "Nuevo candidato" queda como alta manual con `POST /api/candidates`, sin leer CV.
    - La ficha muestra `PersonPanel` (datos editables, "Unir" con posible misma persona, otras postulaciones) y `CandidateHistory`.
  - **RequirementsSelectionModule:**
    - Formulario "Nuevo requerimiento": puesto del organigrama, plazas (1-500), urgencia, plazo en días, contexto, competencias extra y fuentes.
    - Lista con "Plazas: filledCount/vacancies", estado y Cancelar/Reabrir.
    - Bandeja filtrada por requerimiento o puesto y ordenada con `sortSelectionQueue`.
    - Panel de decisión:
      - botón "De acuerdo con la IA ({Aprobar|Rechazar})", deshabilitado si no hay veredicto;
      - botones según `allowedNextDecisions`;
      - para "Contratar", si la postulación no tiene requerimiento, pide uno y lo envía como `requirementId`.
    - Se conservan el bloque "Retroalimentar criterio a la IA", el informe, el chat y los votos de hoy.
    - Los errores 429 y 503 muestran el mensaje de la API.
    - Botón "Reclasificar con IA".
- [ ] **Step 1: Escribir las pruebas que fallan.**
  - `allowedNextDecisions matches API matrix`: las 4 entradas.
  - `agreeWithAi maps verdicts`.
  - `sortSelectionQueue orders by aptitude then overall`: `[null/90, 80/70, 80/85]` → `[80/85, 80/70, null/90]`.
- [ ] **Step 2: Comprobar que fallan.** `npm run test -- src/utils/decisions.test.ts` → FAIL.
- [ ] **Step 3: Implementar.**
- [ ] **Step 4: Verificar.**
  - `npm run test` y `npm run build` dan PASS.
  - Manual contra la API con la demo cargada:
    1. Subir 2 CVs ficticios.
    2. Confirmar que subir el mismo archivo de nuevo muestra "ya existe".
    3. Aprobar con la cuenta A.
    4. Contratar con la cuenta B.
    5. Confirmar que las plazas suben a 1/N.
- [ ] **Step 5: Commit.** `feat(app): candidatos por postulación y flujo de decisión humana`.

### Task 5: Pruebas, Procesos KPI, Reportes y navegación

**Files:**
- Modify: `src/components/{PsychTestsModule,ProcessesKPIModule,ReportsExportModule,HeaderNav}.tsx`
- Create: `src/utils/backup.ts`
- Test: `src/utils/backup.test.ts`

**Interfaces:**
- Produces:
  - `parseBackupFile(text: string): { ok: true; backup: unknown } | { ok: false; error: string }`. Para ser válido, el JSON debe tener `version === 1` y un objeto `data`. Si no, el error es `'El archivo no es un respaldo válido de Pulso Laboral'`.
  - **PsychTestsModule:**
    - El alta de candidato con CV se reemplaza por `UploadCvDialog`.
    - Las cargas de Excel van en multipart (`file` leído con `read_file_bytes`) a `import-excel` y `upload-excel`.
    - Se muestran `passed` y `passingScore`.
    - Rótulo "Evaluación de la persona (vale para todas sus postulaciones)".
  - **ProcessesKPIModule:**
    - El envío de propuestas usa `POST /api/sources/{id}/proposals {requirementId}`.
    - "Bolsas" pasa a llamarse "Fuentes".
    - El texto del KPI de acuerdo explica la nueva definición.
  - **ReportsExportModule:**
    - El estado del respaldo se arma con `GET /api/datacenter/status`.
    - Restaurar: se elige el archivo, se valida con `parseBackupFile`, aparece un modal que exige escribir `RESTAURAR` y se envía `POST /api/datacenter/restore`.
    - Se quitan los instaladores de Windows y el kit.
  - **HeaderNav:**
    - Secciones principales: Candidatos, Organigrama, Requerimientos, Carpeta de CVs y Pruebas.
    - Menú "Más": Procesos KPI, Reportes, Bitácora y Configuración.
    - Contador de pendientes: postulaciones en `Pendiente de revisión`.
- [ ] **Step 1: Escribir las pruebas que fallan.** `parseBackupFile rejects invalid` (JSON roto, `version` 2, falta `data`) y `accepts valid`.
- [ ] **Step 2: Comprobar que fallan.** `npm run test -- src/utils/backup.test.ts` → FAIL.
- [ ] **Step 3: Implementar.**
- [ ] **Step 4: Verificar.**
  - `npm run test` y `npm run build` dan PASS.
  - Manual: subir el Excel de una plantilla completada, enviar una propuesta, y descargar y restaurar un respaldo.
- [ ] **Step 5: Commit.** `feat(app): pruebas, KPIs, reportes y navegación adaptados`.

### Task 6: Organigrama

**Files:**
- Create: `src/components/org/{OrgChartModule,OrgTree,OrgChartView,PositionForm}.tsx`, `src/utils/orgTree.ts`
- Test: `src/utils/orgTree.test.ts`

**Interfaces:**
- Consumes: `POST /api/positions`, `PATCH /api/positions/{id}`, `DELETE /api/positions/{id}` y `POST /api/positions/{id}/reclassify`.
- Produces:
  - `type TreeNode = { position: Position; children: TreeNode[] }`
  - `buildTree(positions: Position[]): TreeNode[]`: ordena por `sortOrder` y luego por `name` con `localeCompare('es')`. Un `parentId` que no existe se trata como raíz.
  - `descendantsOf(id: string, positions: Position[]): Set<string>`: incluye el propio id.
  - **El módulo:**
    - Alterna entre "Árbol" (plegable) y "Gráfico" (cajas con conectores en CSS).
    - Cada nodo muestra los requerimientos abiertos y la cantidad de candidatos.
    - Acciones: "+ Puesto raíz", "+ Subordinado", "Editar", "Mover a…" (el selector excluye `descendantsOf`), "Eliminar" (muestra el mensaje 409 de la API), "Crear requerimiento" (lleva a Requerimientos con el puesto preseleccionado) y "Reclasificar puesto con IA".
  - **PositionForm:**
    - Campos: Nombre, Área (lista sugerida o texto libre), Carpeta, Descripción, Competencias clave, Especificaciones técnicas, Años mínimos y Formación esperada.
    - La Carpeta se autocompleta con `normalizeKey(nombre)` hasta que el usuario la edite.
    - Debajo de la Carpeta se ve una vista previa `rrhh/{carpeta}/<fuente>/`.
- [ ] **Step 1: Escribir las pruebas que fallan.**
  - `buildTree nests and sorts`.
  - `orphan parent becomes root`.
  - `descendantsOf includes self and all descendants`.
- [ ] **Step 2: Comprobar que fallan.** `npm run test -- src/utils/orgTree.test.ts` → FAIL.
- [ ] **Step 3: Implementar.** `normalizeKey` viene de la Tarea 7; si esta tarea se ejecuta antes, crear `src/sync/folderMatch.ts` aquí con la interfaz de la Tarea 7.
- [ ] **Step 4: Verificar.**
  - `npm run test` y `npm run build` dan PASS.
  - Manual: crear un subordinado, intentar moverlo debajo de su propio hijo (no debe aparecer como opción) y eliminar una hoja.
- [ ] **Step 5: Commit.** `feat(app): organigrama de puestos`.

### Task 7: Carpeta de CVs, importación y sincronización

**Files:**
- Create: `src/sync/{folderMatch,syncPlan,runSync}.ts`, `src/components/cv/{CvFolderModule,SyncSummaryDialog}.tsx`
- Modify: `src/App.tsx` (sincronizar al abrir)
- Test: `src/sync/folderMatch.test.ts`, `src/sync/syncPlan.test.ts`, `src/sync/runSync.test.ts`

**Interfaces:**
- Consumes:
  - De la Tarea 1: `invoke('scan_cv_folder')`, `invoke('read_file_bytes')` e `invoke('create_folder_structure')`.
  - De la API: `POST /api/cv-files/check`, `POST /api/cv-files`, `PATCH/DELETE /api/cv-files/{id}` y `DELETE /api/cv-files/blocked/{id}`.
- Produces:
  - `normalizeKey(s: string): string`: misma regla que en Python.
  - `matchFolder<T extends { id: string; name: string; folderName: string }>(folder: string, items: T[]): T | null`: compara contra `folderName` y, si no coincide, contra `name`, ambos normalizados.
  - `type MatchedEntry = ScanEntry & { positionId: string; sourceId: string }`
  - `planMatches(scan: ScanResult, positions, sources): { matched: MatchedEntry[]; inScanDuplicates: MatchedEntry[]; unmatchedFolders: { folder: string; kind: 'puesto'|'fuente'; count: number }[] }`: deja una sola entrada por cada par `sha256 + positionId`, la primera.
  - `finalizePlan(matched: MatchedEntry[], results: { sha256; positionId; status: 'new'|'duplicate'|'deleted_before' }[]): { toUpload: MatchedEntry[]; duplicates: MatchedEntry[]; deletedBefore: MatchedEntry[] }`
  - `runSync(opts: { root: string; origin: 'importacion'|'sync_local'; positions; sources; onProgress?: (done: number, total: number) => void }): Promise<SyncSummary>`:
    - `SyncSummary = { uploaded; duplicates; deletedBefore; unmatchedFolders; skipped; errors: { path; message }[] }`.
    - Sube con un máximo de 3 a la vez.
    - Un 409 durante la subida se cuenta como repetido.
    - Un error en una subida se registra y la sincronización sigue con las demás.
    - Si falla el escaneo, devuelve el resumen con `errors: [{ path: root, message }]` y no lanza.
  - **App:** después de la primera carga de la foto, si `cvFolder` está configurado y `syncOnOpen` activo, ejecuta `runSync` con `origin 'sync_local'` y muestra el aviso "Sincronización: {n} nuevos, {m} repetidos…" con un enlace "Ver detalle".
  - **CvFolderModule:**
    - A la izquierda, el árbol `rrhh/` → puesto → fuente, con conteos de las postulaciones que tienen CV.
    - A la derecha, la lista de archivos: nombre, candidato, estado y veredicto de IA, decisión, quién lo subió y cuándo.
    - Acciones por archivo: Ver CV, Mover (puesto y fuente) y Eliminar, con la confirmación "Se borrará el archivo y los datos de {nombre} de este puesto. No se volverá a importar salvo que lo permitas."
    - Barra de herramientas:
      - Subir CVs: `UploadCvDialog` con la selección actual.
      - Importar carpeta: diálogo de directorio y luego `runSync` con `'importacion'`.
      - Sincronizar ahora: con la carpeta configurada; si no hay, lleva a Configuración.
      - Crear estructura local: para los puestos con requerimientos abiertos por cada fuente activa, usando `folderName`.
    - Pestaña "Eliminados", con `blockedCvFiles` y el botón "Permitir reimportar".
    - Aviso de cola de IA si hay `pausedUntil`.
- [ ] **Step 1: Escribir las pruebas que fallan.**
  - `normalizeKey vectors`: los mismos 4 vectores que `test_normalize_key_vectors` del plan de la API.
  - `matchFolder by folderName or name ignoring case/accents/spaces`: `' Operación  Mina '` coincide con el puesto `'Operación Mina'`.
  - `planMatches groups unmatched by kind with counts`.
  - `dedupes same sha within same position`: el mismo hash en `Perforista/linkedin` y en `Perforista/computrabajo` → 1 en `matched` y 1 en `inScanDuplicates`.
  - `same sha different positions uploads twice`.
  - `finalizePlan splits statuses`.
  - `runSync concurrency never exceeds 3`: `apiFetch` simulado con promesas diferidas, contando cuántas hay en vuelo.
  - `runSync counts 409 as duplicate and continues after network error`.
  - `runSync reports scan error`: `invoke` rechaza → `errors[0].message` contiene `'no existe'`.
- [ ] **Step 2: Comprobar que fallan.** `npm run test -- src/sync` → FAIL.
- [ ] **Step 3: Implementar.**
- [ ] **Step 4: Verificar.**
  - `npm run test` y `npm run build` dan PASS.
  - Manual:
    1. Crear la estructura local en una carpeta temporal.
    2. Copiar 3 PDFs ficticios, uno de ellos duplicado en dos fuentes del mismo puesto.
    3. Sincronizar → 2 nuevos y 1 repetido.
    4. Eliminar uno y volver a sincronizar → aparece como "eliminado previamente".
- [ ] **Step 5: Commit.** `feat(app): carpeta de CVs con importación y sincronización local`.

### Task 8: Bitácora y Configuración

**Files:**
- Create: `src/components/{AuditLogModule,SettingsModule}.tsx`, `src/utils/auditQuery.ts`
- Test: `src/utils/auditQuery.test.ts`

**Interfaces:**
- Consumes: `GET /api/audit`, `GET /api/audit/export.csv`, `GET /api/users`, `GET/PATCH /api/settings`, `GET /api/settings/ai-models`, `GET /api/ai/queue`, `POST /api/ai/queue/retry-errors` y `GET /api/health`.
- Produces:
  - `type AuditFilters = { userId?: string; action?: string; entityType?: string; entityId?: string; dateFrom?: string /*YYYY-MM-DD*/; dateTo?: string; q?: string; offset?: number }`
  - `buildAuditQuery(f: AuditFilters, limit = 100): string`: omite los campos vacíos, codifica `q` y convierte `dateFrom` al inicio del día local en ISO UTC y `dateTo` al final del día local en ISO UTC.
  - **AuditLogModule:**
    - Filtros: usuario, acción por prefijo (`auth`, `position`, `requirement`, `source`, `cv`, `person`, `candidate`, `criterion`, `ai`, `psych`, `test`, `report`, `settings`, `datacenter`), fechas y texto.
    - Tabla paginada de 100 filas con fecha local, usuario, acción y resumen; cada fila se expande para ver los detalles en JSON.
    - "Exportar CSV" con `DownloadButton`.
  - **SettingsModule:**
    - Servidor: la URL y "Probar conexión".
    - Carpeta local: elegir directorio, "Sincronizar al abrir" y "Sincronizar ahora".
    - Empresa.
    - IA:
      - modelo, buscable, de `ai-models`;
      - hasta 2 modelos de respaldo;
      - umbral de 50 a 95;
      - IA activada;
      - estado de la cola con "Reintentar errores".
    - Texto fijo: "Modelos gratuitos de OpenRouter: 20 consultas por minuto y 50 por día (1.000 por día si la cuenta compró al menos USD 10 en créditos). Cada CV usa una consulta."
    - Aviso de privacidad sobre los datos personales.
- [ ] **Step 1: Escribir las pruebas que fallan.**
  - `buildAuditQuery omits empty and encodes q`: `{q: 'Juan Pérez'}` da `q=Juan%20P%C3%A9rez&limit=100`.
  - `buildAuditQuery converts local dates to UTC range`.
- [ ] **Step 2: Comprobar que fallan.** `npm run test -- src/utils/auditQuery.test.ts` → FAIL.
- [ ] **Step 3: Implementar.**
- [ ] **Step 4: Verificar.**
  - `npm run test` y `npm run build` dan PASS.
  - Manual: filtrar la bitácora por el usuario B y ver su contratación; cambiar el umbral y ver `settings.update`.
- [ ] **Step 5: Commit.** `feat(app): bitácora y configuración`.

### Task 9: Instalador, verificación de punta a punta y README

**Files:**
- Modify: `src-tauri/tauri.conf.json` (bundle NSIS) y `rebuild/docs/README.md` (sección App)
- Create: `rebuild/docs/verificacion-e2e.md`

- [ ] **Step 1: Generar el instalador.** Ejecutar `npm run tauri build`. Se espera el archivo `src-tauri/target/release/bundle/nsis/Pulso Laboral_0.1.0_x64-setup.exe`.
- [ ] **Step 2: Instalar y probar de punta a punta** contra la API de Docker Compose con la demo cargada. Anotar el resultado de cada paso, con OK o el problema encontrado, en `verificacion-e2e.md`:
  1. Registrar las cuentas A y B.
  2. Crear un puesto y un requerimiento.
  3. Subir un CV desde la app y confirmar que el repetido se rechaza.
  4. Sincronizar una carpeta local de prueba.
  5. Ver la clasificación con la clave real de OpenRouter.
  6. Aprobar con A y contratar con B.
  7. Ver en la bitácora las acciones de los dos.
  8. Descargar los informes y el CV.
  9. Cerrar y volver a abrir la app: la sesión y la configuración se conservan.
  10. Cambiar la URL del servidor a una inválida: aparece el mensaje claro.
- [ ] **Step 3: Escribir la sección App del README:**
  - requisitos: Node 20+, Rust estable, WebView2;
  - `npm install`, `npm run tauri dev` y `npm run tauri build`;
  - cómo apuntar a la API real (Configuración → Servidor);
  - estructura de la carpeta `rrhh/puesto/fuente`.
- [ ] **Step 4: Verificar** que `npm run test`, `cargo test …` y `npm run build` dan PASS.
- [ ] **Step 5: Commit.** `chore(app): instalador NSIS, verificación E2E y README`.
