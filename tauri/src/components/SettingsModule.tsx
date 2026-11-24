import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react';
import {
  Building2,
  Bot,
  CheckCircle2,
  FolderOpen,
  FolderSync,
  PlugZap,
  RefreshCw,
  RotateCcw,
  Save,
  Server,
  Settings,
  ShieldCheck,
  XCircle,
  Search,
} from 'lucide-react';
import { open as openDialog } from '@tauri-apps/plugin-dialog';
import type { AppState, AppSection } from '../types';
import { apiFetch, errorMessage } from '../api/client';
import { loadConfig, normalizeBaseUrl, saveConfig, type AppConfig } from '../api/config';
import { runSync, anyErrorMessage, type SyncSummary } from '../sync/runSync';
import { saveLastSummary } from '../sync/autoSync';
import { Badge, Button, Card, Field, Notice, Spinner, Toggle, formatDateTime, inputClass } from './cv/ui';
import { SyncSummaryDialog } from './cv/SyncSummaryDialog';

export interface SettingsModuleProps {
  state: AppState;
  onState: (s: AppState) => void;
  refresh: () => Promise<void>;
  navigate: (section: AppSection, opts?: { candidateId?: string; positionId?: string }) => void;
}

interface AiModel {
  id: string;
  name: string;
  contextLength?: number;
}

type Msg = { kind: 'success' | 'error' | 'info' | 'warning'; text: string } | null;

const QUOTA_TEXT =
  'Modelos gratuitos de OpenRouter: 20 consultas por minuto y 50 por día (1.000 por día si la cuenta compró al menos USD 10 en créditos). Cada CV usa una consulta.';

