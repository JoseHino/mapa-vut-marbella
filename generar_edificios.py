"""
Datos por edificio para la vista 3D del mapa de VUT (incremental).

Para cada parcela con VUT necesita del Catastro:
 - Consulta_DNPRC (14 car.): todas las unidades del edificio con escalera/planta/puerta.
 - INSPIRE WFS BU (GetBuildingPartByParcel): huella de cada cuerpo y nº de plantas.
y cruza las VUT del registro turistico por referencia catastral (vut_index.json,
generado por generar_mapa.py: rc18 -> [registro(s), plazas, alta, nº VUT]).

Base fija + actualizacion diaria:
 - La base (unidades y volumetria de cada parcela) cambia muy poco: se descarga del Catastro
   solo cuando se ejecuta sin OFFLINE (refresco manual, p. ej. anual, desde un equipo en Espana;
   el servicio de unidades del Catastro no responde a los servidores de GitHub).
 - Cada dia (OFFLINE=1, en GitHub Actions) se reutiliza esa base y solo se recalcula que
   unidades son VUT, de modo que una VUT nueva en un edificio conocido aparece tambien en el 3D.
 - Las parcelas nuevas quedan "pendientes" de 3D hasta el siguiente refresco de la base.
 - Las fichas no se borran aunque la parcela se quede sin VUT (se reescriben con 0 VUT).

Salida: data/edificios/<parcela>.json
"""

import glob, json, os, re, threading, time, urllib.request
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

BASE = os.path.dirname(os.path.abspath(__file__))
IDX = os.path.join(BASE, "vut_index.json")
RAW = os.path.join(BASE, "cache_catastro")          # cache local opcional (no se sube al repo)
OUT = os.path.join(BASE, "data", "edificios")
os.makedirs(OUT, exist_ok=True)
UA = {"User-Agent": "Mozilla/5.0"}
URL_DNP = ("https://ovc.catastro.meh.es/ovcservweb/OVCSWLocalizacionRC/OVCCallejero.asmx/"
           "Consulta_DNPRC?Provincia=&Municipio=&RC={}")
URL_BU = ("https://ovc.catastro.meh.es/INSPIRE/wfsBU.aspx?service=wfs&version=2&request=getfeature"
          "&STOREDQUERIE_ID=GetBuildingPartByParcel&refcat={}&srsname=EPSG::25830")
OFFLINE = os.environ.get("OFFLINE") == "1"           # no preguntar al Catastro
MAX_NUEVAS = int(os.environ.get("MAX_NUEVAS", "1500"))  # parcelas nuevas por ejecucion
limite = threading.Event()                           # el Catastro ha cortado por peticiones/hora


def descarga(url, cache):
    if os.path.exists(cache) and os.path.getsize(cache) > 200:
        return open(cache, "rb").read().decode("utf8" if cache.endswith("_dnp.xml") else "latin-1", "ignore")
    if OFFLINE or limite.is_set():
        return None
    for i in range(3):
        try:
            b = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=90).read()
            if b"limite de peticiones" in b or b"Peticion denegada" in b:
                limite.set()
                return None
            if len(b) > 200:
                if os.path.isdir(RAW):
                    open(cache, "wb").write(b)
                return b.decode("utf8" if cache.endswith("_dnp.xml") else "latin-1", "ignore")
        except Exception as e:
            if "403" in str(e):
                limite.set()
                return None
        time.sleep(3 * (i + 1))
    return None


def tag(t, s):
    m = re.search(rf"<{t}>([^<]*)</{t}>", s)
    return m.group(1).strip() if m else ""


def unidades(xml):
    # Lista (varias unidades) -> <rcdnp>; unidad unica -> <bico>
    bloques = re.findall(r"<rcdnp>(.*?)</rcdnp>", xml, re.S) or re.findall(r"<bico>(.*?)</bico>", xml, re.S)
    out = []
    for b in bloques:
        loint = re.search(r"<loint>(.*?)</loint>", b, re.S)
        li = loint.group(1) if loint else ""
        out.append([tag("es", li), tag("pt", li), tag("pu", li), tag("luso", b)[:1], tag("car", b)])
    return out


