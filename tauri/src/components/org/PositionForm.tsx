import { useMemo, useState } from 'react';
import { FolderTree } from 'lucide-react';
import type { AppState, Position } from '../../types';
import { apiFetch, errorMessage } from '../../api/client';
import { folderNameFor } from '../../sync/folderMatch';
import { Button, Field, Modal, Notice, inputClass, textareaClass } from '../cv/ui';

const DEFAULT_AREAS = [
  'Gerencia General',
  'Operaciones Mina',
  'Planta de Procesos',
  'Mantenimiento',
  'Seguridad y Salud (HSEC)',
  'Medio Ambiente',
  'Recursos Humanos',
  'Administración y Finanzas',
  'Logística',
  'Geología',
];

export function PositionForm({
  state,
  position,
  parentId,
  onSaved,
  onClose,
}: {
  state: AppState;
  /** Puesto a editar; si no viene, se crea uno nuevo. */
  position?: Position | null;
  /** Para crear: puesto superior (null = raíz). */
  parentId?: string | null;
  onSaved: (s: AppState) => void;
  onClose: () => void;
}) {
  const editing = !!position;
  const [name, setName] = useState(position?.name ?? '');
  const [area, setArea] = useState(
    position?.area ?? (parentId ? state.positions.find((p) => p.id === parentId)?.area ?? '' : ''),
  );
  const [folderName, setFolderName] = useState(position?.folderName ?? '');
  const [folderTouched, setFolderTouched] = useState(editing);
  const [description, setDescription] = useState(position?.description ?? '');
  const [requiredSkills, setRequiredSkills] = useState(position?.requiredSkills ?? '');
  const [technicalSpecifications, setTechnicalSpecifications] = useState(position?.technicalSpecifications ?? '');
  const [minYears, setMinYears] = useState<string>(String(position?.minYearsExperience ?? 0));
  const [educationProfile, setEducationProfile] = useState(position?.educationProfile ?? '');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const areas = useMemo(() => {
    const set = new Set(DEFAULT_AREAS);
    state.positions.forEach((p) => p.area && set.add(p.area));
    return [...set].sort((a, b) => a.localeCompare(b, 'es'));
  }, [state.positions]);

  const effectiveFolder = folderTouched ? folderName : folderNameFor(name);
  const previewFolder = folderNameFor(effectiveFolder) || '…';
  const parentName = parentId ? state.positions.find((p) => p.id === parentId)?.name : null;
  const folderChanged = editing && position && folderNameFor(effectiveFolder) !== position.folderName;

  async function save() {
    setError(null);
    if (!name.trim()) return setError('Escribe el nombre del puesto.');
    if (!area.trim()) return setError('Indica el área del puesto.');
    if (!folderNameFor(effectiveFolder)) return setError('La carpeta no es válida: usa letras o números.');
    const years = Number.parseInt(minYears || '0', 10);
    if (Number.isNaN(years) || years < 0 || years > 60) return setError('Los años mínimos deben estar entre 0 y 60.');
    const body = {
      name: name.trim(),
      area: area.trim(),
      folderName: folderNameFor(effectiveFolder),
      description: description.trim(),
      requiredSkills: requiredSkills.trim(),
      technicalSpecifications: technicalSpecifications.trim(),
      minYearsExperience: years,
      educationProfile: educationProfile.trim(),
    };
    setBusy(true);
    try {
      const res = editing
        ? await apiFetch<{ state: AppState }>(`/api/positions/${position!.id}`, { method: 'PATCH', json: body })
        : await apiFetch<{ state: AppState }>('/api/positions', {
            method: 'POST',
            json: { ...body, parentId: parentId ?? null },
          });
      onSaved(res.state);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal
      title={editing ? `Editar puesto: ${position!.name}` : parentName ? 'Nuevo subordinado' : 'Nuevo puesto raíz'}
      subtitle={!editing && parentName ? `Dependerá de ${parentName}` : undefined}
      onClose={onClose}
      width="max-w-2xl"
      footer={
        <>
          <Button onClick={onClose} disabled={busy}>
            Cancelar
          </Button>
          <Button variant="primary" onClick={save} loading={busy}>
            {editing ? 'Guardar cambios' : 'Crear puesto'}
          </Button>
        </>
      }
    >
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <Field label="Nombre del puesto *">
          <input
            autoFocus
            className={inputClass}
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Ej.: Operador de Scoop"
          />
        </Field>
        <Field label="Área *" hint="Elige una de la lista o escribe una nueva.">
          <input
            className={inputClass}
            list="org-areas"
            value={area}
            onChange={(e) => setArea(e.target.value)}
            placeholder="Ej.: Operaciones Mina"
          />
          <datalist id="org-areas">
            {areas.map((a) => (
              <option key={a} value={a} />
            ))}
          </datalist>
        </Field>
        <Field
          className="sm:col-span-2"
          label="Carpeta"
          hint={
            <span className="inline-flex items-center gap-1.5">
              <FolderTree className="h-3.5 w-3.5" />
              Los CV se guardan en{' '}
              <code className="rounded bg-[#EFEFF1] px-1.5 py-0.5 font-mono-tabular text-[11px] text-[#23272E]">
                rrhh/{previewFolder}/&lt;fuente&gt;/
              </code>
            </span>
          }
        >
          <input
            className={`${inputClass} font-mono-tabular`}
            value={effectiveFolder}
            onChange={(e) => {
              setFolderTouched(true);
              setFolderName(e.target.value);
            }}
            placeholder="se completa con el nombre"
          />
        </Field>
        {folderChanged && (
          <div className="sm:col-span-2">
            <Notice kind="warning">
              Cambiar la carpeta mueve en el servidor los CV ya guardados de este puesto. Si usas una carpeta local
              sincronizada, renómbrala también.
            </Notice>
          </div>
        )}
        <Field className="sm:col-span-2" label="Descripción">
          <textarea
            rows={2}
            className={textareaClass}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Propósito del puesto y responsabilidades principales"
          />
        </Field>
        <Field className="sm:col-span-2" label="Competencias clave">
          <textarea
            rows={2}
            className={textareaClass}
            value={requiredSkills}
            onChange={(e) => setRequiredSkills(e.target.value)}
            placeholder="Ej.: trabajo en equipo, liderazgo, cumplimiento de estándares de seguridad"
          />
        </Field>
        <Field className="sm:col-span-2" label="Especificaciones técnicas">
          <textarea
            rows={2}
            className={textareaClass}
            value={technicalSpecifications}
            onChange={(e) => setTechnicalSpecifications(e.target.value)}
            placeholder="Ej.: licencia A-IIIb, manejo de equipo de bajo perfil, certificación IPERC"
          />
        </Field>
        <Field label="Años mínimos de experiencia">
          <input
            type="number"
            min={0}
            max={60}
            className={inputClass}
            value={minYears}
            onChange={(e) => setMinYears(e.target.value)}
          />
        </Field>
        <Field label="Formación esperada">
          <input
            className={inputClass}
            value={educationProfile}
            onChange={(e) => setEducationProfile(e.target.value)}
            placeholder="Ej.: Técnico en Mecánica de Equipo Pesado"
          />
        </Field>
      </div>
      {error && (
        <div className="mt-4">
          <Notice kind="error">{error}</Notice>
        </div>
      )}
    </Modal>
  );
}

export default PositionForm;
