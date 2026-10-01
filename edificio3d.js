// Visor 3D por edificio: volumetria real del Catastro (INSPIRE) con cada planta
// coloreada por el % de viviendas que son VUT, y fachada esquematica por escalera.
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

const H = 3;                          // altura de planta (m)
const STOPS = [[0, '#0033ff'], [0.2, '#00ffff'], [0.4, '#00ff00'], [0.6, '#ffff00'], [0.8, '#ff6600'], [1, '#ff0033']];
const SIN_DATOS = '#c9c9c9';
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const pct = x => (x * 100).toLocaleString('es-ES', { maximumFractionDigits: 0 }) + ' %';
const dec = x => x.toLocaleString('es-ES', { maximumFractionDigits: 1 });

function heat(s) {
  for (let i = 1; i < STOPS.length; i++) {
    if (s <= STOPS[i][0]) {
      const [a, ca] = STOPS[i - 1], [b, cb] = STOPS[i];
      return new THREE.Color(ca).lerp(new THREE.Color(cb), (s - a) / (b - a));
    }
  }
  return new THREE.Color(STOPS.at(-1)[1]);
}

// Codigo de planta del Catastro -> numero (null = no sobre rasante / desconocida)
function planta(pt) {
  pt = (pt || '').toUpperCase();
  if (/^[+-]?\d+$/.test(pt)) return +pt;
  if (/^(SS|SM)$/.test(pt)) return -0.5;            // semisotano
  if (/^(BJ|BA|PB|OD|LO|EN|00)$/.test(pt) || pt === '') return 0;
  return null;
}

const natural = (a, b) => a.localeCompare(b, 'es', { numeric: true });

// ---------------------------------------------------------------- UI
const css = `
#v3d { position:fixed; inset:0; z-index:5000; background:rgba(20,20,24,.55); display:none; }
#v3d.on { display:block; }
#v3d .box { position:absolute; inset:16px; background:#fff; border-radius:10px; overflow:hidden; display:flex; box-shadow:0 10px 40px rgba(0,0,0,.35); }
#v3d .cv { position:relative; flex:1 1 60%; min-width:0; min-height:0; overflow:hidden; background:#dfe6ea; }
#v3d .cv canvas { display:block; position:absolute; inset:0; }
#v3d .side { flex:0 0 420px; overflow:auto; padding:16px 18px; font-size:13px; border-left:1px solid #e4e4e4; }
#v3d h2 { font-size:16px; margin:0 26px 2px 0; }
#v3d .sub { color:#666; font-size:12px; margin-bottom:10px; }
#v3d .x { position:absolute; top:10px; right:12px; z-index:2; border:0; background:#fff; border-radius:50%; width:30px; height:30px; font-size:18px; cursor:pointer; box-shadow:0 1px 4px rgba(0,0,0,.25); }
#v3d .kp { display:grid; grid-template-columns:repeat(3,1fr); gap:8px; margin:8px 0 12px; }
#v3d .kp div { border-left:3px solid #1ADEB1; padding-left:8px; }
#v3d .kp b { display:block; font-size:18px; font-variant-numeric:tabular-nums; }
#v3d .kp span { font-size:11px; color:#666; }
#v3d .grad { height:10px; border-radius:5px; background:linear-gradient(90deg,#0033ff,#00ffff,#00ff00,#ffff00,#ff6600,#ff0033); }
#v3d .gl { display:flex; justify-content:space-between; font-size:11px; color:#666; margin-bottom:4px; }
#v3d .note { font-size:11px; color:#666; line-height:1.45; margin:6px 0; }
#v3d h3 { font-size:11px; text-transform:uppercase; letter-spacing:.06em; color:#666; margin:14px 0 6px; border-top:1px solid #eee; padding-top:10px; }
#v3d .fach { overflow:auto; max-width:100%; margin-bottom:6px; }
#v3d table.f { border-collapse:separate; border-spacing:2px; font-size:10px; }
#v3d table.f th { font-weight:normal; color:#666; padding:0 2px; text-align:center; }
#v3d table.f td { width:15px; height:13px; border-radius:2px; background:#e6e6e6; }
#v3d table.f td.v { background:#d7191c; }
#v3d table.f td.n { background:transparent; }
#v3d table.f tr:hover th { color:#1044CD; font-weight:bold; }
#v3d table.f tr.pp td { height:16px; font-size:9px; color:#222; text-align:center; background:transparent; }
#v3d .leg { display:flex; gap:12px; font-size:11px; color:#666; align-items:center; }
#v3d .leg i { display:inline-block; width:12px; height:12px; border-radius:2px; vertical-align:-2px; margin-right:4px; }
#v3d .tip { position:absolute; pointer-events:none; background:rgba(255,255,255,.96); border-radius:5px; padding:5px 8px; font-size:12px; box-shadow:0 2px 8px rgba(0,0,0,.2); display:none; white-space:nowrap; }
#v3d .help { position:absolute; left:10px; bottom:8px; font-size:11px; color:#333; background:rgba(255,255,255,.8); padding:3px 7px; border-radius:4px; }
#v3d .load { position:absolute; inset:0; display:flex; align-items:center; justify-content:center; color:#444; }
#v3d .pb div { display:flex; align-items:center; gap:6px; font-size:11px; margin:1px 0; }
#v3d .pb span:first-child { width:34px; text-align:right; color:#666; font-variant-numeric:tabular-nums; }
#v3d .pb em { height:9px; border-radius:2px; display:inline-block; }
@media (max-width:820px) {
  #v3d .box { inset:0; border-radius:0; flex-direction:column; }
  #v3d .cv { flex:0 0 52%; }
  #v3d .side { flex:1 1 auto; border-left:0; border-top:1px solid #e4e4e4; }
}`;
document.head.insertAdjacentHTML('beforeend', `<style>${css}</style>`);
document.body.insertAdjacentHTML('beforeend', `
<div id="v3d"><div class="box">
  <div class="cv"><div class="load">Cargando edificio…</div><div class="tip"></div>
    <div class="help">Arrastra para girar · rueda para zoom · botón derecho para desplazar</div></div>
  <div class="side"><button class="x" title="Cerrar">×</button><div class="cont"></div></div>
</div></div>`);
const root = document.getElementById('v3d');
const cv = root.querySelector('.cv'), tip = root.querySelector('.tip'), cont = root.querySelector('.cont'), load = root.querySelector('.load');

