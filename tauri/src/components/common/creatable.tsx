import { useState, type ChangeEvent, type KeyboardEvent, type ReactNode } from 'react';
import type { AppState, JobUrgency as Urgency, SourceCategory } from '../../types';
import { apiFetch, errorMessage } from '../../api/client';
import { folderNameFor, normalizeKey } from '../../sync/folderMatch';
import { Button, inputClass } from '../cv/ui';

/**
 * Selecciones que permiten crear al vuelo («+ Nuevo puesto…», «+ Nueva fuente…», «+ Nuevo requerimiento…»).
 * Uso: el `<select>` queda dentro del `Field` de la pantalla (value / onChange / newOption) y `panel` se pone
 * debajo, fuera del `<label>`, para que los clics del mini formulario no activen el selector.
 */
export type CreatableKind = 'puesto' | 'fuente' | 'requerimiento';

export const SOURCE_CATEGORIES: SourceCategory[] = ['Bolsa Nacional', 'Red Profesional', 'Portal Minero', 'Referidos Faena'];
const URGENCIES: Urgency[] = ['Urgente', 'Media', 'Planificada'];
const NEW = '__nuevo__';
const NEW_LABEL: Record<CreatableKind, string> = {
  puesto: '+ Nuevo puesto…',
  fuente: '+ Nueva fuente…',
  requerimiento: '+ Nuevo requerimiento…',
};
const NO_AREA = 'Sin área';

type Draft =
  | { kind: 'puesto'; name: string; area: string; parentId: string }
  | { kind: 'fuente'; name: string; category: SourceCategory }
  | { kind: 'requerimiento'; quantity: string; urgency: Urgency };

function emptyDraft(kind: CreatableKind, defaultParentId?: string): Draft {
  if (kind === 'puesto') return { kind, name: '', area: '', parentId: defaultParentId ?? '' };
  if (kind === 'fuente') return { kind, name: '', category: 'Bolsa Nacional' };
  return { kind, quantity: '1', urgency: 'Media' };
}

export interface CreatableOptions {
  kind: CreatableKind;
  state: AppState;
  value: string;
  onSelect: (value: string) => void;
  /** Se llama con el id creado (o el existente con el mismo nombre) y la foto nueva, si la hubo. */
  onCreated: (id: string, state: AppState | null) => void;
  /** Requerimiento: puesto al que pertenece. */
  positionId?: string;
  disabled?: boolean;
}

