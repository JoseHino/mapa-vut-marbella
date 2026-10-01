# Mapa de calor de viviendas de uso turístico (VUT) · Marbella

**Mapa:** https://josehino.github.io/mapa-vut-marbella/

15.457 VUT situadas en el mapa (de 15.781 inscritas), 90.180 plazas, en 3.733 parcelas catastrales (descarga del 01/10/2026).

## Actualización automática (GitHub Actions)
Todo funciona en GitHub, sin depender de ningún ordenador. Una tarea (`.github/workflows/actualizar.yml`) se ejecuta **cada día a las 07:30** (hora de Madrid):
1. Descarga el registro turístico completo y regenera el mapa de calor y las fichas. Si la descarga falla o no cuadra, no se publica nada y se mantiene la versión anterior.
2. Recalcula qué viviendas de cada edificio son VUT sobre la **base fija del Catastro** (unidades y volumetría), así que una VUT nueva en un edificio conocido aparece también en su planta del 3D. Los edificios nuevos salen en el mapa y su 3D se incorpora en la siguiente actualización de la base.
3. Publica solo si algo ha cambiado.

También se puede lanzar a mano desde **Actions → Actualizar datos → Run workflow**.

**Actualizar la base del Catastro** (los edificios cambian poco; basta una vez al año): ejecutar `python generar_edificios.py` sin `OFFLINE` desde un equipo en España (el servicio de unidades del Catastro no responde a los servidores de GitHub) y subir `data/edificios/`.

## Fuentes oficiales
- **Registro de Turismo de Andalucía (RTA)**: Junta de Andalucía, descarga completa del dataset OpenRTA (se regenera cada noche). Cada VUT trae sus coordenadas (UTM ETRS89 huso 30), su referencia catastral y su bloque, planta y puerta. 324 VUT vienen sin coordenadas válidas y no aparecen en el mapa.
- **Dirección General del Catastro**: unidades de cada edificio (`Consulta_DNPRC`) y volumetría (INSPIRE, edificios).

## Mapa
- Mapa de calor con la posición de cada VUT según el RTA, que se puede ponderar por número de viviendas o por plazas.
- Edificios o parcelas con zoom 16 o más: ficha con todas las VUT de la parcela.

## Vista 3D por edificio
Al pulsar un edificio y luego **Ver edificio en 3D**, se abre la volumetría real del Catastro, con cada planta coloreada según el % de unidades inscritas como VUT. Incluye una fachada esquemática por escalera (plantas × puertas) y la ortofoto PNOA como suelo para ver la orientación respecto al mar.

Limitaciones:
- En urbanizaciones, una parcela catastral puede tener varios bloques. El color de cada planta resume todos los bloques a esa altura; la fachada por escalera da el detalle.
- El Catastro no indica hacia dónde mira cada puerta, y la planta baja puede incluir locales.

## Archivos
- `index.html`: el mapa (Leaflet). `edificio3d.js`: visor 3D (three.js).
- `VUT_Marbella_geolocalizadas.csv`: las VUT con lat/lon (EPSG:4326).
- `generar_mapa.py`: descarga el RTA completo (por trozos) y regenera `index.html` y `vut_index.json`.
- `generar_edificios.py`: descarga del Catastro las unidades y la volumetría de cada parcela y genera `data/edificios/*.json`.
