import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Bot, LogOut, ShieldCheck, Type as TypeIcon, Loader2, RefreshCw, AlertCircle } from 'lucide-react';
import { AuthProvider, useAuth } from './auth/AuthProvider';
import { LoginScreen } from './auth/LoginScreen';
import { RegisterScreen } from './auth/RegisterScreen';
import { apiFetch, errorMessage } from './api/client';
import { loadConfig } from './api/config';
import { HeaderNav } from './components/HeaderNav';
import { ToastHost, toast } from './components/common/Toast';
import { ServerStatusIndicator } from './components/common/ServerStatusIndicator';
import { CandidatesDashboard } from './components/CandidatesDashboard';
import { RequirementsSelectionModule } from './components/RequirementsSelectionModule';
import * as Psych from './components/PsychTestsModule';
import * as Processes from './components/ProcessesKPIModule';
import * as Reports from './components/ReportsExportModule';
import { OrgChartModule } from './components/org/OrgChartModule';
import { CvFolderModule } from './components/cv/CvFolderModule';
import { AuditLogModule } from './components/AuditLogModule';
import { SettingsModule } from './components/SettingsModule';
import { WipeDialog } from './components/WipeDialog';
import { startupSync } from './sync/autoSync';
import { formatTime } from './utils/labels';
import type { AppSection, AppState, ModuleProps } from './types';

// Módulos adaptados por otro agente: se tipan de forma laxa para no acoplar el armazón a su avance.
const PsychTestsModule = (Psych as any).PsychTestsModule as React.ComponentType<any>;
const ProcessesKPIModule = (Processes as any).ProcessesKPIModule as React.ComponentType<any>;
const ReportsExportModule = (Reports as any).ReportsExportModule as React.ComponentType<any>;

const POLL_MS = 30_000;