export function useCreatable(o: CreatableOptions) {
  const [draft, setDraft] = useState<Draft | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);

  function onChange(e: ChangeEvent<HTMLSelectElement>) {
    setError(null);
    setNote(null);
    if (e.target.value === NEW) {
      setDraft(emptyDraft(o.kind));
      return;
    }
    setDraft(null);
    o.onSelect(e.target.value);
  }

  function pick(id: string, s: AppState | null, msg: string) {
    o.onCreated(id, s);
    setDraft(null);
    setNote(msg);
  }

  async function create() {
    if (!draft || busy) return;
    setError(null);
    try {
      if (draft.kind === 'puesto' || draft.kind === 'fuente') {
        const name = draft.name.trim();
        if (!folderNameFor(name)) return setError('Escribe un nombre con al menos una letra o un número.');
        const list = draft.kind === 'puesto' ? o.state.positions : o.state.jobBoards;
        const existing = list.find((x) => normalizeKey(x.name) === normalizeKey(name) || x.folderName === folderNameFor(name));
        if (existing) return pick(existing.id, null, `Ya existía «${existing.name}»: quedó elegido.`);
        setBusy(true);
        if (draft.kind === 'puesto') {
          const res = await apiFetch<{ position: { id: string; name: string }; state: AppState }>('/api/positions', {
            method: 'POST',
            json: { name, area: draft.area.trim() || NO_AREA, parentId: draft.parentId || null },
          });
          pick(res.position.id, res.state, `Puesto «${res.position.name}» creado.`);
        } else {
          const res = await apiFetch<{ source: { id: string; name: string }; state: AppState }>('/api/sources', {
            method: 'POST',
            json: { name, category: draft.category },
          });
          pick(res.source.id, res.state, `Fuente «${res.source.name}» creada.`);
        }
      } else {
        if (!o.positionId) return setError('Elige primero el puesto.');
        const quantity = Math.max(1, Math.min(1000, Number.parseInt(draft.quantity, 10) || 1));
        setBusy(true);
        const res = await apiFetch<{ requirement: { id: string }; state: AppState }>('/api/requirements', {
          method: 'POST',
          json: { positionId: o.positionId, quantity, urgency: draft.urgency },
        });
        pick(res.requirement.id, res.state, `Requerimiento de ${quantity} plaza${quantity === 1 ? '' : 's'} creado.`);
      }
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }

  const onEnter = (e: KeyboardEvent) => {
    if (e.key === 'Enter') {
      e.preventDefault(); // dentro de un <form> no debe enviarlo
      void create();
    }
  };

  let panel: ReactNode = null;
  if (draft) {
    const areas = [...new Set(o.state.positions.map((p) => p.area).filter(Boolean))].sort((a, b) => a.localeCompare(b, 'es'));
    const fieldLabel = 'mb-1 block text-xs font-semibold text-[#23272E]';
    panel = (
      <div className="rounded-lg border border-[#E6CDBE] bg-[#FBF4EE] p-3">
        <p className="mb-2 text-sm font-semibold text-[#23272E]">
          {draft.kind === 'puesto' ? 'Nuevo puesto' : draft.kind === 'fuente' ? 'Nueva fuente' : 'Nuevo requerimiento'}
        </p>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          {draft.kind !== 'requerimiento' ? (
            <label className="block">
              <span className={fieldLabel}>Nombre *</span>
              <input
                autoFocus
                className={inputClass}
                value={draft.name}
                maxLength={200}
                placeholder={draft.kind === 'puesto' ? 'Ej.: Topógrafo de Mina' : 'Ej.: Bumeran, Feria laboral Arequipa'}
                onChange={(e) => setDraft({ ...draft, name: e.target.value })}
                onKeyDown={onEnter}
                disabled={busy}
              />
            </label>
          ) : (
            <label className="block">
              <span className={fieldLabel}>Plazas *</span>
              <input
                autoFocus
                type="number"
                min={1}
                max={1000}
                className={inputClass}
                value={draft.quantity}
                onChange={(e) => setDraft({ ...draft, quantity: e.target.value })}
                onKeyDown={onEnter}
                disabled={busy}
              />
            </label>
          )}
          {draft.kind === 'puesto' && (
            <label className="block">
              <span className={fieldLabel}>Área</span>
              <input
                className={inputClass}
                value={draft.area}
                list="creatable-areas"
                placeholder={NO_AREA}
                onChange={(e) => setDraft({ ...draft, area: e.target.value })}
                onKeyDown={onEnter}
                disabled={busy}
              />
              <datalist id="creatable-areas">
                {areas.map((a) => (
                  <option key={a} value={a} />
                ))}
              </datalist>
            </label>
          )}
          {draft.kind === 'puesto' && (
            <label className="block sm:col-span-2">
              <span className={fieldLabel}>Reporta a</span>
              <select
                className={inputClass}
                value={draft.parentId}
                onChange={(e) => setDraft({ ...draft, parentId: e.target.value })}
                disabled={busy}
              >
                <option value="">Nadie (puesto principal del organigrama)</option>
                {[...o.state.positions]
                  .sort((a, b) => a.name.localeCompare(b.name, 'es'))
                  .map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name}
                    </option>
                  ))}
              </select>
            </label>
          )}
          {draft.kind === 'fuente' && (
            <label className="block">
              <span className={fieldLabel}>Categoría</span>
              <select
                className={inputClass}
                value={draft.category}
                onChange={(e) => setDraft({ ...draft, category: e.target.value as SourceCategory })}
                disabled={busy}
              >
                {SOURCE_CATEGORIES.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
            </label>
          )}
          {draft.kind === 'requerimiento' && (
            <label className="block">
              <span className={fieldLabel}>Urgencia</span>
              <select
                className={inputClass}
                value={draft.urgency}
                onChange={(e) => setDraft({ ...draft, urgency: e.target.value as Urgency })}
                disabled={busy}
              >
                {URGENCIES.map((u) => (
                  <option key={u} value={u}>
                    {u}
                  </option>
                ))}
              </select>
            </label>
          )}
        </div>
        {draft.kind !== 'requerimiento' && (
          <p className="mt-2 text-xs text-[#5C626D]">
            Carpeta:{' '}
            {draft.kind === 'puesto' ? 'rrhh/' : 'rrhh/<puesto>/'}
            <span className="font-mono text-[#23272E]">{folderNameFor(draft.name) || '…'}</span>/
          </p>
        )}
        {draft.kind === 'requerimiento' && !o.positionId && (
          <p className="mt-2 text-xs text-amber-800">Elige primero el puesto del requerimiento.</p>
        )}
        {error && <p className="mt-2 text-xs font-semibold text-red-700">{error}</p>}
        <div className="mt-3 flex justify-end gap-2">
          <Button size="sm" onClick={() => setDraft(null)} disabled={busy}>
            Cancelar
          </Button>
          <Button
            size="sm"
            variant="primary"
            onClick={() => void create()}
            loading={busy}
            disabled={draft.kind === 'requerimiento' ? !o.positionId : !draft.name.trim()}
          >
            {draft.kind === 'puesto' ? 'Crear puesto' : draft.kind === 'fuente' ? 'Crear fuente' : 'Crear requerimiento'}
          </Button>
        </div>
      </div>
    );
  } else if (note) {
    panel = <p className="text-xs font-semibold text-emerald-700">{note}</p>;
  }

  return {
    /** Valor para el `<select>`: muestra «+ Nuevo…» mientras el mini formulario está abierto. */
    value: draft ? NEW : o.value,
    onChange,
    newOption: <option value={NEW}>{NEW_LABEL[o.kind]}</option>,
    panel,
    /** true mientras hay un mini formulario abierto sin terminar. */
    pending: draft !== null,
    disabled: !!o.disabled || busy,
  };
}
