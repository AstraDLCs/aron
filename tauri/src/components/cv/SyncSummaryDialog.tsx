import { useState, type ReactNode } from 'react';
import { AlertTriangle, Ban, CheckCircle2, Copy, FolderPlus, FolderX, XCircle } from 'lucide-react';
import type { SyncSummary } from '../../sync/runSync';
import { Button, Modal, Notice, formatDateTime } from './ui';

const SKIP_REASON: Record<string, string> = {
  estructura: 'no está dentro de una carpeta puesto/fuente/',
  formato: 'formato no admitido (solo PDF, DOCX, TXT o RTF) o no se pudo leer',
  tamaño: 'archivo vacío o mayor a 15 MB',
};

function Section({
  icon,
  title,
  count,
  children,
  defaultOpen,
}: {
  icon: ReactNode;
  title: string;
  count: number;
  children: ReactNode;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(!!defaultOpen);
  if (count === 0) return null;
  return (
    <div className="rounded-lg border border-[#E2E4E8]">
      <button
        onClick={() => setOpen(!open)}
        className="flex w-full items-center gap-2 px-3 py-2.5 text-left text-sm font-semibold text-[#23272E] hover:bg-[#F7F7F8]"
      >
        {icon}
        <span className="flex-1">{title}</span>
        <span className="font-mono-tabular text-xs text-[#5C626D]">{count}</span>
        <span className="text-xs text-[#5C626D]">{open ? 'Ocultar' : 'Ver'}</span>
      </button>
      {open && <div className="max-h-56 overflow-y-auto border-t border-[#EFEFF1] px-3 py-2 text-xs">{children}</div>}
    </div>
  );
}

export function SyncSummaryDialog({ summary, onClose }: { summary: SyncSummary; onClose: () => void }) {
  const ok = summary.errors.length === 0;
  const title = summary.origin === 'importacion' ? 'Resultado de la importación' : 'Resultado de la sincronización';
  return (
    <Modal
      title={title}
      subtitle={`${summary.root} · ${formatDateTime(summary.finishedAt)}`}
      onClose={onClose}
      width="max-w-2xl"
      footer={
        <Button variant="primary" onClick={onClose}>
          Cerrar
        </Button>
      }
    >
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {[
          { label: 'Nuevos', value: summary.uploaded, cls: 'text-[#2E6B4B]' },
          { label: 'Repetidos', value: summary.duplicates, cls: 'text-[#8A6100]' },
          { label: 'Eliminados antes', value: summary.deletedBefore, cls: 'text-[#8C4722]' },
          { label: 'Con error', value: summary.errors.length, cls: summary.errors.length ? 'text-[#B42318]' : 'text-[#23272E]' },
        ].map((k) => (
          <div key={k.label} className="rounded-lg border border-[#E2E4E8] px-3 py-2.5">
            <div className="text-xs text-[#5C626D]">{k.label}</div>
            <div className={`font-mono-tabular text-xl font-bold ${k.cls}`}>{k.value}</div>
          </div>
        ))}
      </div>
      <p className="mt-3 text-xs text-[#5C626D]">
        Se revisaron {summary.scanned} archivo{summary.scanned === 1 ? '' : 's'} en la carpeta.
      </p>
      {!ok && summary.scanned === 0 && (
        <div className="mt-3">
          <Notice kind="error">
            No se pudo leer la carpeta: {summary.errors[0]?.message}. Revisa que exista (si era un USB o una unidad de
            red, que esté conectada) o elige otra en Configuración.
          </Notice>
        </div>
      )}
      <div className="mt-4 space-y-2">
        <Section icon={<CheckCircle2 className="h-4 w-4 text-[#2E6B4B]" />} title="CV nuevos registrados" count={summary.uploadedFiles.length}>
          <ul className="space-y-1">
            {summary.uploadedFiles.map((f) => (
              <li key={f.path} className="truncate" title={f.path}>
                <span className="text-[#5C626D]">
                  {f.positionFolder}/{f.sourceFolder}/
                </span>
                {f.fileName}
              </li>
            ))}
          </ul>
        </Section>
        <Section icon={<Copy className="h-4 w-4 text-[#8A6100]" />} title="Repetidos (no se subieron)" count={summary.duplicateFiles.length}>
          <ul className="space-y-1">
            {summary.duplicateFiles.map((f, i) => (
              <li key={f.path + i} className="truncate" title={f.path}>
                <span className="text-[#5C626D]">
                  {f.positionFolder}/{f.sourceFolder}/
                </span>
                {f.fileName}
              </li>
            ))}
          </ul>
        </Section>
        <Section
          icon={<Ban className="h-4 w-4 text-[#8C4722]" />}
          title="Eliminados previamente (no se vuelven a importar)"
          count={summary.deletedBeforeFiles.length}
        >
          <p className="mb-1.5 text-[#5C626D]">Para permitirlos, usa «Permitir reimportar» en la pestaña Eliminados.</p>
          <ul className="space-y-1">
            {summary.deletedBeforeFiles.map((f) => (
              <li key={f.path} className="truncate" title={f.path}>
                <span className="text-[#5C626D]">
                  {f.positionFolder}/{f.sourceFolder}/
                </span>
                {f.fileName}
              </li>
            ))}
          </ul>
        </Section>
        <Section
          icon={<FolderPlus className="h-4 w-4 text-emerald-700" />}
          title="Puestos y fuentes creados a partir de las carpetas"
          count={(summary.createdPositions?.length ?? 0) + (summary.createdSources?.length ?? 0)}
          defaultOpen
        >
          <p className="mb-1.5 text-[#5C626D]">
            No existían en la app, así que se crearon con el nombre de la carpeta. Puedes completarlos en Organigrama.
          </p>
          <ul className="space-y-1">
            {(summary.createdPositions ?? []).map((n) => (
              <li key={`p-${n}`}>
                Puesto: <strong>{n}</strong>
              </li>
            ))}
            {(summary.createdSources ?? []).map((n) => (
              <li key={`f-${n}`}>
                Fuente: <strong>{n}</strong>
              </li>
            ))}
          </ul>
        </Section>
        <Section
          icon={<FolderX className="h-4 w-4 text-[#5C626D]" />}
          title="Carpetas que no se pudieron usar"
          count={summary.unmatchedFolders.length}
          defaultOpen
        >
          <p className="mb-1.5 text-[#5C626D]">
            No se pudo crear el puesto o la fuente para estas carpetas; el motivo está en «Errores».
          </p>
          <ul className="space-y-1">
            {summary.unmatchedFolders.map((u) => (
              <li key={u.kind + u.folder}>
                <strong>{u.folder}</strong> — {u.kind === 'puesto' ? 'puesto no encontrado' : 'fuente no encontrada'} ({u.count}{' '}
                archivo{u.count === 1 ? '' : 's'})
              </li>
            ))}
          </ul>
        </Section>
        <Section
          icon={<AlertTriangle className="h-4 w-4 text-[#8A6100]" />}
          title="Archivos omitidos"
          count={summary.skipped.length}
        >
          <ul className="space-y-1">
            {summary.skipped.map((s) => (
              <li key={s.path} className="truncate" title={s.path}>
                {s.path} — <span className="text-[#5C626D]">{SKIP_REASON[s.reason] ?? s.reason}</span>
              </li>
            ))}
          </ul>
        </Section>
        <Section icon={<XCircle className="h-4 w-4 text-[#B42318]" />} title="Errores" count={summary.errors.length} defaultOpen>
          <ul className="space-y-1">
            {summary.errors.map((e, i) => (
              <li key={e.path + i}>
                <span className="break-all text-[#5C626D]">{e.path}</span>: <span className="text-[#B42318]">{e.message}</span>
              </li>
            ))}
          </ul>
        </Section>
      </div>
    </Modal>
  );
}

export default SyncSummaryDialog;