function Shell() {
  const { user, logout } = useAuth();
  const [state, setState] = useState<AppState | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [online, setOnline] = useState<boolean | null>(null);
  const [apiUrl, setApiUrl] = useState('');
  const [section, setSection] = useState<AppSection>('candidatos');
  const [focusedCandidateId, setFocusedCandidateId] = useState<string | null>(null);
  const [focusedPositionId, setFocusedPositionId] = useState<string | null>(null);
  const [largeText, setLargeText] = useState(() => {
    try {
      return localStorage.getItem('pl-large-text') === '1';
    } catch {
      return false;
    }
  });
  const syncedRef = useRef(false);
  const [wipeOpen, setWipeOpen] = useState(false);

  useEffect(() => {
    void loadConfig().then((c) => setApiUrl(c.apiBaseUrl));
  }, []);

  // Ctrl+Alt+B: borrado total (versión de prueba). Se usa la tecla física para no depender del teclado.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.ctrlKey && e.altKey && !e.shiftKey && !e.metaKey && e.code === 'KeyB') {
        e.preventDefault();
        setWipeOpen(true);
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  useEffect(() => {
    document.documentElement.dataset.largeText = largeText ? 'true' : 'false';
    try {
      localStorage.setItem('pl-large-text', largeText ? '1' : '0');
    } catch {
      /* ignore */
    }
  }, [largeText]);

  const refresh = useCallback(async () => {
    try {
      const s = await apiFetch<AppState>('/api/state');
      setState(s);
      setOnline(true);
      setLoadError(null);
    } catch (e: any) {
      if (e?.status === 0) setOnline(false);
      setLoadError(errorMessage(e));
    }
  }, []);

  const onState = useCallback((s: AppState) => {
    setState(s);
    setOnline(true);
  }, []);

  useEffect(() => {
    void refresh();
    const t = setInterval(() => {
      if (!document.hidden) void refresh();
    }, POLL_MS);
    return () => clearInterval(t);
  }, [refresh]);

  useEffect(() => {
    if (state && !syncedRef.current) {
      syncedRef.current = true;
      startupSync(state, onState).catch((e) => toast(`Sincronización de carpeta: ${errorMessage(e)}`, 'error'));
    }
  }, [state, onState]);

  const navigate = useCallback((s: AppSection, opts?: { candidateId?: string; positionId?: string }) => {
    setFocusedCandidateId(opts?.candidateId ?? null);
    setFocusedPositionId(opts?.positionId ?? null);
    setSection(s);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }, []);

  const pendingReviewCount = useMemo(
    () => (state ? state.candidates.filter((c) => c.decision === 'Pendiente de revisión').length : 0),
    [state],
  );

  if (!state) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#F7F7F8] p-6">
        <div className="w-full max-w-lg rounded-2xl border border-[#E2E4E8] bg-white p-8 text-center shadow-sm">
          {loadError ? (
            <>
              <AlertCircle className="mx-auto mb-3 h-8 w-8 text-red-500" />
              <h2 className="font-display text-lg font-bold">No se pudo cargar la información</h2>
              <p className="mt-2 text-sm text-[#5C626D]">{loadError}</p>
              <div className="mt-5 flex justify-center gap-2">
                <button type="button" onClick={() => void refresh()} className="inline-flex items-center gap-1.5 rounded-lg bg-[#B26337] px-4 py-2 text-sm font-semibold text-white hover:bg-[#99522B]">
                  <RefreshCw className="h-4 w-4" /> Reintentar
                </button>
                <button type="button" onClick={() => void logout()} className="rounded-lg border border-[#D4D7DD] px-4 py-2 text-sm font-semibold text-[#23272E] hover:bg-[#EFEFF1]">
                  Cerrar sesión
                </button>
              </div>
            </>
          ) : (
            <>
              <Loader2 className="mx-auto mb-3 h-7 w-7 animate-spin text-[#B26337]" />
              <p className="text-sm text-[#5C626D]">Cargando Pulso Laboral…</p>
            </>
          )}
        </div>
      </div>
    );
  }

  const props: ModuleProps = { state, onState, refresh, navigate };
  const q = state.aiQueue;

  return (
    <div className="min-h-screen bg-[#F7F7F8] pb-10 text-[#23272E]">
      <HeaderNav
        activeSection={section}
        onSelectSection={(s) => navigate(s)}
        pendingReviewCount={pendingReviewCount}
        companyName={state.companyName}
      />
      <div className="border-b border-[#E2E4E8] bg-[#EFEFF1]/70">
        <div className="mx-auto flex max-w-[1400px] flex-wrap items-center justify-between gap-3 px-6 py-2">
          <div className="flex items-center gap-2 text-sm text-[#5C626D]">
            <ShieldCheck className="h-4 w-4 shrink-0 text-[#B26337]" />
            <span>
              Sesión: <strong className="font-semibold text-[#23272E]">{user?.fullName ?? state.currentUser.fullName}</strong>
              {(user?.jobTitle || state.currentUser.jobTitle) && <> ({user?.jobTitle || state.currentUser.jobTitle})</>}
            </span>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <span
              title={`Modelo: ${q.model || '—'}`}
              className={`inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-xs font-semibold ${
                !q.aiEnabled
                  ? 'border-[#D4D7DD] bg-white text-[#5C626D]'
                  : q.pausedUntil
                    ? 'border-amber-200 bg-amber-50 text-amber-800'
                    : 'border-[#E6CDBE] bg-[#FBF4EE] text-[#8C4722]'
              }`}
            >
              <Bot className="h-3.5 w-3.5" />
              {!q.aiEnabled
                ? 'IA desactivada'
                : `IA: ${q.queued} en cola${q.processing ? ` · ${q.processing} procesando` : ''}${q.errors ? ` · ${q.errors} con error` : ''}`}
              {q.pausedUntil && ` · pausada hasta ${formatTime(q.pausedUntil)}`}
            </span>
            <ServerStatusIndicator online={online} url={apiUrl} />
            <button
              type="button"
              onClick={() => setLargeText((v) => !v)}
              aria-pressed={largeText}
              className={`inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-xs font-semibold transition-colors ${
                largeText ? 'border-[#B26337] bg-[#FBF4EE] text-[#8C4722]' : 'border-[#D4D7DD] bg-white text-[#5C626D] hover:bg-[#EFEFF1]'
              }`}
            >
              <TypeIcon className="h-3.5 w-3.5" />
              {largeText ? 'Texto Estándar' : 'Texto Grande'}
            </button>
            <button
              type="button"
              onClick={() => void logout()}
              className="inline-flex items-center gap-1.5 rounded-lg border border-[#D4D7DD] bg-white px-2.5 py-1.5 text-xs font-semibold text-[#5C626D] hover:bg-[#EFEFF1] hover:text-[#23272E]"
            >
              <LogOut className="h-3.5 w-3.5" /> Cerrar sesión
            </button>
          </div>
        </div>
      </div>

      <main className="mx-auto w-full min-w-0 max-w-[1400px] px-6 py-6">
        {section === 'candidatos' && <CandidatesDashboard {...props} />}
        {section === 'organigrama' && <OrgChartModule {...props} />}
        {section === 'requerimientos' && (
          <RequirementsSelectionModule {...props} initialCandidateId={focusedCandidateId} initialPositionId={focusedPositionId} />
        )}
        {section === 'carpeta' && <CvFolderModule {...props} />}
        {section === 'psicologicas' && <PsychTestsModule {...props} initialCandidateId={focusedCandidateId} />}
        {section === 'procesos' && <ProcessesKPIModule {...props} />}
        {section === 'reportes' && <ReportsExportModule {...props} />}
        {section === 'bitacora' && <AuditLogModule {...props} />}
        {section === 'configuracion' && <SettingsModule {...props} />}
      </main>
      {wipeOpen && (
        <WipeDialog
          onClose={() => setWipeOpen(false)}
          onDone={(s) => {
            onState(s);
            navigate('candidatos');
          }}
        />
      )}
    </div>
  );
}

function Gate() {
  const { status } = useAuth();
  const [mode, setMode] = useState<'login' | 'register'>('login');
  if (status === 'loading') {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#F7F7F8]">
        <Loader2 className="h-7 w-7 animate-spin text-[#B26337]" />
      </div>
    );
  }
  if (status === 'anonymous') {
    return mode === 'login' ? <LoginScreen onRegister={() => setMode('register')} /> : <RegisterScreen onLogin={() => setMode('login')} />;
  }
  return <Shell />;
}

export default function App() {
  return (
    <AuthProvider>
      <Gate />
      <ToastHost />
    </AuthProvider>
  );
}
