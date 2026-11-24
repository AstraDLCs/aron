// Prueba de humo de la interfaz: inicia sesión, recorre todas las pestañas y abre los diálogos con «+ Nuevo…»,
// registrando errores de JavaScript y capturas. Usa Edge/Chrome headless por CDP (sin dependencias).
//
//   1. API local encendida (docker compose ... up -d) y la app en modo navegador:  npx vite --port 1420
//   2. node scripts/smoke-ui.mjs
//
// Variables: APP_URL (http://localhost:1420), SMOKE_EMAIL, SMOKE_PASSWORD, BROWSER (ruta de msedge/chrome),
// OUT_DIR (capturas), SEED_OLD_SUMMARY=1 (precarga un resumen de sincronización con el formato anterior).
import { spawn } from 'node:child_process';
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const APP_URL = process.env.APP_URL ?? 'http://localhost:1420';
const EMAIL = process.env.SMOKE_EMAIL ?? 'demo@pulsolaboral.local';
const PASSWORD = process.env.SMOKE_PASSWORD ?? 'Demo12345!';
const BROWSER = process.env.BROWSER ?? 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe';
const OUT_DIR = process.env.OUT_DIR ?? join(tmpdir(), 'pulso-smoke');
const PORT = 9333;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

mkdirSync(OUT_DIR, { recursive: true });
const profile = mkdtempSync(join(tmpdir(), 'pulso-smoke-profile-'));
const browser = spawn(BROWSER, [
  '--headless=new', `--remote-debugging-port=${PORT}`, `--user-data-dir=${profile}`,
  '--window-size=1440,1000', '--no-first-run', '--disable-gpu', 'about:blank',
], { stdio: 'ignore' });

async function pageWs() {
  for (let i = 0; i < 50; i++) {
    try {
      const list = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json();
      const page = list.find((t) => t.type === 'page');
      if (page) return page.webSocketDebuggerUrl;
    } catch { /* todavía arrancando */ }
    await sleep(200);
  }
  throw new Error('El navegador no abrió el puerto de depuración');
}

const ws = new WebSocket(await pageWs());
await new Promise((r) => ws.addEventListener('open', r, { once: true }));
let seq = 0;
const pending = new Map();
const errors = [];
ws.addEventListener('message', (m) => {
  const msg = JSON.parse(m.data);
  if (msg.id) {
    const cb = pending.get(msg.id);
    pending.delete(msg.id);
    cb?.(msg);
  } else if (msg.method === 'Runtime.exceptionThrown') {
    const d = msg.params.exceptionDetails;
    errors.push(`EXCEPCIÓN: ${d.exception?.description ?? d.text}`.slice(0, 600));
  } else if (msg.method === 'Runtime.consoleAPICalled' && msg.params.type === 'error') {
    errors.push(`console.error: ${msg.params.args.map((a) => a.value ?? a.description ?? '').join(' ')}`.slice(0, 600));
  }
});
const send = (method, params = {}) =>
  new Promise((res, rej) => {
    const id = ++seq;
    pending.set(id, (m) => (m.error ? rej(new Error(`${method}: ${m.error.message}`)) : res(m.result)));
    ws.send(JSON.stringify({ id, method, params }));
  });
const evaluate = async (expression) => {
  const r = await send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true });
  if (r.exceptionDetails) throw new Error(r.exceptionDetails.exception?.description ?? r.exceptionDetails.text);
  return r.result.value;
};
const waitFor = async (expression, what, timeout = 15000) => {
  const end = Date.now() + timeout;
  while (Date.now() < end) {
    if (await evaluate(expression).catch(() => false)) return;
    await sleep(200);
  }
  throw new Error(`Tiempo agotado esperando: ${what}`);
};
const shot = async (name) => {
  const { data } = await send('Page.captureScreenshot', { format: 'png' });
  const file = join(OUT_DIR, `${name}.png`);
  writeFileSync(file, Buffer.from(data, 'base64'));
  return file;
};
// Clic en el primer botón visible cuyo texto contenga `text`.
const click = (text, sel = 'button') =>
  evaluate(`(() => {
    const el = [...document.querySelectorAll(${JSON.stringify(sel)})]
      .find((b) => b.offsetParent !== null && b.textContent.replace(/\\s+/g, ' ').includes(${JSON.stringify(text)}));
    if (!el) return false; el.click(); return true; })()`);
// Elige una opción por valor en el <select> que contiene una opción con ese valor (como lo haría React).
const choose = (value, nth = 0) =>
  evaluate(`(() => {
    const sel = [...document.querySelectorAll('select')].filter((s) => [...s.options].some((o) => o.value === ${JSON.stringify(value)}))[${nth}];
    if (!sel) return false;
    const set = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value').set;
    set.call(sel, ${JSON.stringify(value)}); sel.dispatchEvent(new Event('change', { bubbles: true })); return true; })()`);
const typeInto = (selector, value) =>
  evaluate(`(() => {
    const el = document.querySelector(${JSON.stringify(selector)}); if (!el) return false;
    const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
    set.call(el, ${JSON.stringify(value)}); el.dispatchEvent(new Event('input', { bubbles: true })); return true; })()`);
const rendered = () => evaluate(`(document.getElementById('root')?.innerText ?? '').trim().length`);

