# Mapa de calor de viviendas de uso turístico (VUT) · Marbella

**Mapa:** https://josehino.github.io/mapa-vut-marbella/

15.457 VUT situadas en el mapa (de 15.781 inscritas), 90.180 plazas, en 3.733 parcelas catastrales (descarga del 01/10/2026).

## Actualización automática
Se actualiza **cada día a las 08:00** con una tarea programada de Windows en el ordenador de AMMA (`actualizar_local.cmd`, lanzado por `actualizar_mapas_vut.cmd`). Si el equipo está apagado a esa hora, se ejecuta al encenderlo.
1. Descarga el registro turístico completo y regenera el mapa. Si la descarga falla o llega incompleta, no se publica nada y se mantiene la versión anterior.
2. Pregunta al Catastro solo por las parcelas nuevas o pendientes (como mucho 1.500 por día); en el resto solo recalcula qué viviendas son VUT.
3. Publica en GitHub solo si algo ha cambiado.

No se usa GitHub Actions porque, desde sus servidores (fuera de España), la API de la Junta corta las descargas grandes y el servicio de unidades del Catastro rechaza la conexión.

## Fuentes oficiales
- **Registro de Turismo de Andalucía (RTA)**: API OpenRTA de la Junta de Andalucía. Cada VUT trae sus coordenadas (UTM ETRS89 huso 30), su referencia catastral y su bloque, planta y puerta. 324 VUT vienen sin coordenadas válidas y no aparecen en el mapa.
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
- `generar_mapa.py`: descarga el RTA y regenera `index.html` y `vut_index.json`.
- `generar_edificios.py`: descarga del Catastro las unidades y la volumetría de cada parcela y genera `data/edificios/*.json`.
