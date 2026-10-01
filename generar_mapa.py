"""
Mapa de calor de Viviendas de Uso Turistico (VUT) de Marbella.

Fuente oficial: Registro de Turismo de Andalucia (RTA), Junta de Andalucia.
Se usa la descarga completa del dataset (OpenRTA /all, JSON regenerado cada noche),
bajada en trozos (rangos HTTP) porque el servidor corta las descargas largas; la API
de busqueda solo se usa para contrastar el total de VUT de Marbella.
Cada VUT trae sus coordenadas (UTM ETRS89 30N) y su referencia catastral.

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


DATASET = "https://www.juntadeandalucia.es/ssdigitales/festa/download-pro/dataset-openrta.json"
UA = {"User-Agent": "Mozilla/5.0"}


def descarga_por_trozos(url, path, trozo=4 * 1024 * 1024):
    h = urllib.request.urlopen(urllib.request.Request(url, method="HEAD", headers=UA), timeout=60)
    total, etag = int(h.headers["Content-Length"]), h.headers.get("ETag")
    with open(path, "wb") as f:
        pos = 0
        while pos < total:
            fin = min(pos + trozo, total) - 1
            for intento in range(8):
                try:
                    req = urllib.request.Request(url, headers={**UA, "Range": f"bytes={pos}-{fin}"})
                    r = urllib.request.urlopen(req, timeout=120)
                    if etag and r.headers.get("ETag") not in (None, etag):
                        sys.exit("El dataset ha cambiado durante la descarga; no se publica nada")
                    b = r.read()
                    if len(b) == fin - pos + 1:
                        break
                except Exception as e:
                    print(f"  trozo {pos}: intento {intento + 1} fallido ({e})", flush=True)
                time.sleep(5 * (intento + 1))
            else:
                sys.exit(f"No se ha podido descargar el trozo {pos}-{fin} del RTA; no se publica nada")
            f.write(b)
            pos = fin + 1
    if os.path.getsize(path) != total:
        sys.exit("Descarga del RTA incompleta; no se publica nada")
    print(f"RTA completo descargado: {total / 1e6:.0f} MB", flush=True)


# -- 1. Registro ----------------------------------------------------------------
try:
    rta_fecha = str(get_json(API + "/search/lastUpdateData", 60).get("date") or "")[:10]
except Exception:
    rta_fecha = ""
ruta = os.path.join(BASE, "rta_completo.json")
if os.environ.get("USE_CACHE") != "1" or not os.path.exists(ruta):
    descarga_por_trozos(DATASET, ruta)
todos = json.load(open(ruta, encoding="utf8"))
recs = [r for r in todos if r.get("object_type_id") == 46
        and str(r.get("municipalities") or "").strip().upper() == "MARBELLA"]
del todos
print(f"RTA ({rta_fecha}): {len(recs)} VUT en Marbella", flush=True)

# contraste con el total que da la API de busqueda (consulta pequena, funciona desde GitHub)
try:
    q = {"id": "-", "object_type": "Vivienda de uso turístico", "category": "-", "group": "-", "modality": "-",
         "province": "-", "municipality": "MARBELLA", "order_by": "id", "mode": "ASC", "format": "json", "size": "1"}
    esperado = get_json(API + "/search?" + urllib.parse.urlencode(q), 120)["total_hits"]
    print(f"API: {esperado} VUT en Marbella")
    if abs(len(recs) - esperado) > max(20, esperado * 0.01):
        sys.exit("El dataset completo no cuadra con la API; no se publica nada")
except (KeyError, OSError, ValueError) as e:
    print(f"(no se ha podido contrastar con la API: {e})")
if len(recs) < 10000:
    sys.exit("Registro sospechosamente corto; no se publica nada")

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
    w = csv.writer(f, delimiter=";", lineterminator="\n")
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
