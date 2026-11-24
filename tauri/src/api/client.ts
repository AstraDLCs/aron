import { invoke } from '@tauri-apps/api/core';
import { save, open } from '@tauri-apps/plugin-dialog';
import { loadConfig, isTauri } from './config';
import { getToken, fireUnauthorized } from './session';

export { onUnauthorized } from './session';

export class ApiError extends Error {
  status: number;
  code?: string;
  detail?: unknown;
  constructor(status: number, message: string, code?: string, detail?: unknown) {
    super(message);
    this.status = status;
    this.code = code;
    this.detail = detail;
  }
}

export type ApiOpts = { method?: string; json?: unknown; form?: FormData; signal?: AbortSignal };

function statusMessage(status: number): string {
  if (status === 401) return 'Tu sesión venció o no es válida. Vuelve a ingresar.';
  if (status === 403) return 'No tienes permiso para realizar esta acción.';
  if (status === 404) return 'No se encontró el recurso solicitado en el servidor.';
  if (status === 429) return 'Se alcanzó el límite de uso de la IA. Intenta más tarde.';
  if (status === 503) return 'El servicio no está disponible en este momento.';
  if (status >= 500) return `Error interno del servidor (${status}).`;
  return `Error ${status} del servidor.`;
}

async function parseError(res: Response): Promise<ApiError> {
  let body: any = null;
  try {
    const text = await res.text();
    body = text ? JSON.parse(text) : null;
  } catch {
    body = null;
  }
  const detail = body?.detail ?? body;
  if (typeof detail === 'string') return new ApiError(res.status, detail, undefined, detail);
  if (Array.isArray(detail) && detail.length) {
    const first = detail[0];
    const msg = String(first?.msg ?? statusMessage(res.status));
    return new ApiError(res.status, msg, 'validation', detail);
  }
  if (detail && typeof detail === 'object') {
    const msg = (detail as any).message ?? (detail as any).msg ?? statusMessage(res.status);
    return new ApiError(res.status, String(msg), (detail as any).code, detail);
  }
  return new ApiError(res.status, statusMessage(res.status));
}

async function rawFetch(path: string, opts: ApiOpts = {}): Promise<Response> {
  const cfg = await loadConfig();
  const token = await getToken();
  const headers: Record<string, string> = { Accept: 'application/json' };
  if (token) headers.Authorization = `Bearer ${token}`;
  let body: BodyInit | undefined;
  if (opts.form) body = opts.form;
  else if (opts.json !== undefined) {
    headers['Content-Type'] = 'application/json';
    body = JSON.stringify(opts.json);
  }
  const url = cfg.apiBaseUrl + (path.startsWith('/') ? path : '/' + path);
  let res: Response;
  try {
    res = await fetch(url, { method: opts.method ?? (body ? 'POST' : 'GET'), headers, body, signal: opts.signal });
  } catch (e) {
    if ((e as any)?.name === 'AbortError') throw e;
    throw new ApiError(
      0,
      `No se pudo conectar con el servidor (${cfg.apiBaseUrl}). Revisa la URL en "Servidor" y que la API esté encendida.`,
      'network',
    );
  }
  if (!res.ok) {
    const err = await parseError(res);
    if (res.status === 401 && token && !path.startsWith('/api/auth/')) fireUnauthorized();
    throw err;
  }
  return res;
}

export async function apiFetch<T = any>(path: string, opts: ApiOpts = {}): Promise<T> {
  const res = await rawFetch(path, opts);
  if (res.status === 204) return undefined as T;
  const text = await res.text();
  if (!text) return undefined as T;
  try {
    return JSON.parse(text) as T;
  } catch {
    return text as unknown as T;
  }
}

export function errorMessage(e: unknown): string {
  if (e instanceof ApiError) return e.message;
  if (e instanceof Error) return e.message;
  if (typeof e === 'string') return e;
  return 'Ocurrió un error inesperado.';
}

