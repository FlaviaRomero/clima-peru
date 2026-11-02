"""
PASO 3 y 4 - Limpieza de datos e indicadores
============================================
Lee la data cruda de NASA POWER, la limpia y calcula indicadores de variación
de temperatura y precipitación por provincia y por departamento.

Uso:  python 02_limpieza_indicadores.py
Entrada: data/raw/power_mensual_largo.csv, data/raw/provincias.geojson
Salida:  data/processed/*.csv
"""
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parent
RAW = BASE / "data" / "raw"
PROC = BASE / "data" / "processed"
PROC.mkdir(parents=True, exist_ok=True)

NORMAL = (1991, 2020)        # periodo de referencia climática (estándar de la OMM)
UMBRAL_DESIERTO_MM = 100     # con menos lluvia anual, el coeficiente de variación no es interpretable

# %% 1. Carga y revisión inicial
largo = pd.read_csv(RAW / "power_mensual_largo.csv", dtype={"id_prov": str, "id_dep": str})
print("Filas crudas:", f"{len(largo):,}")
print(largo.variable.value_counts())

# %% 2. Limpieza
# 2.1 POWER agrega un "mes 13" con el valor anual: se elimina, los anuales se calculan aquí
largo = largo[largo.mes.between(1, 12)].copy()

# 2.2 POWER usa -999 para datos faltantes
n_faltantes = (largo.valor <= -999).sum()
largo.loc[largo.valor <= -999, "valor"] = np.nan
print("Valores -999 convertidos a NaN:", n_faltantes)

# 2.3 Duplicados
n_dup = largo.duplicated(["id_prov", "variable", "anio", "mes"]).sum()
largo = largo.drop_duplicates(["id_prov", "variable", "anio", "mes"])
print("Duplicados eliminados:", n_dup)

# 2.4 Formato ancho: una fila por provincia-año-mes
info_prov = largo[["id_prov", "provincia", "departamento", "id_dep", "lat", "lon",
                   "elev_celda_m"]].drop_duplicates("id_prov")
mensual = (largo.pivot(index=["id_prov", "anio", "mes"], columns="variable", values="valor")
           .reset_index()
           .rename(columns={"T2M": "t_media", "T2M_MAX": "t_max", "T2M_MIN": "t_min",
                            "T2M_RANGE": "rango_termico", "PRECTOTCORR": "prec_mm_dia"}))
mensual.columns.name = None
mensual = info_prov.merge(mensual, on="id_prov")

# 2.5 Precipitación: de mm/día (promedio del mes) a mm totales del mes
dias_mes = pd.to_datetime(dict(year=mensual.anio, month=mensual.mes, day=1)).dt.days_in_month
mensual["prec_mm"] = mensual.prec_mm_dia * dias_mes

# 2.6 Controles de consistencia
assert (mensual.prec_mm.dropna() >= 0).all(), "Hay precipitación negativa"
incoherentes = ((mensual.t_min > mensual.t_media) | (mensual.t_media > mensual.t_max)).sum()
print("Meses con t_min > t_media o t_media > t_max:", incoherentes)

# 2.7 Solo años completos (12 meses con dato de temperatura y lluvia)
completos = (mensual.dropna(subset=["t_media", "prec_mm"])
             .groupby(["id_prov", "anio"]).mes.count().rename("n_meses").reset_index())
mensual = mensual.merge(completos, on=["id_prov", "anio"], how="left")
mensual = mensual[mensual.n_meses == 12].drop(columns="n_meses")
print("Años completos:", mensual.anio.min(), "-", mensual.anio.max())
print("Provincias:", mensual.id_prov.nunique())
mensual.to_csv(PROC / "mensual_provincias.csv", index=False)

# %% 3. Series anuales por provincia
anual = (mensual.groupby(["id_prov", "anio"])
         .agg(t_media=("t_media", "mean"), rango_termico=("rango_termico", "mean"),
              prec_anual_mm=("prec_mm", "sum"))
         .reset_index())
anual.to_csv(PROC / "anual_provincias.csv", index=False)

anio_ini, anio_fin = int(anual.anio.min()), int(anual.anio.max())
n = 15
periodo_1 = (anio_ini, anio_ini + n - 1)    # primeros 15 años
periodo_2 = (anio_fin - n + 1, anio_fin)    # últimos 15 años


# %% 4. Indicadores por provincia
def pendiente_por_decada(x, y):
    """Tendencia lineal (mínimos cuadrados) expresada por cada 10 años."""
    ok = ~np.isnan(y)
    return np.polyfit(x[ok], y[ok], 1)[0] * 10 if ok.sum() > 10 else np.nan