function SettingsCard({
  icon,
  title,
  subtitle,
  children,
}: {
  icon: ReactNode;
  title: string;
  subtitle?: string;
  children: ReactNode;
}) {
  return (
    <Card className="p-5">
      <div className="mb-4 flex items-start gap-3 border-b border-[#E2E4E8] pb-4">
        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-[#FBF4EE] text-[#B26337]">{icon}</div>
        <div>
          <h2 className="font-display text-base font-bold text-[#23272E]">{title}</h2>
          {subtitle && <p className="text-xs text-[#5C626D]">{subtitle}</p>}
        </div>
      </div>
      {children}
    </Card>
  );
}

function ModelPicker({
  label,
  value,
  models,
  onChange,
  allowNone,
  exclude = [],
  disabled,
}: {
  label: string;
  value: string;
  models: AiModel[];
  onChange: (id: string) => void;
  allowNone?: boolean;
  exclude?: string[];
  disabled?: boolean;
}) {
  const [filter, setFilter] = useState('');
  const options = useMemo(() => {
    const q = filter.trim().toLowerCase();
    return models.filter(
      (m) => !exclude.includes(m.id) && (!q || m.name.toLowerCase().includes(q) || m.id.toLowerCase().includes(q) || m.id === value),
    );
  }, [models, filter, exclude, value]);
  const inList = !value || models.some((m) => m.id === value);
  return (
    <Field label={label}>
      <div className="space-y-1.5">
        <div className="relative">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-[#9AA0A8]" />
          <input
            className={`${inputClass} min-h-[32px] pl-8 text-xs`}
            placeholder="Filtrar modelos…"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            disabled={disabled}
          />
        </div>
        <select className={inputClass} value={inList ? value : ''} onChange={(e) => onChange(e.target.value)} disabled={disabled}>
          {(allowNone || !inList || !value) && <option value="">{allowNone ? '(Ninguno)' : 'Elige un modelo…'}</option>}
          {options.map((m) => (
            <option key={m.id} value={m.id}>
              {m.name}
              {m.contextLength ? ` · ${Math.round(m.contextLength / 1000)}k` : ''}
            </option>
          ))}
        </select>
        {!inList && value && (
          <span className="block text-xs text-[#8C4722]">
            El modelo guardado ({value}) ya no está en la lista de modelos gratuitos: elige otro.
          </span>
        )}
      </div>
    </Field>
  );
}

export function SettingsModule({ state, onState, refresh }: SettingsModuleProps) {
  // --- Servidor y carpeta local (config.json local) ---
  const [config, setConfig] = useState<AppConfig | null>(null);
  const [url, setUrl] = useState('');
  const [testing, setTesting] = useState(false);
  const [serverMsg, setServerMsg] = useState<Msg>(null);
  const [folderMsg, setFolderMsg] = useState<Msg>(null);
  const [syncing, setSyncing] = useState<{ done: number; total: number } | null>(null);
  const [summary, setSummary] = useState<SyncSummary | null>(null);

  // --- Empresa ---
  const [companyName, setCompanyName] = useState(state.settings?.companyName ?? state.companyName ?? '');
  const [savingCompany, setSavingCompany] = useState(false);
  const [companyMsg, setCompanyMsg] = useState<Msg>(null);

  // --- IA ---
  const s = state.settings;
  const [models, setModels] = useState<AiModel[]>([]);
  const [modelsLoading, setModelsLoading] = useState(false);
  const [modelsError, setModelsError] = useState<string | null>(null);
  const [aiModel, setAiModel] = useState(s?.aiModel ?? '');
  const [fallback1, setFallback1] = useState(s?.aiFallbackModels?.[0] ?? '');
  const [fallback2, setFallback2] = useState(s?.aiFallbackModels?.[1] ?? '');
  const [threshold, setThreshold] = useState<number>(Math.min(95, Math.max(50, s?.aiPreapproveThreshold ?? 70)));
  const [aiEnabled, setAiEnabled] = useState<boolean>(s?.aiEnabled ?? false);
  const [savingAi, setSavingAi] = useState(false);
  const [aiMsg, setAiMsg] = useState<Msg>(null);
  const [queue, setQueue] = useState(state.aiQueue);
  const [retrying, setRetrying] = useState(false);
  const [queueMsg, setQueueMsg] = useState<Msg>(null);

  useEffect(() => {
    loadConfig()
      .then((c) => {
        setConfig(c);
        setUrl(c.apiBaseUrl);
      })
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    setQueue(state.aiQueue);
  }, [state.aiQueue]);

  const loadModels = useCallback(async () => {
    setModelsLoading(true);
    setModelsError(null);
    try {
      const res = await apiFetch<{ models: AiModel[] }>('/api/settings/ai-models');
      setModels(res.models ?? []);
    } catch (e) {
      setModelsError(errorMessage(e));
    } finally {
      setModelsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadModels();
  }, [loadModels]);

  const loadQueue = useCallback(async () => {
    try {
      const q = await apiFetch<AppState['aiQueue']>('/api/ai/queue');
      if (q) setQueue(q);
    } catch {
      /* se usa el de la foto */
    }
  }, []);

  useEffect(() => {
    loadQueue();
    const t = setInterval(() => {
      if (!document.hidden) loadQueue();
    }, 15000);
    return () => clearInterval(t);
  }, [loadQueue]);

  // ---------- Servidor ----------
  async function testConnection() {
    setTesting(true);
    setServerMsg(null);
    const base = normalizeBaseUrl(url);
    try {
      const ctrl = new AbortController();
      const timer = setTimeout(() => ctrl.abort(), 8000);
      const res = await fetch(`${base}/api/health`, { signal: ctrl.signal });
      clearTimeout(timer);
      const body = await res.json().catch(() => null);
      if (res.ok && body?.status === 'ok') {
        setServerMsg({ kind: 'success', text: `Conexión correcta con ${base} (base de datos: ${body.database ?? 'ok'}).` });
      } else {
        setServerMsg({
          kind: 'error',
          text: `El servidor ${base} respondió con error (${res.status})${body?.database === 'error' ? ': la base de datos no responde' : ''}.`,
        });
      }
    } catch {
      setServerMsg({ kind: 'error', text: `No se pudo conectar con ${base}. Revisa la URL y que la API esté encendida.` });
    } finally {
      setTesting(false);
    }
  }

  async function saveServer() {
    const next = await saveConfig({ apiBaseUrl: url });
    setConfig(next);
    setUrl(next.apiBaseUrl);
    setServerMsg({
      kind: 'success',
      text: `URL guardada: ${next.apiBaseUrl}. Si es otro servidor, cierra sesión y vuelve a ingresar con tu cuenta de ese servidor.`,
    });
  }

  // ---------- Carpeta local ----------
  async function chooseFolder() {
    setFolderMsg(null);
    try {
      const dir = await openDialog({ directory: true, multiple: false, title: 'Elige la carpeta local de CVs (rrhh)' });
      if (!dir || Array.isArray(dir)) return;
      const next = await saveConfig({ cvFolder: dir });
      setConfig(next);
      setFolderMsg({ kind: 'success', text: `Carpeta local guardada: ${dir}` });
    } catch (e) {
      setFolderMsg({ kind: 'error', text: anyErrorMessage(e) });
    }
  }

  async function clearFolder() {
    const next = await saveConfig({ cvFolder: null });
    setConfig(next);
    setFolderMsg({ kind: 'info', text: 'Se quitó la carpeta local. La sincronización queda desactivada.' });
  }

  async function toggleSyncOnOpen(v: boolean) {
    const next = await saveConfig({ syncOnOpen: v });
    setConfig(next);
  }

  async function syncNow() {
    if (!config?.cvFolder) {
      setFolderMsg({ kind: 'warning', text: 'Primero elige la carpeta local.' });
      return;
    }
    setFolderMsg(null);
    setSyncing({ done: 0, total: 0 });
    try {
      const res = await runSync({
        root: config.cvFolder,
        origin: 'sync_local',
        positions: state.positions,
        sources: state.jobBoards,
        onProgress: (done, total) => setSyncing({ done, total }),
      });
      saveLastSummary(res);
      setSummary(res);
      try {
        await refresh();
      } catch {
        /* se refresca sola */
      }
    } catch (e) {
      setFolderMsg({ kind: 'error', text: anyErrorMessage(e) });
    } finally {
      setSyncing(null);
    }
  }

  // ---------- Empresa ----------
  async function saveCompany() {
    if (!companyName.trim()) {
      setCompanyMsg({ kind: 'error', text: 'El nombre de la empresa no puede quedar vacío.' });
      return;
    }
    setSavingCompany(true);
    setCompanyMsg(null);
    try {
      const res = await apiFetch<{ state: AppState }>('/api/settings', { method: 'PATCH', json: { companyName: companyName.trim() } });
      onState(res.state);
      setCompanyMsg({ kind: 'success', text: 'Nombre de la empresa guardado.' });
    } catch (e) {
      setCompanyMsg({ kind: 'error', text: errorMessage(e) });
    } finally {
      setSavingCompany(false);
    }
  }

  // ---------- IA ----------
  const modelIds = useMemo(() => new Set(models.map((m) => m.id)), [models]);

  async function saveAi() {
    setAiMsg(null);
    const body: Record<string, unknown> = { aiPreapproveThreshold: threshold, aiEnabled };
    if (models.length > 0) {
      if (aiModel && !modelIds.has(aiModel)) {
        setAiMsg({ kind: 'error', text: 'Elige un modelo de la lista de modelos gratuitos.' });
        return;
      }
      if (aiModel) body.aiModel = aiModel;
      body.aiFallbackModels = [fallback1, fallback2].filter((m, i, arr) => m && modelIds.has(m) && m !== aiModel && arr.indexOf(m) === i);
    }
    setSavingAi(true);
    try {
      const res = await apiFetch<{ state: AppState }>('/api/settings', { method: 'PATCH', json: body });
      onState(res.state);
      setAiMsg({ kind: 'success', text: 'Configuración de la IA guardada.' });
    } catch (e) {
      setAiMsg({ kind: 'error', text: errorMessage(e) });
    } finally {
      setSavingAi(false);
    }
  }

  async function retryErrors() {
    setRetrying(true);
    setQueueMsg(null);
    try {
      const res = await apiFetch<{ state: AppState; requeued?: number }>('/api/ai/queue/retry-errors', { method: 'POST' });
      onState(res.state);
      setQueue(res.state.aiQueue);
      setQueueMsg({
        kind: 'success',
        text: res.requeued ? `Se volvieron a poner en cola ${res.requeued} postulaciones.` : 'No había postulaciones con error para reintentar.',
      });
    } catch (e) {
      setQueueMsg({ kind: 'error', text: errorMessage(e) });
    } finally {
      setRetrying(false);
    }
  }

  const aiConfigured = s?.aiConfigured ?? false;

  return (
    <div className="space-y-5">
      <div className="flex items-start gap-3">
        <div className="mt-0.5 flex h-10 w-10 items-center justify-center rounded-lg bg-[#FBF4EE] text-[#B26337]">
          <Settings className="h-5 w-5" />
        </div>
        <div>
          <h1 className="font-display text-xl font-bold text-[#23272E]">Configuración</h1>
          <p className="mt-0.5 text-sm text-[#5C626D]">Servidor, carpeta local de CVs, datos de la empresa e inteligencia artificial.</p>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">
        <div className="space-y-5">
          <SettingsCard icon={<Server className="h-4 w-4" />} title="Servidor" subtitle="Dirección de la API de Pulso Laboral.">
            <Field label="URL del servidor" hint="Ejemplo: http://localhost:8000 o http://192.168.1.20:8000">
              <input className={`${inputClass} font-mono-tabular`} value={url} onChange={(e) => setUrl(e.target.value)} />
            </Field>
            <div className="mt-3 flex flex-wrap gap-2">
              <Button icon={<PlugZap className="h-4 w-4" />} onClick={testConnection} loading={testing}>
                Probar conexión
              </Button>
              <Button
                variant="primary"
                icon={<Save className="h-4 w-4" />}
                onClick={saveServer}
                disabled={!config || normalizeBaseUrl(url) === config.apiBaseUrl}
              >
                Guardar
              </Button>
            </div>
            {serverMsg && (
              <div className="mt-3">
                <Notice kind={serverMsg.kind} onDismiss={() => setServerMsg(null)}>
                  {serverMsg.text}
                </Notice>
              </div>
            )}
          </SettingsCard>

          <SettingsCard
            icon={<FolderOpen className="h-4 w-4" />}
            title="Carpeta local de CVs"
            subtitle="Carpeta de esta computadora organizada como rrhh/puesto/fuente/ que se sincroniza con el servidor."
          >
            <div className="rounded-lg border border-[#E2E4E8] bg-[#F7F7F8] px-3 py-2.5">
              {config?.cvFolder ? (
                <code className="break-all font-mono-tabular text-xs text-[#23272E]">{config.cvFolder}</code>
              ) : (
                <span className="text-sm text-[#9AA0A8]">No hay carpeta configurada</span>
              )}
            </div>
            <div className="mt-3 flex flex-wrap gap-2">
              <Button icon={<FolderOpen className="h-4 w-4" />} onClick={chooseFolder}>
                {config?.cvFolder ? 'Cambiar carpeta…' : 'Elegir carpeta…'}
              </Button>
              {config?.cvFolder && (
                <Button variant="ghost" onClick={clearFolder}>
                  Quitar
                </Button>
              )}
              <Button
                variant="primary"
                icon={<FolderSync className="h-4 w-4" />}
                onClick={syncNow}
                loading={!!syncing}
                disabled={!config?.cvFolder}
              >
                Sincronizar ahora
              </Button>
            </div>
            {syncing && (
              <p className="mt-2 text-xs text-[#5C626D]">
                {syncing.total ? `Subiendo ${syncing.done} de ${syncing.total} archivos…` : 'Revisando la carpeta…'}
              </p>
            )}
            <div className="mt-4">
              <Toggle
                checked={config?.syncOnOpen ?? true}
                onChange={toggleSyncOnOpen}
                disabled={!config}
                label="Sincronizar al abrir"
                description="Al abrir la app se suben los CV nuevos de la carpeta local. Los repetidos y los eliminados no se suben."
              />
            </div>
            {folderMsg && (
              <div className="mt-3">
                <Notice kind={folderMsg.kind} onDismiss={() => setFolderMsg(null)}>
                  {folderMsg.text}
                </Notice>
              </div>
            )}
          </SettingsCard>

          <SettingsCard icon={<Building2 className="h-4 w-4" />} title="Empresa" subtitle="Aparece en los informes y documentos.">
            <Field label="Nombre de la empresa">
              <input className={inputClass} value={companyName} onChange={(e) => setCompanyName(e.target.value)} />
            </Field>
            <div className="mt-3">
              <Button
                variant="primary"
                icon={<Save className="h-4 w-4" />}
                onClick={saveCompany}
                loading={savingCompany}
                disabled={companyName.trim() === (state.settings?.companyName ?? state.companyName)}
              >
                Guardar
              </Button>
            </div>
            {companyMsg && (
              <div className="mt-3">
                <Notice kind={companyMsg.kind} onDismiss={() => setCompanyMsg(null)}>
                  {companyMsg.text}
                </Notice>
              </div>
            )}
          </SettingsCard>
        </div>

        <div className="space-y-5">
          <SettingsCard
            icon={<Bot className="h-4 w-4" />}
            title="Inteligencia artificial"
            subtitle="Clasificación automática de CV con modelos gratuitos de OpenRouter."
          >
            {!aiConfigured && (
              <div className="mb-4">
                <Notice kind="warning">
                  La IA no está configurada en el servidor (falta OPENROUTER_API_KEY). Los CV se registran igual, pero quedan
                  como «Sin IA» hasta que se configure.
                </Notice>
              </div>
            )}
            <div className="space-y-4">
              <Toggle
                checked={aiEnabled}
                onChange={setAiEnabled}
                label="IA activada"
                description="Si la desactivas, los CV nuevos quedan como «Sin IA» y la decisión es solo manual."
              />

              {modelsLoading ? (
                <Spinner label="Cargando modelos gratuitos…" />
              ) : modelsError ? (
                <Notice
                  kind="error"
                  action={
                    <Button size="sm" icon={<RefreshCw className="h-3.5 w-3.5" />} onClick={loadModels}>
                      Reintentar
                    </Button>
                  }
                >
                  No se pudo obtener la lista de modelos: {modelsError}
                </Notice>
              ) : models.length === 0 ? (
                <Notice kind="warning">OpenRouter no devolvió modelos gratuitos en este momento.</Notice>
              ) : (
                <>
                  <ModelPicker label="Modelo principal" value={aiModel} models={models} onChange={setAiModel} />
                  <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                    <ModelPicker
                      label="Respaldo 1 (opcional)"
                      value={fallback1}
                      models={models}
                      onChange={setFallback1}
                      allowNone
                      exclude={[aiModel, fallback2].filter(Boolean)}
                    />
                    <ModelPicker
                      label="Respaldo 2 (opcional)"
                      value={fallback2}
                      models={models}
                      onChange={setFallback2}
                      allowNone
                      exclude={[aiModel, fallback1].filter(Boolean)}
                      disabled={!fallback1}
                    />
                  </div>
                  <p className="text-xs text-[#5C626D]">
                    Solo se pueden elegir modelos gratuitos ({models.length} disponibles). Si el principal falla o está
                    saturado, se usan los de respaldo en orden.
                  </p>
                </>
              )}

              <Field
                label={`Umbral de pre-aprobación: ${threshold}`}
                hint="Con una aptitud igual o mayor al umbral, la IA marca «Pre-aprobado»; por debajo, «Pre-denegado». La decisión final siempre es humana."
              >
                <div className="flex items-center gap-3">
                  <input
                    type="range"
                    min={50}
                    max={95}
                    step={1}
                    value={threshold}
                    onChange={(e) => setThreshold(Number(e.target.value))}
                    className="flex-1 accent-[#B26337]"
                  />
                  <input
                    type="number"
                    min={50}
                    max={95}
                    value={threshold}
                    onChange={(e) => setThreshold(Math.min(95, Math.max(50, Number(e.target.value) || 50)))}
                    className={`${inputClass} w-20 text-center font-mono-tabular`}
                  />
                </div>
              </Field>

              <Notice kind="info">{QUOTA_TEXT}</Notice>

              <div>
                <Button variant="primary" icon={<Save className="h-4 w-4" />} onClick={saveAi} loading={savingAi}>
                  Guardar configuración de IA
                </Button>
              </div>
              {aiMsg && (
                <Notice kind={aiMsg.kind} onDismiss={() => setAiMsg(null)}>
                  {aiMsg.text}
                </Notice>
              )}
            </div>
          </SettingsCard>

          <SettingsCard icon={<RefreshCw className="h-4 w-4" />} title="Cola de la IA" subtitle="Estado de las clasificaciones pendientes.">
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              {[
                { label: 'En cola', value: queue?.queued ?? 0, tone: 'text-[#2F4A6B]' },
                { label: 'Procesando', value: queue?.processing ?? 0, tone: 'text-[#8A6100]' },
                { label: 'Con error', value: queue?.errors ?? 0, tone: (queue?.errors ?? 0) > 0 ? 'text-[#B42318]' : 'text-[#23272E]' },
                { label: 'Sin IA', value: queue?.sinIa ?? 0, tone: 'text-[#5C626D]' },
              ].map((k) => (
                <div key={k.label} className="rounded-lg border border-[#E2E4E8] px-3 py-2.5">
                  <div className="text-xs text-[#5C626D]">{k.label}</div>
                  <div className={`font-mono-tabular text-xl font-bold ${k.tone}`}>{k.value}</div>
                </div>
              ))}
            </div>
            <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-[#5C626D]">
              {queue?.aiEnabled ? (
                <Badge tone="green">
                  <CheckCircle2 className="h-3 w-3" /> IA en funcionamiento
                </Badge>
              ) : (
                <Badge tone="neutral">
                  <XCircle className="h-3 w-3" /> IA inactiva
                </Badge>
              )}
              {queue?.model && (
                <span>
                  Modelo: <code className="font-mono-tabular text-[#23272E]">{queue.model}</code>
                </span>
              )}
            </div>
            {queue?.pausedUntil && (
              <div className="mt-3">
                <Notice kind="warning">
                  Cola en pausa hasta {formatDateTime(queue.pausedUntil)} por el límite de consultas de OpenRouter. Se
                  reanuda sola.
                </Notice>
              </div>
            )}
            <div className="mt-3 flex gap-2">
              <Button
                icon={<RotateCcw className="h-4 w-4" />}
                onClick={retryErrors}
                loading={retrying}
                disabled={(queue?.errors ?? 0) + (queue?.sinIa ?? 0) === 0}
              >
                Reintentar errores
              </Button>
              <Button variant="ghost" icon={<RefreshCw className="h-4 w-4" />} onClick={loadQueue}>
                Actualizar
              </Button>
            </div>
            {queueMsg && (
              <div className="mt-3">
                <Notice kind={queueMsg.kind} onDismiss={() => setQueueMsg(null)}>
                  {queueMsg.text}
                </Notice>
              </div>
            )}
          </SettingsCard>

          <SettingsCard icon={<ShieldCheck className="h-4 w-4" />} title="Privacidad de los datos">
            <p className="text-sm leading-relaxed text-[#23272E]">
              Los CV contienen datos personales (nombre, documento, contacto, historial laboral). Se guardan solo en el
              servidor de la empresa. Cuando la IA está activada, el texto del CV se envía a OpenRouter y al proveedor del
              modelo elegido para clasificarlo; los modelos gratuitos pueden usar ese contenido para mejorar sus servicios.
              Si no deseas compartir estos datos con terceros, desactiva la IA. Usa la app solo con fines de selección de
              personal y elimina los CV que ya no correspondan.
            </p>
          </SettingsCard>
        </div>
      </div>

      {summary && <SyncSummaryDialog summary={summary} onClose={() => setSummary(null)} />}
    </div>
  );
}

export default SettingsModule;