let renderer, scene, camera, controls, raf, slabs = [], hovered = null;

function cerrar() {
  root.classList.remove('on');
  cancelAnimationFrame(raf);
  if (renderer) { renderer.dispose(); renderer.domElement.remove(); renderer = null; }
}
root.querySelector('.x').onclick = cerrar;
root.addEventListener('click', e => { if (e.target === root) cerrar(); });
addEventListener('keydown', e => { if (e.key === 'Escape' && root.classList.contains('on')) cerrar(); });

// ---------------------------------------------------------------- datos
function analiza(j) {
  const todas = j.u.map(([es, pt, pu, uso, v]) => ({ es: es || '–', pt, pu: pu || '–', f: planta(pt), v }));
  const uds = todas.filter(u => u.f !== null && u.f >= 0);
  const fuera = todas.filter(u => u.v && !(u.f !== null && u.f >= 0)).length;   // VUT en sotano / planta sin codificar
  const pisos = new Map();
  for (const u of uds) {
    const p = pisos.get(u.f) || { n: 0, v: 0 };
    p.n++; if (u.v) p.v++;
    pisos.set(u.f, p);
  }
  // comparacion en altura solo entre unidades de planta 1 o superior (la PB mezcla locales)
  const alt = uds.filter(u => u.f >= 1), vs = alt.filter(u => u.v), ns = alt.filter(u => !u.v);
  const media = a => a.length ? a.reduce((s, u) => s + u.f, 0) / a.length : NaN;
  return { uds, pisos, nv: uds.filter(u => u.v).length, fuera, nV: vs.length, nN: ns.length, mediaV: media(vs), mediaN: media(ns) };
}