filas = []
for id_prov, a in anual.groupby("id_prov"):
    m = mensual[mensual.id_prov == id_prov]
    normal_a = a[a.anio.between(*NORMAL)]
    normal_m = m[m.anio.between(*NORMAL)]
    clim = normal_m.groupby("mes").agg(t=("t_media", "mean"), p=("prec_mm", "mean"))
    p1 = a[a.anio.between(*periodo_1)]
    p2 = a[a.anio.between(*periodo_2)]
    prec_media = normal_a.prec_anual_mm.mean()
    anio_max = a.loc[a.prec_anual_mm.idxmax()]
    filas.append({
        "id_prov": id_prov,
        # nivel (clima normal)
        "t_media_c": normal_a.t_media.mean(),
        "prec_anual_mm": prec_media,
        # A. variación diaria
        "rango_termico_c": normal_a.rango_termico.mean(),
        # B. variación estacional
        "amplitud_estacional_t_c": clim.t.max() - clim.t.min(),
        "pct_lluvia_dic_mar": 100 * clim.p.loc[[12, 1, 2, 3]].sum() / clim.p.sum(),
        # C. variación entre años
        "sd_t_anual_c": normal_a.t_media.std(),
        "cv_prec_pct": (100 * normal_a.prec_anual_mm.std() / prec_media
                        if prec_media >= UMBRAL_DESIERTO_MM else np.nan),
        "anio_mas_lluvioso": int(anio_max.anio),
        "veces_lluvia_normal": anio_max.prec_anual_mm / prec_media if prec_media > 0 else np.nan,
        # D. cambio de largo plazo
        "tendencia_t_c_decada": pendiente_por_decada(a.anio.values.astype(float), a.t_media.values),
        "cambio_t_c": p2.t_media.mean() - p1.t_media.mean(),
        "cambio_prec_pct": (100 * (p2.prec_anual_mm.mean() / p1.prec_anual_mm.mean() - 1)
                            if prec_media >= UMBRAL_DESIERTO_MM else np.nan),
    })

ind = pd.DataFrame(filas)
info = mensual[["id_prov", "provincia", "departamento", "id_dep", "lat", "lon",
                "elev_celda_m"]].drop_duplicates("id_prov")
ind = info.merge(ind, on="id_prov")

# Índice compuesto de variabilidad (0-100): promedio de percentiles de cuatro dimensiones
componentes = ["rango_termico_c", "amplitud_estacional_t_c", "cv_prec_pct", "tendencia_t_c_decada"]
ind["indice_variabilidad"] = (ind[componentes].rank(pct=True).mean(axis=1, skipna=True) * 100).round(1)
ind = ind.round(2).sort_values("indice_variabilidad", ascending=False)
ind.to_csv(PROC / "indicadores_provincias.csv", index=False)
print(ind.head(10)[["provincia", "departamento", "indice_variabilidad"] + componentes])

# %% 5. Indicadores por departamento (promedio de sus provincias, ponderado por superficie)
geo = gpd.read_file(RAW / "provincias.geojson")[["id_prov", "ha"]]
ind_dep = ind.merge(geo, on="id_prov")
cols = [c for c in ind.columns if c not in ("id_prov", "provincia", "departamento", "id_dep",
                                            "lat", "lon", "anio_mas_lluvioso")]


def prom_ponderado(g):
    out = {}
    for c in cols:
        ok = g[c].notna()
        out[c] = np.average(g.loc[ok, c], weights=g.loc[ok, "ha"]) if ok.any() else np.nan
    out["n_provincias"] = len(g)
    return pd.Series(out)


dep = (ind_dep.groupby(["id_dep", "departamento"]).apply(prom_ponderado, include_groups=False)
       .reset_index().round(2).sort_values("indice_variabilidad", ascending=False))
dep.to_csv(PROC / "indicadores_departamentos.csv", index=False)
print(dep[["departamento", "indice_variabilidad", "rango_termico_c", "cv_prec_pct",
           "tendencia_t_c_decada"]].to_string(index=False))

# %% 6. Serie nacional (promedio de provincias, para el gráfico de tendencia)
nacional = anual.groupby("anio")[["t_media", "prec_anual_mm"]].mean().reset_index()
base = nacional[nacional.anio.between(*NORMAL)]
nacional["anomalia_t_c"] = nacional.t_media - base.t_media.mean()
nacional["anomalia_prec_pct"] = 100 * (nacional.prec_anual_mm / base.prec_anual_mm.mean() - 1)
nacional.round(3).to_csv(PROC / "serie_nacional.csv", index=False)
print(f"\nPeriodos comparados: {periodo_1} vs {periodo_2}")
print("Listo: archivos en", PROC)
