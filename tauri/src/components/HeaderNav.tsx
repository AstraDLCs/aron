import React, { useEffect, useRef, useState } from 'react';
import { ChevronDown, FileDown } from 'lucide-react';
import type { AppSection } from '../types';
import { DownloadButton } from './common/DownloadButton';

interface HeaderNavProps {
  activeSection: AppSection;
  onSelectSection: (section: AppSection) => void;
  pendingReviewCount: number;
  companyName: string;
}

const MAIN: Array<{ id: AppSection; label: string }> = [
  { id: 'candidatos', label: 'Candidatos' },
  { id: 'organigrama', label: 'Organigrama' },
  { id: 'requerimientos', label: 'Requerimientos' },
  { id: 'carpeta', label: 'Carpeta de CVs' },
  { id: 'psicologicas', label: 'Pruebas' },
];

const MORE: Array<{ id: AppSection; label: string }> = [
  { id: 'procesos', label: 'Procesos KPI' },
  { id: 'reportes', label: 'Reportes' },
  { id: 'bitacora', label: 'Bitácora' },
  { id: 'configuracion', label: 'Configuración' },
];

export const HeaderNav: React.FC<HeaderNavProps> = ({ activeSection, onSelectSection, pendingReviewCount, companyName }) => {
  const [moreOpen, setMoreOpen] = useState(false);
  const moreRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const h = (e: MouseEvent) => {
      if (moreRef.current && !moreRef.current.contains(e.target as Node)) setMoreOpen(false);
    };
    document.addEventListener('mousedown', h);
    return () => document.removeEventListener('mousedown', h);
  }, []);
  const moreActive = MORE.some((m) => m.id === activeSection);

  const tabCls = (active: boolean) =>
    `relative py-2 text-sm font-medium transition-colors whitespace-nowrap cursor-pointer ${
      active ? 'text-[#B26337] font-semibold' : 'text-[#5C626D] hover:text-[#23272E]'
    }`;

  return (
    <header className="sticky top-0 z-30 border-b border-[#E2E4E8] bg-white/95 backdrop-blur-sm">
      <div className="mx-auto flex h-16 max-w-[1400px] items-center justify-between gap-6 px-6">
        <button type="button" onClick={() => onSelectSection('candidatos')} className="flex min-w-0 items-center gap-2.5 cursor-pointer">
          <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-[#B26337] font-display text-sm font-extrabold text-white">
            PL
          </span>
          <span className="min-w-0 text-left leading-tight">
            <span className="block font-display text-base font-bold tracking-tight text-[#23272E]">Pulso Laboral</span>
            <span className="block truncate text-[11px] text-[#5C626D]">{companyName}</span>
          </span>
        </button>

        <nav aria-label="Navegación principal" className="flex items-center gap-5">
          {MAIN.map((item) => {
            const isActive = activeSection === item.id;
            const label =
              item.id === 'requerimientos' && pendingReviewCount > 0 ? (
                <>
                  {item.label}{' '}
                  <span className="ml-1 rounded-full bg-[#B26337] px-1.5 py-0.5 text-[10px] font-bold text-white">{pendingReviewCount}</span>
                </>
              ) : (
                item.label
              );
            return (
              <button key={item.id} type="button" onClick={() => onSelectSection(item.id)} className={tabCls(isActive)}>
                {label}
                {isActive && <span aria-hidden="true" className="absolute inset-x-0 -bottom-[17px] h-0.5 bg-[#B26337]" />}
              </button>
            );
          })}
          <div className="relative" ref={moreRef}>
            <button type="button" onClick={() => setMoreOpen((v) => !v)} className={`${tabCls(moreActive)} inline-flex items-center gap-1`}>
              {moreActive ? MORE.find((m) => m.id === activeSection)?.label : 'Más'}
              <ChevronDown className="h-3.5 w-3.5" />
              {moreActive && <span aria-hidden="true" className="absolute inset-x-0 -bottom-[17px] h-0.5 bg-[#B26337]" />}
            </button>
            {moreOpen && (
              <div className="absolute right-0 top-full z-40 mt-3 w-52 overflow-hidden rounded-xl border border-[#E2E4E8] bg-white py-1 shadow-lg">
                {MORE.map((m) => (
                  <button
                    key={m.id}
                    type="button"
                    onClick={() => {
                      setMoreOpen(false);
                      onSelectSection(m.id);
                    }}
                    className={`block w-full px-4 py-2 text-left text-sm hover:bg-[#F7F7F8] ${
                      activeSection === m.id ? 'font-semibold text-[#B26337]' : 'text-[#23272E]'
                    }`}
                  >
                    {m.label}
                  </button>
                ))}
              </div>
            )}
          </div>
        </nav>

        <div className="flex shrink-0 items-center">
          <DownloadButton
            path="/api/reports/admin-doc"
            fileName="Informe_Ejecutivo.doc"
            label="Informe Admin"
            variant="primary"
            icon={<FileDown className="h-4 w-4" />}
          />
        </div>
      </div>
    </header>
  );
};
