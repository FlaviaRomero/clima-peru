# ¿Qué territorios del Perú presentan mayores variaciones de temperatura o precipitación?

Tarea 3, Python Intermedio. Parte 1: análisis de datos.

## Pregunta
¿Qué provincias y departamentos del Perú presentan las mayores variaciones de temperatura o precipitación
entre 1991 y 2025?

"Variación" se mide en cuatro dimensiones:

| Dimensión | Indicador | Qué significa |
|---|---|---|
| A. Diaria | Rango térmico (°C) | Diferencia entre la temperatura máxima y la mínima |
| B. Estacional | Amplitud estacional (°C) y % de lluvia entre diciembre y marzo | Diferencia entre el mes más cálido y el más frío; concentración de la lluvia |
| C. Entre años | Coeficiente de variación de la lluvia anual (%) y desviación estándar de la temperatura anual | Qué tan distinto es un año de otro (por ejemplo, El Niño) |
| D. Largo plazo | Tendencia de temperatura (°C por década) y cambio de lluvia (últimos 15 años frente a los primeros 15) | Calentamiento y cambio en la lluvia |

El **índice de variabilidad (0-100)** promedia los percentiles del rango térmico, la amplitud estacional, el
coeficiente de variación de la lluvia y la tendencia de temperatura.

## Fuentes
- **NASA POWER**, API mensual por punto (reanálisis MERRA-2, celdas de unos 50 km): T2M, T2M_MAX, T2M_MIN,
  T2M_RANGE y PRECTOTCORR. https://power.larc.nasa.gov
- **Límites provinciales del INEI**, repositorio peru-geojson: https://github.com/juaneladio/peru-geojson

## Cómo ejecutarlo (Visual Studio Code)
```bash
python -m venv .venv
# Windows:   .venv\Scripts\activate
# Mac/Linux: source .venv/bin/activate
pip install -r requirements.txt

python 01_descargar.py            # descarga (5-15 min)
python 02_limpieza_indicadores.py # limpieza e indicadores
python 03_hallazgos.py            # gráficos y hallazgos
```
Cada script tiene celdas `# %%`: en VS Code puedes correrlas una por una con **Run Cell**
(requiere la extensión de Python y Jupyter).

## Limpieza realizada
- El mapa del INEI trae 197 polígonos: dos provincias partidas con el nombre mal escrito ("PUIRA" y
  "VICTOR FAFARDO"). Se unieron por código y quedan 195 provincias.
- Se eliminó el "mes 13" (anual) que agrega NASA POWER; los anuales se recalculan.
- Los valores -999 (faltantes) se convirtieron a NaN; se eliminaron duplicados.
- La precipitación pasó de mm/día a mm por mes.
- Solo se usan años completos (12 meses).
- El coeficiente de variación de la lluvia no se calcula donde llueve menos de 100 mm al año, porque en el
  desierto costero cualquier llovizna lo dispara.

## Limitaciones
- Se toma un punto representativo por provincia. NASA POWER tiene celdas de unos 50 km, así que las provincias
  pequeñas (sobre todo en Lima y la costa) pueden compartir la misma celda, y la altitud de la celda es un
  promedio suavizado.
- Es un reanálisis, no una medición de estación: puede diferir de SENAMHI, sobre todo en la sierra.
- El mapa no incluye la provincia de Putumayo (Loreto), creada en 2014.
- Los promedios por departamento ponderan sus provincias por superficie.
- El aumento de lluvia de +158 % en Castrovirreyna y de +99 % en Chupaca probablemente es un error del reanálisis (cambios en los datos que usa el modelo con el tiempo), no un cambio real; no se usa como hallazgo.
- El calentamiento de Ucayali es muy alto comparado con el resto del país; habría que validarlo con estaciones de SENAMHI.

## Estructura
```
01_descargar.py              Paso 2: descarga
02_limpieza_indicadores.py   Pasos 3 y 4: limpieza e indicadores
03_hallazgos.py              Paso 5: gráficos y hallazgos
data/raw/                    datos crudos
data/processed/              datos limpios e indicadores (los usará el dashboard)
resultados/                  gráficos y hallazgos.md
```
Hallazgo 1. La costa norte tiene la lluvia más irregular del país por El Niño.
Sechura y Paita (Piura) tienen un coeficiente de variación de la lluvia anual de 175 % y 171 %, el más alto del Perú. En 1998, durante El Niño 1997-98, llovió 9 veces más de lo normal en Paita y Sechura, y 7 veces más en la provincia de Piura. En esa zona, un año “promedio” casi no existe: o casi no llueve o llueve de forma extrema.

Hallazgo 2. En el altiplano la diferencia entre el día y la noche es cuatro veces mayor que en la costa.
Lampa, San Román y Azángaro (Puno) tienen un rango térmico diario de 16 °C, frente a solo 4 °C en Camaná y Paita, donde el mar modera la temperatura. A mayor altitud, mayor rango (correlación de 0.67). Esto explica por qué las heladas golpean al sur andino aun cuando los días son templados.

Hallazgo 3. El Perú se está calentando, y 2023-2024 fueron los años más cálidos del periodo.
El 97 % de las provincias muestra una tendencia de calentamiento entre 1991 y 2025. 2023 y 2024 superaron el promedio 1991-2020 en +1.10 °C y +1.39 °C, en coincidencia con El Niño 2023-24. El mayor calentamiento aparece en Ucayali (0.6 a 0.7 °C por década en Atalaya, Padre Abad y Coronel Portillo).