// ---------------------------------------------------------------- 3D
function escena(j, A) {
  const W = cv.clientWidth, Hh = cv.clientHeight;
  renderer = new THREE.WebGLRenderer({ antialias: true });
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
  renderer.setSize(W, Hh);
  cv.prepend(renderer.domElement);
  scene = new THREE.Scene();
  scene.background = new THREE.Color('#dfe6ea');
  scene.add(new THREE.HemisphereLight(0xffffff, 0x8899aa, 1.6));
  const sol = new THREE.DirectionalLight(0xffffff, 1.4); sol.position.set(-80, 160, 120); scene.add(sol);

  const g = new THREE.Group();
  g.rotation.x = -Math.PI / 2;          // shape XY (este, norte) -> suelo; extrusion -> arriba
  scene.add(g);
  slabs = [];
  let ext = 10, top = 0;
  const mats = new Map();
  const mat = f => {
    if (!mats.has(f)) {
      const p = A.pisos.get(f);
      const c = p ? heat(p.v / p.n) : new THREE.Color(SIN_DATOS);
      mats.set(f, new THREE.MeshLambertMaterial({ color: c, transparent: !p, opacity: p ? 1 : 0.55 }));
    }
    return mats.get(f);
  };
  const lineMat = new THREE.LineBasicMaterial({ color: 0x333333, transparent: true, opacity: 0.35 });
  for (const [sobre, , anillos] of j.cuerpos) {
    if (!sobre) continue;
    const shape = new THREE.Shape(anillos[0].map(([x, y]) => new THREE.Vector2(x, y)));
    anillos.slice(1).forEach(a => shape.holes.push(new THREE.Path(a.map(([x, y]) => new THREE.Vector2(x, y)))));
    anillos[0].forEach(([x, y]) => { ext = Math.max(ext, Math.abs(x), Math.abs(y)); });
    const geo = new THREE.ExtrudeGeometry(shape, { depth: H * 0.86, bevelEnabled: false });
    const edges = new THREE.EdgesGeometry(geo, 30);
    for (let f = 0; f < sobre; f++) {
      const m = new THREE.Mesh(geo, mat(f));
      m.position.z = f * H; m.userData.f = f;
      g.add(m); slabs.push(m);
      const l = new THREE.LineSegments(edges, lineMat); l.position.z = f * H; g.add(l);
    }
    top = Math.max(top, sobre * H);
  }

  // suelo con ortofoto PNOA (IGN), recortada alrededor del edificio
  const R = Math.max(140, ext * 2.6);
  const [cx, cy] = j.c;
  const url = 'https://www.ign.es/wms-inspire/pnoa-ma?SERVICE=WMS&VERSION=1.3.0&REQUEST=GetMap&LAYERS=OI.OrthoimageCoverage&STYLES=' +
    `&CRS=EPSG:25830&BBOX=${cx - R},${cy - R},${cx + R},${cy + R}&WIDTH=1024&HEIGHT=1024&FORMAT=image/jpeg`;
  const suelo = new THREE.Mesh(new THREE.PlaneGeometry(2 * R, 2 * R), new THREE.MeshBasicMaterial({ color: 0xcfd6da }));
  suelo.rotation.x = -Math.PI / 2; suelo.position.y = -0.05; scene.add(suelo);
  new THREE.TextureLoader().setCrossOrigin('anonymous').load(url, t => {
    t.colorSpace = THREE.SRGBColorSpace;
    suelo.material = new THREE.MeshBasicMaterial({ map: t });
  });

  // norte
  const c = document.createElement('canvas'); c.width = c.height = 128;
  const x = c.getContext('2d');
  x.fillStyle = 'rgba(255,255,255,.9)'; x.beginPath(); x.arc(64, 64, 58, 0, 7); x.fill();
  x.fillStyle = '#222'; x.font = 'bold 72px Segoe UI, Arial'; x.textAlign = 'center'; x.textBaseline = 'middle'; x.fillText('N', 64, 70);
  const n = new THREE.Sprite(new THREE.SpriteMaterial({ map: new THREE.CanvasTexture(c) }));
  n.scale.set(R * 0.07, R * 0.07, 1); n.position.set(0, R * 0.035, -R * 0.92); scene.add(n);

  camera = new THREE.PerspectiveCamera(40, W / Hh, 1, 5000);
  // encuadre: esfera que envuelve el edificio, vista desde el sur-este
  const r = Math.hypot(ext, top / 2) + 5;
  const dist = r / Math.sin(THREE.MathUtils.degToRad(20)) * 1.05;
  const dir = new THREE.Vector3(0.55, 0.45, 0.8).normalize();
  camera.position.copy(dir.multiplyScalar(dist)).add(new THREE.Vector3(0, top / 2, 0));
  controls = new OrbitControls(camera, renderer.domElement);
  controls.target.set(0, top / 2, 0);
  controls.maxPolarAngle = Math.PI * 0.495;
  controls.enableDamping = true;
  controls.update();

  const ray = new THREE.Raycaster(), ptr = new THREE.Vector2();
  renderer.domElement.onpointermove = e => {
    const r = renderer.domElement.getBoundingClientRect();
    ptr.set(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1);
    ray.setFromCamera(ptr, camera);
    const hit = ray.intersectObjects(slabs)[0];
    resalta(hit ? hit.object.userData.f : null);
    if (hit) {
      const f = hit.object.userData.f, p = A.pisos.get(f);
      tip.innerHTML = `<b>${f === 0 ? 'Planta baja' : 'Planta ' + f}</b> · ` +
        (p ? `${p.v} de ${p.n} unidades son VUT (${pct(p.v / p.n)})` : 'sin unidades en el Catastro');
      tip.style.display = 'block';
      tip.style.left = (e.clientX - r.left + 14) + 'px'; tip.style.top = (e.clientY - r.top + 10) + 'px';
    } else tip.style.display = 'none';
  };
  renderer.domElement.onpointerleave = () => { resalta(null); tip.style.display = 'none'; };

  const loop = () => { controls.update(); renderer.render(scene, camera); raf = requestAnimationFrame(loop); };
  loop();
  new ResizeObserver(() => {
    if (!renderer) return;
    renderer.setSize(cv.clientWidth, cv.clientHeight);
    camera.aspect = cv.clientWidth / cv.clientHeight; camera.updateProjectionMatrix();
  }).observe(cv);
}

