"""
Mapa de calor de Viviendas de Uso Turistico (VUT) de Marbella.

Fuente oficial: Registro de Turismo de Andalucia (RTA), API OpenRTA de la
Junta de Andalucia. Cada VUT trae sus coordenadas (UTM ETRS89 30N) y su
referencia catastral.

 - Mapa de calor: coordenadas de cada VUT segun el RTA.
 - Edificios: VUT agrupadas por parcela catastral (14 primeros caracteres de la RC).
 - vut_index.json: VUT por referencia catastral, para generar_edificios.py (vista 3D).
"""

import csv, json, os, re, sys, time, urllib.parse, urllib.request
from collections import Counter, defaultdict
from datetime import date
from pyproj import Transformer

BASE = os.path.dirname(os.path.abspath(__file__))
API = "https://datos.juntadeandalucia.es/api/v0/openrta"
OUT_HTML = os.path.join(BASE, "index.html")
OUT_CSV = os.path.join(BASE, "VUT_Marbella_geolocalizadas.csv")
OUT_IDX = os.path.join(BASE, "vut_index.json")


def get_json(url, timeout):
    req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "Mozilla/5.0"})
    return json.loads(urllib.request.urlopen(req, timeout=timeout).read().decode("utf-8"))


def pagina(modo, size=8000):
    # La API no pagina y con 10.000 registros suele colgarse: dos lotes de 8.000 (ASC y DESC)
    path = os.path.join(BASE, f"rta_{modo}.json")
    if os.environ.get("USE_CACHE") == "1" and os.path.exists(path):
        return json.load(open(path, encoding="utf8"))
    q = {"id": "-", "object_type": "Vivienda de uso turístico", "category": "-", "group": "-",
         "modality": "-", "province": "-", "municipality": "MARBELLA", "order_by": "id",
         "mode": modo, "format": "json", "size": str(size)}
    for intento in range(4):
        try:
            d = get_json(API + "/search?" + urllib.parse.urlencode(q), 900)
            json.dump(d, open(path, "w", encoding="utf8"), ensure_ascii=False)
            return d
        except Exception as e:
            print(f"RTA {modo}: intento {intento + 1} fallido ({e})", flush=True)
            time.sleep(60)
    sys.exit("No se ha podido descargar el RTA; no se publica nada")


# -- 1. Registro ----------------------------------------------------------------
try:
    rta_fecha = str(get_json(API + "/search/lastUpdateData", 60).get("date") or "")[:10]
except Exception:
    rta_fecha = ""
asc, desc = pagina("ASC"), pagina("DESC")
recs = list({r["id"]: r for r in asc["results"] + desc["results"]}.values())
print(f"RTA ({rta_fecha}): {asc['total_hits']} VUT declaradas, {len(recs)} descargadas")
if len(recs) < asc["total_hits"]:
    sys.exit("Faltan registros del RTA (¿más de 16.000 VUT?): hay que añadir otro lote; no se publica nada")

tr = Transformer.from_crs("EPSG:25830", "EPSG:4326", always_xy=True)


def num(v):
    try:
        return float(str(v).replace(",", ".").strip())
    except (TypeError, ValueError):
        return None


def fecha(v):
    v = str(v or "")[:10]
    m = re.match(r"(\d{4})-?(\d{2})-?(\d{2})", v)          # RTA: AAAAMMDD
    return f"{m.group(3)}/{m.group(2)}/{m.group(1)}" if m else v


def piso(r):
    # bloque / portal / escalera / planta / puerta segun los campos del RTA
    partes = [(e, r.get(k)) for e, k in (("Blq.", "block"), ("Portal", "portal"), ("Esc.", "staircase"),
                                         ("Pl.", "floor"), ("Pta.", "door"))]
    return " ".join(f"{e} {v}" for e, v in partes if v not in (None, "", "No disponible"))


def calle(direccion):
    return re.split(r"\s+(Blq\.|Portal|Esc\.|Plta/Piso|Pta/Letra|Compl\.Dom\.)", direccion or "")[0].strip()