const results = [];
async function step(name, fn) {
  const before = errors.length;
  let fail = null;
  try {
    await fn();
    await sleep(900);
    const chars = await rendered();
    if (chars < 80) fail = `pantalla casi vacía (${chars} caracteres)`;
  } catch (e) {
    fail = e.message;
  }
  const newErrors = errors.slice(before);
  if (!fail && newErrors.some((e) => e.startsWith('EXCEPCIÓN'))) fail = 'excepción de JavaScript';
  const file = await shot(name.replace(/[^a-z0-9]+/gi, '-').toLowerCase()).catch(() => '');
  results.push({ name, ok: !fail, fail, errors: newErrors, file });
  console.log(`${fail ? 'FALLA' : 'ok   '}  ${name}${fail ? ` — ${fail}` : ''}`);
  for (const e of newErrors) console.log(`        ${e}`);
}

try {
  await send('Runtime.enable');
  await send('Page.enable');
  await send('Page.navigate', { url: APP_URL });
  await waitFor(`!!document.querySelector('input[type=email]')`, 'pantalla de ingreso');
  await evaluate(`localStorage.removeItem('pl-token'); true`);
  if (process.env.SEED_OLD_SUMMARY === '1') {
    const old = {
      root: 'C:/cvs/rrhh', origin: 'sync_local', scanned: 13, uploaded: 5, duplicates: 7, deletedBefore: 0,
      unmatchedFolders: [{ folder: 'agente-de-seguridad-patrimonial', kind: 'puesto', count: 1 }],
      skipped: [], errors: [], uploadedFiles: [], duplicateFiles: [], deletedBeforeFiles: [],
      finishedAt: new Date().toISOString(),
    };
    await evaluate(`localStorage.setItem('pulso.lastSyncSummary', ${JSON.stringify(JSON.stringify(old))}); true`);
  }
  // Marca la página actual: tras recargar hay que esperar a la página NUEVA, no al formulario de la anterior.
  await evaluate(`window.__antesDeRecargar = true; true`);
  await send('Page.reload');
  await waitFor(
    `!window.__antesDeRecargar && document.readyState === 'complete' && !!document.querySelector('input[type=email]')`,
    'pantalla de ingreso tras recargar',
  );

  await step('Ingreso', async () => {
    await typeInto('input[type=email]', EMAIL);
    await typeInto('input[type=password]', PASSWORD);
    await click('Ingresar', 'button[type=submit]');
    await waitFor(`document.body.innerText.includes('Cerrar sesión')`, 'pantalla principal');
  });

  for (const tab of ['Candidatos', 'Organigrama', 'Requerimientos', 'Carpeta de CVs', 'Pruebas']) {
    await step(`Pestaña ${tab}`, async () => {
      if (!(await click(tab))) throw new Error(`no se encontró la pestaña ${tab}`);
    });
  }
  const MORE = ['Procesos KPI', 'Reportes', 'Bitácora', 'Configuración'];
  for (const tab of MORE) {
    await step(`Pestaña ${tab}`, async () => {
      // El botón del menú dice «Más», o el nombre de la pestaña secundaria activa.
      let opened = await click('Más');
      for (const label of MORE) if (!opened) opened = await click(label);
      if (!opened) throw new Error('no se encontró el menú Más');
      await sleep(300);
      if (!(await click(tab))) throw new Error(`no se encontró ${tab} en el menú`);
    });
  }

  await step('Subir CV: «+ Nueva fuente…» y «+ Nuevo puesto…»', async () => {
    await click('Candidatos');
    await sleep(500);
    if (!(await click('Subir CV'))) throw new Error('no se encontró el botón Subir CV');
    await waitFor(`document.body.innerText.includes('Subir CVs')`, 'diálogo Subir CVs');
    if (!(await choose('__nuevo__', 1))) throw new Error('no hay opción «+ Nueva fuente…»');
    await waitFor(`document.body.innerText.includes('Nueva fuente')`, 'mini formulario de fuente');
    if (!(await choose('__nuevo__', 0))) throw new Error('no hay opción «+ Nuevo puesto…»');
    await waitFor(`document.body.innerText.includes('Nuevo puesto')`, 'mini formulario de puesto');
  });
  await step('Subir CV: cerrar', async () => {
    await click('Cancelar');
    await sleep(300);
    await click('Cancelar');
  });

  await step('Alta manual: «+ Nuevo…»', async () => {
    if (!(await click('Nuevo candidato'))) throw new Error('no se encontró Nuevo candidato');
    await waitFor(`document.body.innerText.includes('alta manual')`, 'formulario de alta manual');
    if (!(await choose('__nuevo__', 2))) throw new Error('no hay «+ Nueva fuente…» en el alta manual');
    await waitFor(`document.body.innerText.includes('Nueva fuente')`, 'mini formulario de fuente');
  });
} catch (e) {
  results.push({ name: 'ejecución', ok: false, fail: e.message, errors: [], file: '' });
  console.log(`FALLA  ejecución — ${e.message}`);
} finally {
  ws.close();
  browser.kill();
  await sleep(500);
  try { rmSync(profile, { recursive: true, force: true }); } catch { /* perfil en uso */ }
}

const failed = results.filter((r) => !r.ok);
writeFileSync(join(OUT_DIR, 'resultado.json'), JSON.stringify(results, null, 2));
console.log(`\n${results.length - failed.length}/${results.length} pasos sin errores. Capturas en ${OUT_DIR}`);
process.exit(failed.length ? 1 : 0);
