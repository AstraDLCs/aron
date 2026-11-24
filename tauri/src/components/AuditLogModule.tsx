import { Fragment, useCallback, useEffect, useState } from 'react';
import { ChevronDown, ChevronLeft, ChevronRight, Download, FilterX, History, RefreshCw, Search } from 'lucide-react';
import type { AppState, AppSection, UserOut } from '../types';
import { apiFetch, downloadFile, errorMessage } from '../api/client';
import { buildAuditQuery, type AuditFilters } from '../utils/auditQuery';
import { Badge, Button, Card, EmptyState, Field, Notice, SectionHeader, Spinner, formatDateTime, inputClass } from './cv/ui';

export interface AuditLogModuleProps {
  state: AppState;
  onState: (s: AppState) => void;
  refresh: () => Promise<void>;
  navigate: (section: AppSection, opts?: { candidateId?: string; positionId?: string }) => void;
}

interface AuditItem {
  id: string;
  at: string;
  userId: string | null;
  userName?: string | null;
  actorName?: string | null;
  action: string;
  entityType: string | null;
  entityId: string | null;
  summary: string;
  details?: unknown;
  ip?: string | null;
}

const PAGE = 100;

const ACTIONS: { value: string; label: string }[] = [
  { value: '', label: 'Todas las acciones' },
  { value: 'auth', label: 'Ingresos y cuentas' },
  { value: 'position', label: 'Organigrama (puestos)' },
  { value: 'requirement', label: 'Requerimientos' },
  { value: 'source', label: 'Fuentes' },
  { value: 'cv', label: 'CV (subidas, movimientos, eliminaciones)' },
  { value: 'person', label: 'Personas' },
  { value: 'candidate', label: 'Postulaciones y decisiones' },
  { value: 'criterion', label: 'Criterios de selección' },
  { value: 'ai', label: 'Inteligencia artificial' },
  { value: 'psych', label: 'Evaluaciones psicológicas' },
  { value: 'test', label: 'Pruebas técnicas' },
  { value: 'report', label: 'Informes descargados' },
  { value: 'settings', label: 'Configuración' },
  { value: 'datacenter', label: 'Centro de datos' },
  { value: 'audit', label: 'Bitácora' },
];

function actionTone(action: string): 'neutral' | 'accent' | 'green' | 'red' | 'blue' | 'amber' {
  if (/delete|remove|block|reject|failed/.test(action)) return 'red';
  if (/create|upload|register|hire|approve/.test(action)) return 'green';
  if (action.startsWith('ai.')) return 'blue';
  if (action.startsWith('auth.')) return 'neutral';
  if (/update|move|decision|reclassify/.test(action)) return 'amber';
  return 'accent';
}

const EMPTY: AuditFilters = { userId: '', action: '', dateFrom: '', dateTo: '', q: '' };