def cuerpos_de(xml):
    ps = []
    for bp in re.findall(r"<bu-ext2d:BuildingPart (.*?)</bu-ext2d:BuildingPart>", xml, re.S):
        sobre = re.search(r"numberOfFloorsAboveGround>(\d*)<", bp)
        bajo = re.search(r"numberOfFloorsBelowGround>(\d*)<", bp)
        anillos = []
        for pl in re.findall(r"<gml:posList[^>]*>([^<]+)</gml:posList>", bp):
            v = [float(x) for x in pl.split()]
            anillos.append(list(zip(v[0::2], v[1::2])))
        if anillos:
            ps.append([int(sobre.group(1)) if sobre and sobre.group(1) else 0,
                       int(bajo.group(1)) if bajo and bajo.group(1) else 0, anillos])
    # coordenadas locales (m) respecto al centro de la huella
    pts = [p for _, _, an in ps for a in an for p in a]
    cx = sum(p[0] for p in pts) / len(pts) if pts else 0
    cy = sum(p[1] for p in pts) / len(pts) if pts else 0
    cuerpos = [[s, b, [[[round(x - cx, 2), round(y - cy, 2)] for x, y in a] for a in an]] for s, b, an in ps]
    return [round(cx, 1), round(cy, 1)], cuerpos


def base_previa(pc):
    """Unidades y volumetria ya conocidas de la parcela (ficha publicada con 'car'), o None."""
    f = os.path.join(OUT, pc + ".json")
    if not os.path.exists(f):
        return None
    j = json.load(open(f, encoding="utf8"))
    if j.get("u") and len(j["u"][0]) < 6:            # ficha antigua sin 'car': no reutilizable
        return None
    return {"c": j["c"], "cuerpos": j["cuerpos"], "u": [[*u[:4], u[5]] for u in j["u"]],
            "error": j.get("error"), "visto": j.get("visto")}


vut = json.load(open(IDX, encoding="utf8"))
por_pc = defaultdict(dict)
for rc, v in vut.items():
    if re.fullmatch(r"[0-9A-Z]{14}", rc[:14]):
        por_pc[rc[:14]][rc[14:18]] = v
pcs = sorted(por_pc)
hoy = time.strftime("%Y-%m-%d")

# parcelas con ficha que ya no tienen VUT: se conservan (base) y se reescriben sin VUT
previas = {os.path.basename(f)[:-5] for f in glob.glob(os.path.join(OUT, "*.json"))}
sin_vut = previas - set(pcs)
pcs = sorted(set(pcs) | previas)

nuevas = 0
lock = threading.Lock()


def procesa(pc):
    global nuevas
    b = base_previa(pc)
    if b is None:
        dnp_c, bu_c = os.path.join(RAW, pc + "_dnp.xml"), os.path.join(RAW, pc + "_bu.xml")
        en_cache = os.path.exists(dnp_c) and os.path.exists(bu_c)
        if not en_cache and not OFFLINE:
            with lock:
                if nuevas >= MAX_NUEVAS:
                    return pc, "pendiente"
                nuevas += 1
        dnp, bu = descarga(URL_DNP.format(pc), dnp_c), descarga(URL_BU.format(pc), bu_c)
        if dnp is None or bu is None:
            return pc, "pendiente"
        c, cuerpos = cuerpos_de(bu)
        u = unidades(dnp)
        err = tag("des", dnp) if not u else None      # p. ej. "NO EXISTE NINGUN INMUEBLE..."
        b = {"c": c, "cuerpos": cuerpos, "u": u, "error": err, "visto": hoy}
    vs = por_pc.get(pc, {})
    filas = [[es, pt, pu, uso, vs.get(car, 0), car] for es, pt, pu, uso, car in b["u"]]
    j = {"pc": pc, "c": b["c"], "cuerpos": b["cuerpos"], "u": filas,
         "vut": sum(v[3] for v in vs.values()),
         "vut_cruzadas": sum(f[4][3] for f in filas if f[4]),
         "visto": b.get("visto") or hoy}
    if b.get("error"):
        j["error"] = b["error"]
    json.dump(j, open(os.path.join(OUT, pc + ".json"), "w", encoding="utf8"), ensure_ascii=False, separators=(",", ":"))
    return pc, "ok"


with ThreadPoolExecutor(1 if OFFLINE else 6) as ex:
    res = dict(ex.map(procesa, pcs))

pend = [p for p, s in res.items() if s == "pendiente"]
pcs = [p for p in pcs if p not in sin_vut]
print(f"Parcelas con VUT: {len(pcs)} | con ficha: {len(pcs) - len(pend)} | pendientes: {len(pend)} | "
      f"consultadas al Catastro: {nuevas} | fichas sin VUT conservadas: {len(sin_vut)}"
      + (" | LIMITE DEL CATASTRO ALCANZADO" if limite.is_set() else ""))
json.dump({"parcelas": len(pcs), "pendientes": len(pend), "fecha": hoy},
          open(os.path.join(BASE, "data", "estado_edificios.json"), "w"))