export function parseContentDisposition(h: string | null): string | null {
  if (!h) return null;
  const star = /filename\*\s*=\s*(?:UTF-8|utf-8)''([^;]+)/.exec(h);
  if (star) {
    try {
      return decodeURIComponent(star[1].trim().replace(/^"|"$/g, ''));
    } catch {
      /* sigue */
    }
  }
  const plain = /filename\s*=\s*"?([^";]+)"?/.exec(h);
  return plain ? plain[1].trim() : null;
}

export async function apiBlob(path: string): Promise<{ blob: Blob; fileName: string | null }> {
  const res = await rawFetch(path, {});
  const blob = await res.blob();
  return { blob, fileName: parseContentDisposition(res.headers.get('content-disposition')) };
}

function browserDownload(blob: Blob, name: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = name;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 5000);
}

/** Descarga con diálogo "Guardar como". Devuelve la ruta guardada o null si el usuario cancela. */
export async function downloadFile(path: string, suggestedName: string): Promise<string | null> {
  if (!isTauri()) {
    const { blob, fileName } = await apiBlob(path);
    browserDownload(blob, fileName || suggestedName);
    return fileName || suggestedName;
  }
  const target = await save({ defaultPath: suggestedName });
  if (!target) return null;
  const { blob } = await apiBlob(path);
  const bytes = new Uint8Array(await blob.arrayBuffer());
  await invoke('save_file', bytes, { headers: { 'x-path': encodeURIComponent(target) } });
  return target;
}

/** Guarda bytes generados localmente con diálogo "Guardar como". */
export async function saveBytes(bytes: Uint8Array, suggestedName: string): Promise<string | null> {
  if (!isTauri()) {
    browserDownload(new Blob([bytes as BlobPart]), suggestedName);
    return suggestedName;
  }
  const target = await save({ defaultPath: suggestedName });
  if (!target) return null;
  await invoke('save_file', bytes, { headers: { 'x-path': encodeURIComponent(target) } });
  return target;
}

/** Descarga a una carpeta temporal y abre con la aplicación predeterminada. */
export async function openRemoteFile(path: string, fallbackName: string): Promise<void> {
  const { blob, fileName } = await apiBlob(path);
  const name = fileName || fallbackName;
  if (!isTauri()) {
    window.open(URL.createObjectURL(blob), '_blank');
    return;
  }
  const bytes = new Uint8Array(await blob.arrayBuffer());
  await invoke('open_temp_file', bytes, { headers: { 'x-file-name': encodeURIComponent(name) } });
}

export async function openLocalPath(path: string): Promise<void> {
  if (!isTauri()) return;
  await invoke('open_path', { path });
}

/** Lee un archivo local (ruta absoluta) como bytes vía Rust. */
export async function readLocalFile(path: string): Promise<Uint8Array> {
  const buf = await invoke<ArrayBuffer>('read_file_bytes', { path });
  return new Uint8Array(buf);
}

export function fileNameFromPath(p: string): string {
  return p.split(/[\\/]/).pop() || p;
}

export function mimeFromName(name: string): string {
  const ext = name.toLowerCase().split('.').pop();
  switch (ext) {
    case 'pdf':
      return 'application/pdf';
    case 'docx':
      return 'application/vnd.openxmlformats-officedocument.wordprocessingml.document';
    case 'txt':
      return 'text/plain';
    case 'rtf':
      return 'application/rtf';
    case 'xlsx':
      return 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet';
    case 'json':
      return 'application/json';
    default:
      return 'application/octet-stream';
  }
}

/** Construye un File a partir de una ruta local, listo para FormData. */
export async function fileFromPath(path: string): Promise<File> {
  const bytes = await readLocalFile(path);
  const name = fileNameFromPath(path);
  return new File([bytes as BlobPart], name, { type: mimeFromName(name) });
}

/** Abre el diálogo para elegir archivos locales. Devuelve rutas absolutas (vacío si cancela). */
export async function pickFiles(opts: { multiple?: boolean; name: string; extensions: string[] }): Promise<string[]> {
  const r = await open({ multiple: opts.multiple ?? false, filters: [{ name: opts.name, extensions: opts.extensions }] });
  if (!r) return [];
  return Array.isArray(r) ? r : [r];
}

export type StateResponse<T = object> = { state: import('../types').AppState } & T;
