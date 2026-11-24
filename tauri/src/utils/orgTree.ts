import type { Position } from '../types';

export type TreeNode = { position: Position; children: TreeNode[] };

function byOrder(a: Position, b: Position): number {
  const s = (a.sortOrder ?? 0) - (b.sortOrder ?? 0);
  return s !== 0 ? s : a.name.localeCompare(b.name, 'es');
}

/** Árbol del organigrama: ordena por `sortOrder` y luego por nombre. Un `parentId` inexistente se trata como raíz. */
export function buildTree(positions: Position[]): TreeNode[] {
  const ids = new Set(positions.map((p) => p.id));
  const childrenOf = new Map<string | null, Position[]>();
  for (const p of positions) {
    const parent = p.parentId && ids.has(p.parentId) && p.parentId !== p.id ? p.parentId : null;
    const list = childrenOf.get(parent) ?? [];
    list.push(p);
    childrenOf.set(parent, list);
  }
  const visited = new Set<string>();
  const build = (parent: string | null): TreeNode[] =>
    (childrenOf.get(parent) ?? [])
      .slice()
      .sort(byOrder)
      .filter((p) => !visited.has(p.id))
      .map((p) => {
        visited.add(p.id);
        return { position: p, children: build(p.id) };
      });
  return build(null);
}

/** Ids del puesto y de todos sus subordinados (directos e indirectos). */
export function descendantsOf(id: string, positions: Position[]): Set<string> {
  const result = new Set<string>([id]);
  let changed = true;
  while (changed) {
    changed = false;
    for (const p of positions) {
      if (p.parentId && result.has(p.parentId) && !result.has(p.id)) {
        result.add(p.id);
        changed = true;
      }
    }
  }
  return result;
}

/** Ruta "Gerencia › Jefatura › Puesto" para mostrar en selectores. */
export function positionPath(id: string, positions: Position[]): string {
  const byId = new Map(positions.map((p) => [p.id, p]));
  const parts: string[] = [];
  let cur = byId.get(id);
  const guard = new Set<string>();
  while (cur && !guard.has(cur.id)) {
    guard.add(cur.id);
    parts.unshift(cur.name);
    cur = cur.parentId ? byId.get(cur.parentId) : undefined;
  }
  return parts.join(' › ');
}
