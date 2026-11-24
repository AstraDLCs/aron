// Piezas de interfaz compartidas por Organigrama, Carpeta de CVs, Bitácora y Configuración.
import { useEffect, type ReactNode } from 'react';
import { AlertTriangle, CheckCircle2, Info, Loader2, X, XCircle } from 'lucide-react';

export const inputClass =
  'w-full min-h-[38px] rounded-lg border border-[#D8DCE0] bg-white px-3 text-sm text-[#23272E] placeholder:text-[#9AA0A8] focus:border-[#B26337] focus:outline-none focus:ring-2 focus:ring-[#B26337]/15 disabled:bg-[#F7F7F8] disabled:text-[#9AA0A8]';

export const textareaClass =
  'w-full rounded-lg border border-[#D8DCE0] bg-white px-3 py-2 text-sm text-[#23272E] placeholder:text-[#9AA0A8] focus:border-[#B26337] focus:outline-none focus:ring-2 focus:ring-[#B26337]/15';

type Variant = 'primary' | 'secondary' | 'danger' | 'ghost';

const variantClass: Record<Variant, string> = {
  primary: 'bg-[#B26337] text-white hover:bg-[#99522B] border border-[#B26337]',
  secondary: 'bg-white text-[#23272E] border border-[#D8DCE0] hover:bg-[#F7F7F8]',
  danger: 'bg-white text-[#B42318] border border-[#F3C5C0] hover:bg-[#FEF3F2]',
  ghost: 'bg-transparent text-[#5C626D] border border-transparent hover:bg-[#EFEFF1] hover:text-[#23272E]',
};

export function Button({
  children,
  onClick,
  variant = 'secondary',
  size = 'md',
  icon,
  disabled,
  loading,
  title,
  type = 'button',
  className = '',
}: {
  children?: ReactNode;
  onClick?: () => void;
  variant?: Variant;
  size?: 'sm' | 'md';
  icon?: ReactNode;
  disabled?: boolean;
  loading?: boolean;
  title?: string;
  type?: 'button' | 'submit';
  className?: string;
}) {
  const sizeClass = size === 'sm' ? 'h-8 px-2.5 text-xs gap-1.5' : 'h-9 px-3.5 text-sm gap-2';
  return (
    <button
      type={type}
      title={title}
      onClick={onClick}
      disabled={disabled || loading}
      className={`inline-flex shrink-0 items-center justify-center rounded-lg font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${sizeClass} ${variantClass[variant]} ${className}`}
    >
      {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : icon}
      {children}
    </button>
  );
}

