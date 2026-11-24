import { useEffect, useMemo, useState } from 'react';
import {
  Briefcase,
  ChevronDown,
  ChevronRight,
  ClipboardPlus,
  FolderTree,
  GitBranch,
  Network,
  Pencil,
  Plus,
  Search,
  Sparkles,
  Trash2,
  Users,
  MoveRight,
  ListTree,
} from 'lucide-react';
import type { AppState, AppSection, Position } from '../../types';
import { apiFetch, errorMessage } from '../../api/client';
import { buildTree, descendantsOf, positionPath, type TreeNode } from '../../utils/orgTree';
import { Badge, Button, Card, ConfirmDialog, EmptyState, Field, Modal, Notice, SectionHeader, inputClass } from '../cv/ui';
import { PositionForm } from './PositionForm';

export interface OrgChartModuleProps {
  state: AppState;
  onState: (s: AppState) => void;
  refresh: () => Promise<void>;
  navigate: (section: AppSection, opts?: { candidateId?: string; positionId?: string }) => void;
}

type FormState = { mode: 'create'; parentId: string | null } | { mode: 'edit'; position: Position } | null;

const CHART_CSS = `
.orgc ul { display:flex; justify-content:center; padding-top:20px; position:relative; margin:0; }
.orgc li { list-style:none; text-align:center; position:relative; padding:20px 6px 0 6px; }
.orgc li::before, .orgc li::after { content:''; position:absolute; top:0; right:50%; border-top:1.5px solid #D8DCE0; width:50%; height:20px; }
.orgc li::after { right:auto; left:50%; border-left:1.5px solid #D8DCE0; }
.orgc li:only-child::after, .orgc li:only-child::before { display:none; }
.orgc li:only-child { padding-top:0; }
.orgc li:first-child::before, .orgc li:last-child::after { border:0 none; }
.orgc li:last-child::before { border-right:1.5px solid #D8DCE0; border-radius:0 6px 0 0; }
.orgc li:first-child::after { border-radius:6px 0 0 0; }
.orgc ul ul::before { content:''; position:absolute; top:0; left:50%; border-left:1.5px solid #D8DCE0; width:0; height:20px; }
.orgc > ul { padding-top:0; }
`;

function countDescendants(node: TreeNode): number {
  return node.children.reduce((acc, c) => acc + 1 + countDescendants(c), 0);
}

