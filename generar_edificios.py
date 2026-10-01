"""
Datos por edificio para la vista 3D del mapa de VUT de Marbella.

Para cada parcela con VUT descarga del Catastro:
 - Consulta_DNPRC (14 car.): todas las unidades del edificio con escalera/planta/puerta.
 - INSPIRE WFS BU (GetBuildingPartByParcel): huella de cada cuerpo y nº de plantas.
y cruza las VUT del Registro de Turismo de Andalucia (RTA) por referencia catastral
(vut_index.json, generado por generar_mapa.py).

Salida: data/edificios/<parcela>.json
"""

import csv, json, os, re, time, urllib.request
from concurrent.futures import ThreadPoolExecutor

BASE = os.path.dirname(os.path.abspath(__file__))
IDX = os.path.join(BASE, "vut_index.json")
RAW = os.path.join(BASE, "cache_catastro")
OUT = os.path.join(BASE, "data", "edificios")
os.makedirs(RAW, exist_ok=True)
os.makedirs(OUT, exist_ok=True)
UA = {"User-Agent": "Mozilla/5.0"}
URL_DNP = ("https://ovc.catastro.meh.es/ovcservweb/OVCSWLocalizacionRC/OVCCallejero.asmx/"
           "Consulta_DNPRC?Provincia=&Municipio=&RC={}")
URL_BU = ("https://ovc.catastro.meh.es/INSPIRE/wfsBU.aspx?service=wfs&version=2&request=getfeature"
          "&STOREDQUERIE_ID=GetBuildingPartByParcel&refcat={}&srsname=EPSG::25830")


OFFLINE = os.environ.get("OFFLINE") == "1"      # solo cache (p. ej. si el Catastro limita peticiones/hora)


def descarga(url, path):
    if os.path.exists(path) and os.path.getsize(path) > 200:
        return open(path, "rb").read()
    if OFFLINE:
        return b""
    for i in range(4):
        try:
            b = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=90).read()
            if len(b) > 200:
                open(path, "wb").write(b)
                return b
        except Exception:
            pass
        time.sleep(3 * (i + 1))
    return b""


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
        out.append({"car": tag("car", b), "es": tag("es", li), "pt": tag("pt", li), "pu": tag("pu", li),
                    "uso": tag("luso", b)})
    return out


def partes(xml):
    res = []
    for bp in re.findall(r"<bu-ext2d:BuildingPart (.*?)</bu-ext2d:BuildingPart>", xml, re.S):
        sobre = re.search(r"numberOfFloorsAboveGround>(\d*)<", bp)
        bajo = re.search(r"numberOfFloorsBelowGround>(\d*)<", bp)
        sobre = int(sobre.group(1)) if sobre and sobre.group(1) else 0
        bajo = int(bajo.group(1)) if bajo and bajo.group(1) else 0
        anillos = []
        for pl in re.findall(r"<gml:posList[^>]*>([^<]+)</gml:posList>", bp):
            v = [float(x) for x in pl.split()]
            anillos.append(list(zip(v[0::2], v[1::2])))
        if anillos:
            res.append({"sobre": sobre, "bajo": bajo, "anillos": anillos})
    return res


def num(v):
    try:
        return float(str(v).replace(",", ".").strip())
    except ValueError:
        return 0


vut = json.load(open(IDX, encoding="utf8"))      # rc18 -> [registro(s), plazas, alta, nº VUT]
pcs = sorted({k[:14] for k in vut if re.fullmatch(r"[0-9A-Z]{14}", k[:14])})
print(f"Parcelas con VUT: {len(pcs)}")


def procesa(pc):
    dnp = descarga(URL_DNP.format(pc), os.path.join(RAW, pc + "_dnp.xml")).decode("utf8", "ignore")
    bu = descarga(URL_BU.format(pc), os.path.join(RAW, pc + "_bu.xml")).decode("latin-1", "ignore")
    if not dnp or not bu:                       # sin datos (limite del Catastro): no generar ficha incompleta
        return pc, 0, 0, 0, 0
    us = unidades(dnp)
    ps = partes(bu)
    # coordenadas locales (m) respecto al centro de la huella
    pts = [p for parte in ps for a in parte["anillos"] for p in a]
    cx = sum(p[0] for p in pts) / len(pts) if pts else 0
    cy = sum(p[1] for p in pts) / len(pts) if pts else 0
    cuerpos = [[parte["sobre"], parte["bajo"],
                [[[round(x - cx, 2), round(y - cy, 2)] for x, y in a] for a in parte["anillos"]]]
               for parte in ps]
    filas, enc = [], 0
    for u in us:
        r = vut.get(pc + u["car"])
        if r:
            enc += r[3]
        filas.append([u["es"], u["pt"], u["pu"], u["uso"][:1],
                      r if r else 0])
    total_vut = sum(v[3] for k, v in vut.items() if k.startswith(pc))
    json.dump({"pc": pc, "c": [round(cx, 1), round(cy, 1)], "cuerpos": cuerpos, "u": filas, "vut": total_vut, "vut_cruzadas": enc},
              open(os.path.join(OUT, pc + ".json"), "w", encoding="utf8"),
              ensure_ascii=False, separators=(",", ":"))
    return pc, len(us), len(ps), total_vut, enc


res = []
with ThreadPoolExecutor(8) as ex:
    for i, x in enumerate(ex.map(procesa, pcs)):
        res.append(x)
        if i % 50 == 0:
            print(i, x, flush=True)

sin_u = [x for x in res if x[1] == 0]
sin_bu = [x for x in res if x[2] == 0]
desc = [x for x in res if x[3] != x[4]]
print(f"Edificios: {len(res)} | sin unidades: {len(sin_u)} | sin volumetria: {len(sin_bu)} | "
      f"con VUT sin cruzar: {len(desc)} ({sum(x[3] - x[4] for x in desc)} VUT)")
print("Unidades totales:", sum(x[1] for x in res))
print("Ejemplos descuadre:", desc[:10])