export function AuditLogModule(_props: AuditLogModuleProps) {
  const [users, setUsers] = useState<UserOut[]>([]);
  const [draft, setDraft] = useState<AuditFilters>(EMPTY);
  const [filters, setFilters] = useState<AuditFilters>(EMPTY);
  const [offset, setOffset] = useState(0);
  const [items, setItems] = useState<AuditItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [exporting, setExporting] = useState(false);
  const [exportMsg, setExportMsg] = useState<{ kind: 'success' | 'error'; text: string } | null>(null);

  useEffect(() => {
    apiFetch<UserOut[]>('/api/users')
      .then((u) => setUsers(Array.isArray(u) ? u : []))
      .catch(() => setUsers([]));
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await apiFetch<{ items: AuditItem[]; total: number }>(`/api/audit?${buildAuditQuery({ ...filters, offset }, PAGE)}`);
      setItems(res.items ?? []);
      setTotal(res.total ?? 0);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setLoading(false);
    }
  }, [filters, offset]);

  useEffect(() => {
    load();
  }, [load]);

  function apply() {
    setOffset(0);
    setFilters({ ...draft });
  }

  function clear() {
    setDraft(EMPTY);
    setFilters(EMPTY);
    setOffset(0);
  }

  async function exportCsv() {
    setExporting(true);
    setExportMsg(null);
    try {
      const q = buildAuditQuery(filters, 500).replace(/(^|&)limit=\d+/, '').replace(/^&/, '');
      const today = new Date().toISOString().slice(0, 10);
      const saved = await downloadFile(`/api/audit/export.csv${q ? `?${q}` : ''}`, `Bitacora_${today}.csv`);
      if (saved) setExportMsg({ kind: 'success', text: `Bitácora exportada: ${saved}` });
    } catch (e) {
      setExportMsg({ kind: 'error', text: errorMessage(e) });
    } finally {
      setExporting(false);
    }
  }

  function toggle(id: string) {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  const from = total === 0 ? 0 : offset + 1;
  const to = Math.min(offset + PAGE, total);
  const hasFilters = !!(filters.userId || filters.action || filters.dateFrom || filters.dateTo || filters.q);

  return (
    <div className="space-y-5">
      <SectionHeader
        icon={<History className="h-5 w-5" />}
        title="Bitácora"
        subtitle="Registro de todo lo que hace cada usuario: quién, qué y cuándo."
        actions={
          <>
            <Button icon={<RefreshCw className="h-4 w-4" />} onClick={load} disabled={loading}>
              Actualizar
            </Button>
            <Button variant="primary" icon={<Download className="h-4 w-4" />} onClick={exportCsv} loading={exporting}>
              Exportar CSV
            </Button>
          </>
        }
      />

      {exportMsg && (
        <Notice kind={exportMsg.kind} onDismiss={() => setExportMsg(null)}>
          {exportMsg.text}
        </Notice>
      )}

      <Card className="p-4">
        <form
          className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-[1fr_1fr_150px_150px_1.3fr_auto]"
          onSubmit={(e) => {
            e.preventDefault();
            apply();
          }}
        >
          <Field label="Usuario">
            <select className={inputClass} value={draft.userId} onChange={(e) => setDraft({ ...draft, userId: e.target.value })}>
              <option value="">Todos los usuarios</option>
              {users.map((u) => (
                <option key={u.id} value={u.id}>
                  {u.fullName} {u.isActive ? '' : '(inactivo)'}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Acción">
            <select className={inputClass} value={draft.action} onChange={(e) => setDraft({ ...draft, action: e.target.value })}>
              {ACTIONS.map((a) => (
                <option key={a.value} value={a.value ? `${a.value}.` : ''}>
                  {a.label}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Desde">
            <input type="date" className={inputClass} value={draft.dateFrom} onChange={(e) => setDraft({ ...draft, dateFrom: e.target.value })} />
          </Field>
          <Field label="Hasta">
            <input type="date" className={inputClass} value={draft.dateTo} onChange={(e) => setDraft({ ...draft, dateTo: e.target.value })} />
          </Field>
          <Field label="Texto">
            <div className="relative">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[#9AA0A8]" />
              <input
                className={`${inputClass} pl-9`}
                placeholder="Buscar en el resumen…"
                value={draft.q}
                onChange={(e) => setDraft({ ...draft, q: e.target.value })}
              />
            </div>
          </Field>
          <div className="flex items-end gap-2">
            <Button type="submit" variant="primary" icon={<Search className="h-4 w-4" />}>
              Filtrar
            </Button>
            <Button onClick={clear} icon={<FilterX className="h-4 w-4" />} title="Quitar filtros" />
          </div>
        </form>
      </Card>

      <Card className="min-w-0">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[#E2E4E8] px-4 py-3">
          <span className="text-sm text-[#5C626D]">
            {loading ? (
              <Spinner label="Cargando…" />
            ) : (
              <>
                Mostrando <strong className="text-[#23272E]">{from}–{to}</strong> de{' '}
                <strong className="text-[#23272E]">{total}</strong> registros{hasFilters && ' (filtrados)'}
              </>
            )}
          </span>
          <div className="flex items-center gap-2">
            <Button
              size="sm"
              icon={<ChevronLeft className="h-3.5 w-3.5" />}
              disabled={offset === 0 || loading}
              onClick={() => setOffset(Math.max(0, offset - PAGE))}
            >
              Anterior
            </Button>
            <Button size="sm" disabled={offset + PAGE >= total || loading} onClick={() => setOffset(offset + PAGE)}>
              Siguiente <ChevronRight className="h-3.5 w-3.5" />
            </Button>
          </div>
        </div>

        {error ? (
          <div className="p-4">
            <Notice kind="error" action={<Button size="sm" onClick={load}>Reintentar</Button>}>
              No se pudo cargar la bitácora: {error}
            </Notice>
          </div>
        ) : !loading && items.length === 0 ? (
          <EmptyState
            icon={<History className="h-5 w-5" />}
            title={hasFilters ? 'Ningún registro coincide con los filtros' : 'La bitácora está vacía'}
            description={hasFilters ? 'Cambia o quita los filtros para ver más registros.' : undefined}
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[820px] border-collapse text-left text-sm">
              <thead>
                <tr className="border-b border-[#E2E4E8] bg-[#F7F7F8] text-xs font-semibold text-[#5C626D]">
                  <th className="w-8 px-3 py-2.5" />
                  <th className="px-3 py-2.5">Fecha y hora</th>
                  <th className="px-3 py-2.5">Usuario</th>
                  <th className="px-3 py-2.5">Acción</th>
                  <th className="px-3 py-2.5">Resumen</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#EFEFF1]">
                {items.map((it) => {
                  const open = expanded.has(it.id);
                  return (
                    <Fragment key={it.id}>
                      <tr className="cursor-pointer hover:bg-[#FAFAFB]" onClick={() => toggle(it.id)}>
                        <td className="px-3 py-2.5 text-[#9AA0A8]">
                          {open ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
                        </td>
                        <td className="whitespace-nowrap px-3 py-2.5 font-mono-tabular text-xs text-[#5C626D]">{formatDateTime(it.at)}</td>
                        <td className="whitespace-nowrap px-3 py-2.5 text-[#23272E]">{it.userName ?? it.actorName ?? 'Sistema'}</td>
                        <td className="px-3 py-2.5">
                          <Badge tone={actionTone(it.action)}>{it.action}</Badge>
                        </td>
                        <td className="px-3 py-2.5 text-[#23272E]">{it.summary}</td>
                      </tr>
                      {open && (
                        <tr className="bg-[#FAFAFB]">
                          <td />
                          <td colSpan={4} className="px-3 pb-3 pt-1">
                            <div className="mb-2 flex flex-wrap gap-x-5 gap-y-1 text-xs text-[#5C626D]">
                              <span>
                                Entidad: <strong className="text-[#23272E]">{it.entityType || '—'}</strong>
                              </span>
                              <span>
                                Id: <code className="font-mono-tabular text-[#23272E]">{it.entityId || '—'}</code>
                              </span>
                              <span>
                                IP: <code className="font-mono-tabular text-[#23272E]">{it.ip || '—'}</code>
                              </span>
                            </div>
                            {it.details != null ? (
                              <pre className="max-h-72 overflow-auto rounded-lg border border-[#E2E4E8] bg-white p-3 font-mono-tabular text-xs leading-relaxed text-[#23272E]">
                                {JSON.stringify(it.details, null, 2)}
                              </pre>
                            ) : (
                              <p className="text-xs text-[#9AA0A8]">Sin detalles adicionales.</p>
                            )}
                          </td>
                        </tr>
                      )}
                    </Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}

export default AuditLogModule;