export function OrgChartModule({ state, onState, navigate }: OrgChartModuleProps) {
  const [view, setView] = useState<'arbol' | 'grafico'>('arbol');
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());
  const [query, setQuery] = useState('');
  const [form, setForm] = useState<FormState>(null);
  const [moving, setMoving] = useState<Position | null>(null);
  const [deleting, setDeleting] = useState<Position | null>(null);
  const [reclassifying, setReclassifying] = useState<Position | null>(null);
  const [busy, setBusy] = useState(false);
  const [dialogError, setDialogError] = useState<string | null>(null);
  const [toast, setToast] = useState<{ kind: 'success' | 'error'; text: string } | null>(null);

  const positions = state.positions;
  const tree = useMemo(() => buildTree(positions), [positions]);
  const selected = positions.find((p) => p.id === selectedId) ?? null;

  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 6000);
    return () => clearTimeout(t);
  }, [toast]);

  const matchesQuery = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return null;
    const hits = new Set<string>();
    const byId = new Map(positions.map((p) => [p.id, p]));
    for (const p of positions) {
      if (`${p.name} ${p.area} ${p.folderName}`.toLowerCase().includes(q)) {
        // incluir ancestros para que se vea el camino
        let cur: Position | undefined = p;
        const guard = new Set<string>();
        while (cur && !guard.has(cur.id)) {
          guard.add(cur.id);
          hits.add(cur.id);
          cur = cur.parentId ? byId.get(cur.parentId) : undefined;
        }
      }
    }
    return hits;
  }, [query, positions]);

  const totals = useMemo(
    () => ({
      positions: positions.length,
      areas: new Set(positions.map((p) => p.area).filter(Boolean)).size,
      openReqs: positions.reduce((a, p) => a + (p.openRequirementsCount ?? 0), 0),
      candidates: positions.reduce((a, p) => a + (p.candidatesCount ?? 0), 0),
    }),
    [positions],
  );

  function toggle(id: string) {
    setCollapsed((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function closeDialogs() {
    setMoving(null);
    setDeleting(null);
    setReclassifying(null);
    setDialogError(null);
  }

  async function doDelete() {
    if (!deleting) return;
    setBusy(true);
    setDialogError(null);
    try {
      const res = await apiFetch<{ state: AppState }>(`/api/positions/${deleting.id}`, { method: 'DELETE' });
      onState(res.state);
      setToast({ kind: 'success', text: `Se eliminó el puesto ${deleting.name}.` });
      if (selectedId === deleting.id) setSelectedId(null);
      closeDialogs();
    } catch (e) {
      setDialogError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }

  async function doReclassify() {
    if (!reclassifying) return;
    setBusy(true);
    setDialogError(null);
    try {
      const res = await apiFetch<{ state: AppState; requeued?: number }>(
        `/api/positions/${reclassifying.id}/reclassify`,
        { method: 'POST' },
      );
      onState(res.state);
      setToast({
        kind: 'success',
        text: `Se enviaron ${res.requeued ?? 0} postulaciones de ${reclassifying.name} a la cola de la IA.`,
      });
      closeDialogs();
    } catch (e) {
      setDialogError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }

  const renderTreeNode = (node: TreeNode, depth: number) => {
    const p = node.position;
    if (matchesQuery && !matchesQuery.has(p.id)) return null;
    const isCollapsed = collapsed.has(p.id) && !matchesQuery;
    const isSelected = p.id === selectedId;
    return (
      <div key={p.id}>
        <div
          onClick={() => setSelectedId(p.id)}
          className={`group flex cursor-pointer items-center gap-2 rounded-lg border px-2 py-2 transition-colors ${
            isSelected ? 'border-[#E6CDBE] bg-[#FBF4EE]' : 'border-transparent hover:bg-[#F7F7F8]'
          }`}
          style={{ marginLeft: depth * 22 }}
        >
          <button
            onClick={(e) => {
              e.stopPropagation();
              toggle(p.id);
            }}
            className={`flex h-6 w-6 items-center justify-center rounded text-[#5C626D] hover:bg-[#EFEFF1] ${
              node.children.length ? '' : 'invisible'
            }`}
            aria-label={isCollapsed ? 'Desplegar' : 'Plegar'}
          >
            {isCollapsed ? <ChevronRight className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
          </button>
          <div
            className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-lg ${
              depth === 0 ? 'bg-[#B26337] text-white' : 'bg-[#EFEFF1] text-[#5C626D]'
            }`}
          >
            <Briefcase className="h-4 w-4" />
          </div>
          <div className="min-w-0 flex-1">
            <div className="truncate text-sm font-semibold text-[#23272E]">{p.name}</div>
            <div className="truncate text-xs text-[#5C626D]">
              {p.area}
              {node.children.length > 0 && ` · ${node.children.length} subordinado${node.children.length === 1 ? '' : 's'}`}
            </div>
          </div>
          <div className="flex shrink-0 items-center gap-1.5">
            {p.openRequirementsCount > 0 && (
              <Badge tone="accent" title="Requerimientos abiertos">
                <ClipboardPlus className="h-3 w-3" />
                {p.openRequirementsCount} abierto{p.openRequirementsCount === 1 ? '' : 's'}
              </Badge>
            )}
            <Badge tone={p.candidatesCount > 0 ? 'blue' : 'neutral'} title="Candidatos (postulaciones)">
              <Users className="h-3 w-3" />
              {p.candidatesCount}
            </Badge>
            <button
              title="Agregar subordinado"
              onClick={(e) => {
                e.stopPropagation();
                setForm({ mode: 'create', parentId: p.id });
              }}
              className="hidden h-7 w-7 items-center justify-center rounded-md text-[#5C626D] hover:bg-white hover:text-[#B26337] group-hover:flex"
            >
              <Plus className="h-4 w-4" />
            </button>
            <button
              title="Editar"
              onClick={(e) => {
                e.stopPropagation();
                setForm({ mode: 'edit', position: p });
              }}
              className="hidden h-7 w-7 items-center justify-center rounded-md text-[#5C626D] hover:bg-white hover:text-[#B26337] group-hover:flex"
            >
              <Pencil className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>
        {!isCollapsed && node.children.map((c) => renderTreeNode(c, depth + 1))}
      </div>
    );
  };

  const renderChartNode = (node: TreeNode) => {
    const p = node.position;
    const isSelected = p.id === selectedId;
    const isCollapsed = collapsed.has(p.id);
    return (
      <li key={p.id}>
        <div
          onClick={() => setSelectedId(p.id)}
          className={`inline-block w-[170px] cursor-pointer rounded-lg border bg-white px-3 py-2.5 text-left shadow-sm transition-colors ${
            isSelected ? 'border-[#B26337] ring-2 ring-[#B26337]/15' : 'border-[#E2E4E8] hover:border-[#E6CDBE]'
          }`}
        >
          <div className="line-clamp-2 text-xs font-bold leading-snug text-[#23272E]">{p.name}</div>
          <div className="mt-0.5 truncate text-[11px] text-[#5C626D]">{p.area}</div>
          <div className="mt-2 flex items-center justify-between gap-1">
            <span
              className={`text-[11px] font-semibold ${p.openRequirementsCount > 0 ? 'text-[#B26337]' : 'text-[#9AA0A8]'}`}
              title="Requerimientos abiertos"
            >
              {p.openRequirementsCount} req.
            </span>
            <span className="inline-flex items-center gap-1 text-[11px] text-[#5C626D]" title="Candidatos">
              <Users className="h-3 w-3" />
              {p.candidatesCount}
            </span>
            {node.children.length > 0 && (
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  toggle(p.id);
                }}
                className="rounded px-1 text-[11px] font-semibold text-[#5C626D] hover:bg-[#EFEFF1]"
                title={isCollapsed ? 'Mostrar subordinados' : 'Ocultar subordinados'}
              >
                {isCollapsed ? `+${countDescendants(node)}` : '−'}
              </button>
            )}
          </div>
        </div>
        {node.children.length > 0 && !isCollapsed && <ul>{node.children.map(renderChartNode)}</ul>}
      </li>
    );
  };

  const selectedNode = useMemo(() => {
    if (!selected) return null;
    const find = (nodes: TreeNode[]): TreeNode | null => {
      for (const n of nodes) {
        if (n.position.id === selected.id) return n;
        const r = find(n.children);
        if (r) return r;
      }
      return null;
    };
    return find(tree);
  }, [selected, tree]);

  return (
    <div className="space-y-5">
      <style>{CHART_CSS}</style>
      <SectionHeader
        icon={<Network className="h-5 w-5" />}
        title="Organigrama"
        subtitle="Puestos de la empresa, su jerarquía y la carpeta donde se guardan sus CV."
        actions={
          <>
            <div className="inline-flex rounded-lg border border-[#D8DCE0] bg-white p-0.5">
              <button
                onClick={() => setView('arbol')}
                className={`inline-flex h-8 items-center gap-1.5 rounded-md px-3 text-xs font-semibold ${
                  view === 'arbol' ? 'bg-[#23272E] text-white' : 'text-[#5C626D] hover:text-[#23272E]'
                }`}
              >
                <ListTree className="h-3.5 w-3.5" /> Árbol
              </button>
              <button
                onClick={() => setView('grafico')}
                className={`inline-flex h-8 items-center gap-1.5 rounded-md px-3 text-xs font-semibold ${
                  view === 'grafico' ? 'bg-[#23272E] text-white' : 'text-[#5C626D] hover:text-[#23272E]'
                }`}
              >
                <GitBranch className="h-3.5 w-3.5" /> Gráfico
              </button>
            </div>
            <Button variant="primary" icon={<Plus className="h-4 w-4" />} onClick={() => setForm({ mode: 'create', parentId: null })}>
              Puesto raíz
            </Button>
          </>
        }
      />

      {toast && (
        <Notice kind={toast.kind} onDismiss={() => setToast(null)}>
          {toast.text}
        </Notice>
      )}

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {[
          { label: 'Puestos', value: totals.positions },
          { label: 'Áreas', value: totals.areas },
          { label: 'Requerimientos abiertos', value: totals.openReqs },
          { label: 'Candidatos', value: totals.candidates },
        ].map((k) => (
          <Card key={k.label} className="px-4 py-3">
            <div className="text-xs font-medium text-[#5C626D]">{k.label}</div>
            <div className="mt-0.5 font-mono-tabular text-xl font-bold text-[#23272E]">{k.value}</div>
          </Card>
        ))}
      </div>

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-[minmax(0,1fr)_340px]">
        <Card className="min-w-0 p-4">
          {positions.length === 0 ? (
            <EmptyState
              icon={<Network className="h-5 w-5" />}
              title="Aún no hay puestos"
              description="Crea el primer puesto (por ejemplo, Gerencia General) y luego agrega sus subordinados."
              action={
                <Button variant="primary" icon={<Plus className="h-4 w-4" />} onClick={() => setForm({ mode: 'create', parentId: null })}>
                  Crear puesto raíz
                </Button>
              }
            />
          ) : view === 'arbol' ? (
            <>
              <div className="mb-3 flex flex-wrap items-center gap-2">
                <div className="relative min-w-[220px] flex-1">
                  <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[#9AA0A8]" />
                  <input
                    className={`${inputClass} pl-9`}
                    placeholder="Buscar puesto, área o carpeta…"
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                  />
                </div>
                <Button size="sm" variant="ghost" onClick={() => setCollapsed(new Set())}>
                  Desplegar todo
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => setCollapsed(new Set(positions.filter((p) => positions.some((c) => c.parentId === p.id)).map((p) => p.id)))}
                >
                  Plegar todo
                </Button>
              </div>
              <div className="space-y-0.5">
                {tree.map((n) => renderTreeNode(n, 0))}
                {matchesQuery && matchesQuery.size === 0 && (
                  <p className="py-6 text-center text-sm text-[#5C626D]">Ningún puesto coincide con «{query}».</p>
                )}
              </div>
            </>
          ) : (
            <div className="overflow-auto pb-4">
              <div className="orgc inline-block min-w-full px-2 py-2">
                <ul>{tree.map(renderChartNode)}</ul>
              </div>
            </div>
          )}
        </Card>

        <Card className="h-fit p-5 xl:sticky xl:top-4">
          {!selected ? (
            <EmptyState
              icon={<Briefcase className="h-5 w-5" />}
              title="Selecciona un puesto"
              description="Haz clic en un puesto para ver su detalle y sus acciones."
            />
          ) : (
            <div className="space-y-4">
              <div>
                <div className="text-xs font-medium text-[#5C626D]">{positionPath(selected.id, positions)}</div>
                <h2 className="mt-1 font-display text-lg font-bold text-[#23272E]">{selected.name}</h2>
                <div className="mt-1 flex flex-wrap gap-1.5">
                  <Badge>{selected.area}</Badge>
                  <Badge tone="accent">{selected.openRequirementsCount} req. abiertos</Badge>
                  <Badge tone="blue">{selected.candidatesCount} candidatos</Badge>
                </div>
              </div>
              <div className="flex items-center gap-2 rounded-lg bg-[#F7F7F8] px-3 py-2 text-xs text-[#5C626D]">
                <FolderTree className="h-4 w-4 shrink-0 text-[#B26337]" />
                <code className="truncate font-mono-tabular text-[#23272E]">rrhh/{selected.folderName}/&lt;fuente&gt;/</code>
              </div>
              <dl className="space-y-2.5 text-sm">
                {[
                  ['Descripción', selected.description],
                  ['Competencias clave', selected.requiredSkills],
                  ['Especificaciones técnicas', selected.technicalSpecifications],
                  ['Formación esperada', selected.educationProfile],
                  ['Años mínimos', String(selected.minYearsExperience ?? 0)],
                  ['Subordinados directos', String(selectedNode?.children.length ?? 0)],
                ].map(([k, v]) => (
                  <div key={k}>
                    <dt className="text-xs font-semibold text-[#5C626D]">{k}</dt>
                    <dd className="whitespace-pre-wrap text-[#23272E]">{v || <span className="text-[#9AA0A8]">—</span>}</dd>
                  </div>
                ))}
              </dl>
              <div className="grid grid-cols-2 gap-2 border-t border-[#E2E4E8] pt-4">
                <Button size="sm" icon={<Plus className="h-3.5 w-3.5" />} onClick={() => setForm({ mode: 'create', parentId: selected.id })}>
                  Subordinado
                </Button>
                <Button size="sm" icon={<Pencil className="h-3.5 w-3.5" />} onClick={() => setForm({ mode: 'edit', position: selected })}>
                  Editar
                </Button>
                <Button size="sm" icon={<MoveRight className="h-3.5 w-3.5" />} onClick={() => setMoving(selected)}>
                  Mover a…
                </Button>
                <Button size="sm" variant="danger" icon={<Trash2 className="h-3.5 w-3.5" />} onClick={() => setDeleting(selected)}>
                  Eliminar
                </Button>
                <Button
                  size="sm"
                  variant="primary"
                  className="col-span-2"
                  icon={<ClipboardPlus className="h-3.5 w-3.5" />}
                  onClick={() => navigate('requerimientos', { positionId: selected.id })}
                >
                  Crear requerimiento
                </Button>
                <Button
                  size="sm"
                  className="col-span-2"
                  icon={<Sparkles className="h-3.5 w-3.5" />}
                  onClick={() => setReclassifying(selected)}
                  disabled={selected.candidatesCount === 0}
                  title={selected.candidatesCount === 0 ? 'Este puesto no tiene postulaciones' : undefined}
                >
                  Reclasificar puesto con IA
                </Button>
              </div>
            </div>
          )}
        </Card>
      </div>

      {form && (
        <PositionForm
          state={state}
          position={form.mode === 'edit' ? form.position : null}
          parentId={form.mode === 'create' ? form.parentId : undefined}
          onClose={() => setForm(null)}
          onSaved={(s) => {
            const wasEdit = form.mode === 'edit';
            onState(s);
            setForm(null);
            setToast({ kind: 'success', text: wasEdit ? 'Cambios guardados.' : 'Puesto creado.' });
          }}
        />
      )}

      {moving && (
        <MoveDialog
          position={moving}
          positions={positions}
          onClose={closeDialogs}
          onDone={(s) => {
            onState(s);
            setToast({ kind: 'success', text: `Se movió ${moving.name}.` });
            closeDialogs();
          }}
        />
      )}

      {deleting && (
        <ConfirmDialog
          title="Eliminar puesto"
          danger
          confirmLabel="Eliminar"
          busy={busy}
          error={dialogError}
          message={
            <>
              ¿Eliminar el puesto <strong>{deleting.name}</strong>? Solo se puede eliminar si no tiene subordinados,
              requerimientos ni candidatos.
            </>
          }
          onConfirm={doDelete}
          onCancel={closeDialogs}
        />
      )}

      {reclassifying && (
        <ConfirmDialog
          title="Reclasificar puesto con IA"
          confirmLabel="Reclasificar"
          busy={busy}
          error={dialogError}
          message={
            <>
              Se volverán a enviar a la IA las postulaciones de <strong>{reclassifying.name}</strong> (
              {reclassifying.candidatesCount}). Su veredicto actual se reemplazará cuando la IA termine. Cada CV usa una
              consulta del cupo diario de OpenRouter.
            </>
          }
          onConfirm={doReclassify}
          onCancel={closeDialogs}
        />
      )}
    </div>
  );
}

function MoveDialog({
  position,
  positions,
  onClose,
  onDone,
}: {
  position: Position;
  positions: Position[];
  onClose: () => void;
  onDone: (s: AppState) => void;
}) {
  const excluded = useMemo(() => descendantsOf(position.id, positions), [position.id, positions]);
  const options = useMemo(
    () =>
      positions
        .filter((p) => !excluded.has(p.id))
        .map((p) => ({ id: p.id, label: positionPath(p.id, positions) }))
        .sort((a, b) => a.label.localeCompare(b.label, 'es')),
    [positions, excluded],
  );
  const [target, setTarget] = useState<string>(position.parentId ?? '');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function save() {
    setBusy(true);
    setError(null);
    try {
      const res = await apiFetch<{ state: AppState }>(`/api/positions/${position.id}`, {
        method: 'PATCH',
        json: { parentId: target || null },
      });
      onDone(res.state);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal
      title={`Mover ${position.name}`}
      subtitle="Elige el nuevo puesto superior. No aparecen el propio puesto ni sus subordinados."
      onClose={onClose}
      footer={
        <>
          <Button onClick={onClose} disabled={busy}>
            Cancelar
          </Button>
          <Button variant="primary" onClick={save} loading={busy} disabled={(position.parentId ?? '') === target}>
            Mover
          </Button>
        </>
      }
    >
      <Field label="Nuevo puesto superior">
        <select className={inputClass} value={target} onChange={(e) => setTarget(e.target.value)}>
          <option value="">(Sin superior: puesto raíz)</option>
          {options.map((o) => (
            <option key={o.id} value={o.id}>
              {o.label}
            </option>
          ))}
        </select>
      </Field>
      {error && (
        <div className="mt-3">
          <Notice kind="error">{error}</Notice>
        </div>
      )}
    </Modal>
  );
}

export default OrgChartModule;