function resalta(f) {
  if (f === hovered) return;
  hovered = f;
  // todas las losas de una misma planta comparten material
  for (const m of slabs) m.material.emissive.setHex(m.userData.f === f ? 0x555555 : 0);
  cont.querySelectorAll('tr[data-f]').forEach(tr => tr.style.outline = +tr.dataset.f === f ? '1px solid #1044CD' : '');
}

// ---------------------------------------------------------------- panel
function panel(d, j, A) {
  const n = A.uds.length;
  const escs = [...new Set(A.uds.map(u => u.es))].sort(natural);
  const fach = escs.map(es => {
    const todas = A.uds.filter(u => u.es === es);
    const us = todas.filter(u => u.f >= 1);            // la planta baja (locales) va resumida aparte
    const pb = todas.filter(u => u.f < 1);
    const puertas = [...new Set(us.map(u => u.pu))].sort(natural);
    const fl = [...new Set(us.map(u => u.f))].sort((a, b) => b - a);
    const idx = new Map(us.map(u => [u.f + '|' + u.pu, u]));
    const filas = fl.map(f => `<tr data-f="${f}"><th>${f}</th>` + puertas.map(p => {
      const u = idx.get(f + '|' + p);
      if (!u) return '<td class="n"></td>';
      const t = u.v ? `${u.v[0]} · ${u.v[1]} plazas · alta ${u.v[2]}` : 'No inscrita como VUT';
      return `<td class="${u.v ? 'v' : ''}" title="Planta ${f}, puerta ${esc(p)}: ${esc(t)}"></td>`;
    }).join('') + '</tr>').join('');
    const pp = puertas.map(p => {
      const c = us.filter(u => u.pu === p), s = c.filter(u => u.v).length / c.length;
      return `<td title="Puerta ${esc(p)}: ${pct(s)} VUT" style="background:#${heat(s).getHexString()}55">${Math.round(s * 100)}</td>`;
    }).join('');
    const pbv = pb.filter(u => u.v).length;
    const filaPB = pb.length ? `<tr data-f="0"><th>PB</th><td colspan="${Math.max(1, puertas.length)}" class="n" style="font-size:10px;color:#666;text-align:left;white-space:nowrap">` +
      `${pb.length} unidades (locales y viviendas)${pbv ? `, <b style="color:#d7191c">${pbv} VUT</b>` : ''}</td></tr>` : '';
    const nv = todas.filter(u => u.v).length;
    return `<div class="note"><b>Escalera ${esc(es)}</b> · ${nv} VUT de ${todas.length} unidades</div>
      <div class="fach"><table class="f">${puertas.length ? `<tr><th></th>${puertas.map(p => `<th>${esc(p)}</th>`).join('')}</tr>` : ''}${filas}${filaPB}
      ${puertas.length ? `<tr class="pp"><th>% VUT</th>${pp}</tr>` : ''}</table></div>`;
  }).join('');

  const fl = [...A.pisos.keys()].sort((a, b) => b - a);
  const bars = fl.map(f => {
    const p = A.pisos.get(f), s = p.v / p.n;
    return `<div data-f="${f}"><span>${f === 0 ? 'PB' : f}</span><em style="width:${Math.max(2, s * 200)}px;background:#${heat(s).getHexString()}"></em><span style="width:auto;text-align:left">${p.v}/${p.n}</span></div>`;
  }).join('');

  let lectura = '';
  if (A.nV >= 3 && A.nN >= 5) {
    const dif = A.mediaV - A.mediaN;
    lectura = Math.abs(dif) < 1
      ? 'Las VUT están repartidas en altura de forma parecida al resto de viviendas.'
      : `Las VUT tienden a estar <b>más ${dif > 0 ? 'arriba' : 'abajo'}</b> que el resto de viviendas: planta media ${dec(A.mediaV)} frente a ${dec(A.mediaN)}.`;
  }

  cont.innerHTML = `
    <h2>${esc(d[2])}</h2>
    <div class="sub">CP ${esc(d[3])} · parcela catastral ${esc(d[4])}</div>
    <div class="kp">
      <div><b>${A.nv}</b><span>unidades con VUT</span></div>
      <div><b>${n}</b><span>unidades sobre rasante</span></div>
      <div><b>${n ? pct(A.nv / n) : '–'}</b><span>son VUT</span></div>
    </div>
    ${lectura ? `<div class="note">${lectura}</div>` : ''}
    <div class="grad"></div><div class="gl"><span>0 % de la planta es VUT</span><span>100 %</span></div>
    <div class="note">Cada planta del modelo se colorea con el % de sus unidades inscritas como VUT; en gris, plantas sin unidades en el Catastro. Volumen: huella y nº de plantas de cada cuerpo del edificio (Catastro). Suelo: ortofoto PNOA (IGN), con el norte arriba.</div>
    <h3>% VUT por planta</h3>
    <div class="pb">${bars}</div>
    <h3>Fachada esquemática por escalera</h3>
    <div class="leg"><span><i style="background:#d7191c"></i>VUT</span><span><i style="background:#e6e6e6"></i>Otra unidad</span></div>
    <div class="note">Filas = plantas, columnas = puertas. La última fila da el % de VUT de cada puerta: cuando las puertas van por letras (A, B, C…), una letra que concentra VUT en todas las plantas indica una misma posición en el edificio. Si van numeradas correlativamente, cada número es una vivienda distinta. El Catastro no dice hacia dónde mira cada puerta; para saber si es la fachada al mar, compara con la ortofoto o con Street View.</div>
    ${fach}
    <div class="note">La planta baja puede incluir locales comerciales (el Catastro no distingue el uso en esta consulta). Sótanos y garajes excluidos.${A.fuera ? ` ${A.fuera} VUT de este edificio están bajo rasante o sin planta codificada (habitual en edificios en ladera) y no aparecen en el modelo.` : ''}${j.vut !== j.vut_cruzadas ? ` ${j.vut - j.vut_cruzadas} VUT de este edificio no se han podido situar en una unidad catastral.` : ''}</div>`;

  cont.querySelectorAll('[data-f]').forEach(el => {
    el.onmouseenter = () => resalta(+el.dataset.f);
    el.onmouseleave = () => resalta(null);
  });
}

