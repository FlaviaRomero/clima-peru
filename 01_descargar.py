"""
PASO 2 - Descarga de datos
==========================
Descarga, para cada una de las 196 provincias del Perú, la serie mensual de
temperatura y precipitación de NASA POWER (1991-2025), y los límites
provinciales del INEI.

Fuentes (públicas, sin clave):
- NASA POWER, API mensual por punto: https://power.larc.nasa.gov/docs/services/api/temporal/monthly/
- Límites provinciales (INEI) del repositorio peru-geojson: https://github.com/juaneladio/peru-geojson

Uso:  python 01_descargar.py
Tarda unos 5 a 15 minutos. Si se corta, vuelve a ejecutarlo: las provincias
ya descargadas se guardan en data/raw/power/ y no se vuelven a pedir.
"""
from pathlib import Path
import json
import time

import geopandas as gpd
import pandas as pd
import requests

BASE = Path(__file__).resolve().parent
RAW = BASE / "data" / "raw"
CACHE = RAW / "power"
CACHE.mkdir(parents=True, exist_ok=True)

URL_PROVINCIAS = "https://raw.githubusercontent.com/juaneladio/peru-geojson/master/peru_provincial_simple.geojson"
URL_POWER = "https://power.larc.nasa.gov/api/temporal/monthly/point"

# T2M: temperatura media | T2M_MAX / T2M_MIN: máxima y mínima del mes
# T2M_RANGE: rango térmico (máx - mín) | PRECTOTCORR: precipitación (mm/día)
VARIABLES = "T2M,T2M_MAX,T2M_MIN,T2M_RANGE,PRECTOTCORR"
ANIO_INICIO, ANIO_FIN = 1991, 2025


# %% 1. Límites provinciales y un punto representativo por provincia
provincias = gpd.read_file(URL_PROVINCIAS)
provincias = provincias.rename(columns={"FIRST_IDPR": "id_prov", "NOMBPROV": "provincia",
                                        "FIRST_NOMB": "departamento"})
provincias["id_dep"] = provincias["id_prov"].str[:2]
# Limpieza: el mapa trae 2 provincias partidas en dos polígonos con el nombre mal escrito
# ("PUIRA" y "VICTOR FAFARDO"). Se unen por código (UBIGEO) y se conserva el nombre del trozo más grande.
print("Polígonos en el archivo:", len(provincias), "| códigos repetidos:", provincias.id_prov.duplicated().sum())
provincias = provincias.sort_values("ha", ascending=False)
provincias = provincias.dissolve(by="id_prov", aggfunc={"provincia": "first", "departamento": "first",
                                                        "id_dep": "first", "ha": "sum"}).reset_index()
# representative_point() siempre cae DENTRO del polígono (el centroide no siempre)
puntos = provincias.to_crs(32718).representative_point().to_crs(4326)
provincias["lat"], provincias["lon"] = puntos.y.round(4), puntos.x.round(4)
provincias.to_file(RAW / "provincias.geojson", driver="GeoJSON")
print(f"{len(provincias)} provincias")
print(provincias[["id_prov", "provincia", "departamento", "lat", "lon"]].head())


# %% 2. Descarga de NASA POWER (una consulta por provincia, con caché)
def pedir_power(lat, lon, anio_fin):
    params = {"parameters": VARIABLES, "community": "AG", "latitude": lat, "longitude": lon,
              "start": ANIO_INICIO, "end": anio_fin, "format": "JSON"}
    r = requests.get(URL_POWER, params=params, timeout=180)
    r.raise_for_status()
    return r.json()


def descargar(fila):
    destino = CACHE / f"{fila.id_prov}.json"
    if destino.exists():
        return json.loads(destino.read_text())
    for intento in range(4):
        try:
            try:
                datos = pedir_power(fila.lat, fila.lon, ANIO_FIN)
            except requests.HTTPError:
                # si el último año aún no está completo en POWER, se pide hasta el anterior
                datos = pedir_power(fila.lat, fila.lon, ANIO_FIN - 1)
            destino.write_text(json.dumps(datos))
            return datos
        except Exception as e:
            espera = 2 ** (intento + 1)
            print(f"   {fila.provincia}: error ({e}); reintento en {espera} s")
            time.sleep(espera)
    raise RuntimeError(f"No se pudo descargar {fila.provincia}")


filas = []
for i, fila in enumerate(provincias.itertuples(), start=1):
    ya_estaba = (CACHE / f"{fila.id_prov}.json").exists()
    datos = descargar(fila)
    coords = datos["geometry"]["coordinates"]
    elev = coords[2] if len(coords) > 2 else None   # altitud de la celda de NASA POWER
    param = datos["properties"]["parameter"]
    for var, serie in param.items():
        for clave, valor in serie.items():
            filas.append({"id_prov": fila.id_prov, "provincia": fila.provincia,
                          "departamento": fila.departamento, "id_dep": fila.id_dep,
                          "lat": fila.lat, "lon": fila.lon, "elev_celda_m": elev,
                          "variable": var, "anio": int(clave[:4]), "mes": int(clave[4:]),
                          "valor": valor})
    if not ya_estaba:
        print(f"[{i}/{len(provincias)}] {fila.provincia} ({fila.departamento}) OK")
        time.sleep(0.5)   # pausa corta para no saturar el servicio

# %% 3. Guardar en formato largo (una fila por provincia, variable, año y mes)
largo = pd.DataFrame(filas)
largo.to_csv(RAW / "power_mensual_largo.csv", index=False)
print(largo.shape)
print(largo.head())
print("\nAños descargados:", largo.anio.min(), "-", largo.anio.max())
