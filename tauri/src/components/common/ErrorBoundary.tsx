import { Component, type ErrorInfo, type ReactNode } from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';

/**
 * Si una pestaña falla al dibujarse, muestra el error en esa pestaña en vez de dejar toda la app en blanco.
 * El menú y las demás pestañas siguen funcionando. Usar con `key` = sección para reiniciarlo al cambiar de pestaña.
 */
export class ErrorBoundary extends Component<{ children: ReactNode; area: string }, { error: Error | null }> {
  state: { error: Error | null } = { error: null };

  static getDerivedStateFromError(error: Error) {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error(`Error en ${this.props.area}:`, error, info.componentStack);
  }

  render() {
    const { error } = this.state;
    if (!error) return this.props.children;
    return (
      <div className="mx-auto max-w-2xl rounded-xl border border-red-200 bg-white p-6 shadow-sm">
        <div className="flex items-start gap-3">
          <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-red-600" />
          <div className="min-w-0">
            <h2 className="font-display text-base font-bold text-[#23272E]">«{this.props.area}» tuvo un error al mostrarse</h2>
            <p className="mt-1 text-sm text-[#5C626D]">
              El resto de la aplicación sigue funcionando: puedes ir a otra pestaña o reintentar.
            </p>
            <pre className="mt-3 max-h-40 overflow-auto rounded-lg bg-[#F7F7F8] p-3 text-xs text-red-800">
              {error.message}
            </pre>
            <button
              type="button"
              onClick={() => this.setState({ error: null })}
              className="mt-4 inline-flex items-center gap-1.5 rounded-lg bg-[#B26337] px-4 py-2 text-sm font-semibold text-white hover:bg-[#99522B]"
            >
              <RefreshCw className="h-4 w-4" /> Reintentar
            </button>
          </div>
        </div>
      </div>
    );
  }
}