export function Card({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <div className={`rounded-xl border border-[#E2E4E8] bg-white ${className}`}>{children}</div>;
}

export function SectionHeader({
  icon,
  title,
  subtitle,
  actions,
}: {
  icon?: ReactNode;
  title: string;
  subtitle?: string;
  actions?: ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-4">
      <div className="flex items-start gap-3">
        {icon && (
          <div className="mt-0.5 flex h-10 w-10 items-center justify-center rounded-lg bg-[#FBF4EE] text-[#B26337]">
            {icon}
          </div>
        )}
        <div>
          <h1 className="font-display text-xl font-bold text-[#23272E]">{title}</h1>
          {subtitle && <p className="mt-0.5 text-sm text-[#5C626D]">{subtitle}</p>}
        </div>
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}

export function Field({
  label,
  hint,
  children,
  className = '',
}: {
  label: string;
  hint?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <label className={`block ${className}`}>
      <span className="mb-1 block text-xs font-semibold text-[#23272E]">{label}</span>
      {children}
      {hint && <span className="mt-1 block text-xs text-[#5C626D]">{hint}</span>}
    </label>
  );
}

export function Modal({
  open = true,
  title,
  subtitle,
  onClose,
  children,
  footer,
  width = 'max-w-lg',
}: {
  open?: boolean;
  title: string;
  subtitle?: string;
  onClose: () => void;
  children: ReactNode;
  footer?: ReactNode;
  width?: string;
}) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-[#23272E]/40 p-4" onMouseDown={onClose}>
      <div
        className={`flex max-h-[90vh] w-full ${width} flex-col overflow-hidden rounded-xl border border-[#E2E4E8] bg-white shadow-xl`}
        onMouseDown={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
      >
        <div className="flex items-start justify-between gap-4 border-b border-[#E2E4E8] px-5 py-4">
          <div>
            <h2 className="font-display text-base font-bold text-[#23272E]">{title}</h2>
            {subtitle && <p className="mt-0.5 text-xs text-[#5C626D]">{subtitle}</p>}
          </div>
          <button
            onClick={onClose}
            className="rounded-md p-1 text-[#5C626D] hover:bg-[#EFEFF1] hover:text-[#23272E]"
            aria-label="Cerrar"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto px-5 py-4">{children}</div>
        {footer && (
          <div className="flex flex-wrap items-center justify-end gap-2 border-t border-[#E2E4E8] bg-[#F7F7F8] px-5 py-3">
            {footer}
          </div>
        )}
      </div>
    </div>
  );
}

export function ConfirmDialog({
  title,
  message,
  confirmLabel = 'Confirmar',
  danger,
  busy,
  error,
  onConfirm,
  onCancel,
}: {
  title: string;
  message: ReactNode;
  confirmLabel?: string;
  danger?: boolean;
  busy?: boolean;
  error?: string | null;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  return (
    <Modal
      title={title}
      onClose={onCancel}
      width="max-w-md"
      footer={
        <>
          <Button onClick={onCancel} disabled={busy}>
            Cancelar
          </Button>
          <Button variant={danger ? 'danger' : 'primary'} onClick={onConfirm} loading={busy}>
            {confirmLabel}
          </Button>
        </>
      }
    >
      <div className="text-sm leading-relaxed text-[#23272E]">{message}</div>
      {error && (
        <div className="mt-3">
          <Notice kind="error">{error}</Notice>
        </div>
      )}
    </Modal>
  );
}

type NoticeKind = 'info' | 'warning' | 'error' | 'success';

const noticeStyle: Record<NoticeKind, { cls: string; icon: ReactNode }> = {
  info: { cls: 'border-[#D5DEEA] bg-[#F3F6FA] text-[#2F4A6B]', icon: <Info className="h-4 w-4 shrink-0" /> },
  warning: {
    cls: 'border-[#E6CDBE] bg-[#FBF4EE] text-[#8C4722]',
    icon: <AlertTriangle className="h-4 w-4 shrink-0" />,
  },
  error: { cls: 'border-[#F3C5C0] bg-[#FEF3F2] text-[#B42318]', icon: <XCircle className="h-4 w-4 shrink-0" /> },
  success: {
    cls: 'border-[#C8E0D2] bg-[#F1F8F4] text-[#2E6B4B]',
    icon: <CheckCircle2 className="h-4 w-4 shrink-0" />,
  },
};

export function Notice({
  kind = 'info',
  children,
  action,
  onDismiss,
}: {
  kind?: NoticeKind;
  children: ReactNode;
  action?: ReactNode;
  onDismiss?: () => void;
}) {
  const s = noticeStyle[kind];
  return (
    <div className={`flex items-start gap-2.5 rounded-lg border px-3.5 py-2.5 text-sm ${s.cls}`}>
      <span className="mt-0.5">{s.icon}</span>
      <div className="min-w-0 flex-1">{children}</div>
      {action}
      {onDismiss && (
        <button onClick={onDismiss} className="rounded p-0.5 opacity-70 hover:opacity-100" aria-label="Cerrar aviso">
          <X className="h-3.5 w-3.5" />
        </button>
      )}
    </div>
  );
}

export function EmptyState({
  icon,
  title,
  description,
  action,
}: {
  icon?: ReactNode;
  title: string;
  description?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center px-6 py-12 text-center">
      {icon && (
        <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-[#EFEFF1] text-[#5C626D]">
          {icon}
        </div>
      )}
      <p className="font-display text-sm font-bold text-[#23272E]">{title}</p>
      {description && <p className="mt-1 max-w-md text-sm text-[#5C626D]">{description}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

export function Badge({
  children,
  tone = 'neutral',
  title,
}: {
  children: ReactNode;
  tone?: 'neutral' | 'accent' | 'green' | 'red' | 'blue' | 'amber';
  title?: string;
}) {
  const tones = {
    neutral: 'bg-[#EFEFF1] text-[#5C626D] border-[#E2E4E8]',
    accent: 'bg-[#FBF4EE] text-[#99522B] border-[#E6CDBE]',
    green: 'bg-[#F1F8F4] text-[#2E6B4B] border-[#C8E0D2]',
    red: 'bg-[#FEF3F2] text-[#B42318] border-[#F3C5C0]',
    blue: 'bg-[#F3F6FA] text-[#2F4A6B] border-[#D5DEEA]',
    amber: 'bg-[#FFF8E6] text-[#8A6100] border-[#F0DCA8]',
  } as const;
  return (
    <span
      title={title}
      className={`inline-flex items-center gap-1 whitespace-nowrap rounded-full border px-2 py-0.5 text-[11px] font-semibold ${tones[tone]}`}
    >
      {children}
    </span>
  );
}

export function Spinner({ label }: { label?: string }) {
  return (
    <span className="inline-flex items-center gap-2 text-sm text-[#5C626D]">
      <Loader2 className="h-4 w-4 animate-spin" />
      {label}
    </span>
  );
}

export function Toggle({
  checked,
  onChange,
  label,
  description,
  disabled,
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
  label: string;
  description?: string;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className="flex w-full items-start gap-3 text-left disabled:opacity-50"
    >
      <span
        className={`relative mt-0.5 inline-flex h-5 w-9 shrink-0 items-center rounded-full transition-colors ${
          checked ? 'bg-[#B26337]' : 'bg-[#D8DCE0]'
        }`}
      >
        <span
          className={`inline-block h-4 w-4 rounded-full bg-white shadow transition-transform ${
            checked ? 'translate-x-4' : 'translate-x-0.5'
          }`}
        />
      </span>
      <span>
        <span className="block text-sm font-semibold text-[#23272E]">{label}</span>
        {description && <span className="block text-xs text-[#5C626D]">{description}</span>}
      </span>
    </button>
  );
}

export function formatDateTime(iso?: string | null): string {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString('es-PE', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export function formatDate(iso?: string | null): string {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString('es-PE', { day: '2-digit', month: '2-digit', year: 'numeric' });
}