// ---------------------------------------------------------------- entrada
window.abrir3D = async d => {
  root.classList.add('on');
  cont.innerHTML = ''; tip.style.display = 'none'; hovered = null; load.style.display = 'flex'; load.textContent = 'Cargando edificio…';
  if (renderer) { cancelAnimationFrame(raf); renderer.dispose(); renderer.domElement.remove(); renderer = null; }
  try {
    const res = await fetch(`data/edificios/${d[4]}.json`);
    if (res.status === 404) {
      load.textContent = 'La vista 3D de esta parcela aún no está disponible (pendiente de descarga del Catastro).';
      return;
    }
    const j = await res.json();
    if (!j.u.length) {
      load.textContent = `El Catastro no devuelve inmuebles para la parcela ${d[4]}` +
        (j.error ? ` («${j.error.toLowerCase()}»): probablemente la referencia catastral del registro turístico es errónea.` : '.');
      return;
    }
    const A = analiza(j);
    panel(d, j, A);
    load.style.display = 'none';
    if (j.cuerpos.some(c => c[0] > 0)) escena(j, A);
    else { load.style.display = 'flex'; load.textContent = 'El Catastro no tiene volumetría para esta parcela.'; }
  } catch (e) {
    load.textContent = 'No se ha podido cargar el edificio (abre el mapa desde la web, no como archivo local).';
    console.error(e);
  }
};