puntos, edif, idx = [], defaultdict(list), {}
sin_geo = 0
for r in recs:
    x, y = num(r.get("coord_x")), num(r.get("coord_y"))
    if not x or not y:
        sin_geo += 1
        continue
    lon, lat = tr.transform(x, y)
    if not (36.40 < lat < 36.65 and -5.10 < lon < -4.70):
        sin_geo += 1
        continue
    rc = re.sub(r"\s", "", str(r.get("catastral_ref") or "")).upper()
    pl = int(num(r.get("tot_gen_places")) or 0)
    v = {"lat": lat, "lon": lon, "reg": r.get("registration_code") or "", "dir": r.get("establishment_address") or "",
         "cp": str(r.get("postal_code") or ""), "plazas": pl, "habs": int(num(r.get("tot_gen_ua")) or 0),
         "alta": fecha(r.get("activity_start_date")), "rc": rc, "mod": r.get("group") or "", "piso": piso(r)}
    puntos.append(v)
    clave = rc[:14] if len(rc) >= 14 else f"sinrc_{lat:.5f}_{lon:.5f}"
    edif[clave].append(v)
    if len(rc) >= 18:                       # varias VUT pueden compartir unidad catastral
        e = idx.get(rc[:18])
        if e:
            e[0] += " + " + v["reg"]; e[1] += pl; e[3] += 1
        else:
            idx[rc[:18]] = [v["reg"], pl, v["alta"], 1]

json.dump(idx, open(OUT_IDX, "w", encoding="utf8"), ensure_ascii=False)

with open(OUT_CSV, "w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f, delimiter=";")
    w.writerow(["registro", "direccion", "cp", "ref_catastral", "plazas", "habitaciones", "modalidad", "alta", "lon", "lat"])
    for v in puntos:
        w.writerow([v["reg"], v["dir"], v["cp"], v["rc"], v["plazas"], v["habs"], v["mod"], v["alta"], f"{v['lon']:.6f}", f"{v['lat']:.6f}"])

# -- 2. Edificios: punto medio de las VUT de la parcela -------------------------
data = []
for pc, lst in edif.items():
    lat = sum(v["lat"] for v in lst) / len(lst)
    lon = sum(v["lon"] for v in lst) / len(lst)
    unidades = [[v["reg"], v["piso"], v["plazas"], v["habs"], v["alta"], 0]
                for v in sorted(lst, key=lambda v: v["dir"])]
    data.append([round(lat, 6), round(lon, 6), calle(lst[0]["dir"])[:90], lst[0]["cp"],
                 pc if not pc.startswith("sinrc_") else "", unidades])
data.sort(key=lambda d: -len(d[5]))
heat = [[round(v["lat"], 5), round(v["lon"], 5), v["plazas"]] for v in puntos]

anios = Counter(v["alta"][-4:] for v in puntos if v["alta"])
cps = Counter(v["cp"] for v in puntos if v["cp"])
meta = {"total": len(puntos), "plazas": sum(v["plazas"] for v in puntos), "edificios": len(data),
        "registro": len(recs), "sin_geo": sin_geo, "fecha": date.today().strftime("%d/%m/%Y"),
        "rta": rta_fecha, "anios": sorted(anios.items()), "cps": cps.most_common(12)}
print(f"Mapeadas {meta['total']} VUT, {meta['plazas']} plazas, {meta['edificios']} parcelas; sin coordenadas {sin_geo}")

html = open(os.path.join(BASE, "plantilla.html"), encoding="utf8").read()
html = html.replace("/*__DATA__*/null", json.dumps(data, ensure_ascii=False, separators=(",", ":")))
html = html.replace("/*__HEAT__*/null", json.dumps(heat, separators=(",", ":")))
html = html.replace("/*__META__*/null", json.dumps(meta, ensure_ascii=False, separators=(",", ":")))
open(OUT_HTML, "w", encoding="utf8").write(html)
print(f"OK -> {OUT_HTML} ({os.path.getsize(OUT_HTML) / 1e6:.1f} MB)")
