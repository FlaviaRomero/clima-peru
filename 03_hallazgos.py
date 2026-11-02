"""
PASO 5 - Hallazgos
==================
Genera rankings, gráficos y un resumen de hallazgos con cifras.

Uso:  python 03_hallazgos.py
Salida: resultados/*.png y resultados/hallazgos.md
"""
from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import pandas as pd

BASE = Path(__file__).resolve().parent
RAW = BASE / "data" / "raw"
PROC = BASE / "data" / "processed"
OUT = BASE / "resultados"
OUT.mkdir(exist_ok=True)

ind = pd.read_csv(PROC / "indicadores_provincias.csv", dtype={"id_prov": str})
dep = pd.read_csv(PROC / "indicadores_departamentos.csv")
anual = pd.read_csv(PROC / "anual_provincias.csv", dtype={"id_prov": str})
nac = pd.read_csv(PROC / "serie_nacional.csv")
geo = gpd.read_file(RAW / "provincias.geojson")[["id_prov", "geometry"]]
mapa = geo.merge(ind, on="id_prov")

plt.rcParams.update({"figure.dpi": 120, "axes.spines.top": False, "axes.spines.right": False})


def top(df, col, n=5, asc=False):
    return df.dropna(subset=[col]).sort_values(col, ascending=asc).head(n)


def lista(df, col, unidad, n=5, asc=False, nombre="provincia", dec=1):
    t = top(df, col, n, asc)
    extra = t.departamento if nombre == "provincia" else None
    partes = []
    for i, (_, f) in enumerate(t.iterrows()):
        etiqueta = f"{f[nombre].title()}" + (f" ({f.departamento.title()})" if extra is not None else "")
        partes.append(f"{etiqueta}: {f[col]:.{dec}f}{unidad}")
    return "; ".join(partes)


# %% Figura 1: mapas de las cuatro dimensiones
dims = [("rango_termico_c", "A. Rango térmico diario (°C)", "YlOrRd"),
        ("amplitud_estacional_t_c", "B. Amplitud estacional de temperatura (°C)", "PuRd"),
        ("cv_prec_pct", "C. Variación de la lluvia entre años (CV %)", "Blues"),
        ("tendencia_t_c_decada", "D. Calentamiento (°C por década)", "Reds")]
fig, axs = plt.subplots(1, 4, figsize=(18, 7))
for ax, (col, titulo, cmap) in zip(axs, dims):
    mapa.plot(column=col, cmap=cmap, legend=True, ax=ax, edgecolor="white", linewidth=0.2,
              missing_kwds={"color": "#dddddd", "label": "sin dato / desierto"},
              legend_kwds={"shrink": 0.6})
    ax.set_title(titulo, fontsize=10)
    ax.set_axis_off()
fig.suptitle("Variación climática por provincia, Perú (NASA POWER)", fontsize=13)
fig.tight_layout()
fig.savefig(OUT / "fig1_mapas_dimensiones.png", bbox_inches="tight")

# %% Figura 2: índice compuesto por departamento
d = dep.sort_values("indice_variabilidad")
fig, ax = plt.subplots(figsize=(7, 8))
ax.barh(d.departamento.str.title(), d.indice_variabilidad, color="#c0504d")
ax.set_xlabel("Índice de variabilidad climática (0-100)")
ax.set_title("¿Qué departamentos tienen el clima más variable?")
fig.tight_layout()
fig.savefig(OUT / "fig2_indice_departamentos.png", bbox_inches="tight")

# %% Figura 3: lluvia anual de las provincias con lluvia más irregular
t3 = top(ind, "cv_prec_pct", 3)
fig, ax = plt.subplots(figsize=(10, 4.5))
for _, f in t3.iterrows():
    s = anual[anual.id_prov == f.id_prov]
    ax.plot(s.anio, s.prec_anual_mm, marker="o", ms=3,
            label=f"{f.provincia.title()} ({f.departamento.title()})")
for a in (1998, 2017, 2023):
    ax.axvline(a, color="grey", ls=":", lw=1)
ax.set_ylabel("Precipitación anual (mm)")
ax.set_title("Las provincias con la lluvia más irregular (líneas punteadas: años de El Niño costero/fuerte)")
ax.legend()
fig.tight_layout()
fig.savefig(OUT / "fig3_lluvia_irregular.png", bbox_inches="tight")

# %% Figura 4: anomalía de temperatura nacional
fig, ax = plt.subplots(figsize=(10, 4))
colores = ["#c0504d" if v > 0 else "#4f81bd" for v in nac.anomalia_t_c]
ax.bar(nac.anio, nac.anomalia_t_c, color=colores)
ax.axhline(0, color="black", lw=0.8)
ax.set_ylabel("°C respecto a 1991-2020")
ax.set_title("Anomalía de temperatura media anual, promedio de provincias del Perú")
fig.tight_layout()
fig.savefig(OUT / "fig4_anomalia_temperatura.png", bbox_inches="tight")

# %% Figura 5: rango térmico vs altitud de la celda
if ind.elev_celda_m.notna().any():
    fig, ax = plt.subplots(figsize=(7, 5))
    ax.scatter(ind.elev_celda_m, ind.rango_termico_c, s=14, alpha=0.7, color="#c0504d")
    ax.set_xlabel("Altitud de la celda NASA POWER (m s. n. m.)")
    ax.set_ylabel("Rango térmico diario (°C)")
    ax.set_title("Rango térmico diario según la altitud")
    fig.tight_layout()
    fig.savefig(OUT / "fig5_rango_vs_altitud.png", bbox_inches="tight")

# %% Hallazgos con cifras
corr = ind[["elev_celda_m", "rango_termico_c"]].corr().iloc[0, 1] if ind.elev_celda_m.notna().any() else float("nan")
calent = (ind.tendencia_t_c_decada > 0).mean() * 100
ult = nac.tail(5)
texto = f"""# Hallazgos (Parte 1)

Datos: NASA POWER, {int(anual.anio.min())}-{int(anual.anio.max())}, {ind.id_prov.nunique()} provincias. Clima normal: 1991-2020.

## 1. Variación diaria (diferencia entre el día y la noche)
Mayor rango térmico (máxima menos mínima): {lista(ind, "rango_termico_c", " °C")}.
Menor rango: {lista(ind, "rango_termico_c", " °C", asc=True)}.
Correlación entre altitud y rango térmico: {corr:.2f}.

## 2. Variación entre años: la lluvia más irregular
Mayor coeficiente de variación de la lluvia anual (solo provincias con más de 100 mm al año):
{lista(ind, "cv_prec_pct", " %")}.
Año más lluvioso de esas provincias: {", ".join(f"{f.provincia.title()} {int(f.anio_mas_lluvioso)} ({f.veces_lluvia_normal:.1f} veces lo normal)" for _, f in top(ind, "cv_prec_pct", 3).iterrows())}.

## 3. Variación estacional
Mayor diferencia de temperatura entre el mes más cálido y el más frío: {lista(ind, "amplitud_estacional_t_c", " °C")}.
Lluvia más concentrada entre diciembre y marzo: {lista(ind, "pct_lluvia_dic_mar", " %")}.

## 4. Cambio de largo plazo
El {calent:.0f} % de las provincias muestra una tendencia de calentamiento.
Mayor calentamiento: {lista(ind, "tendencia_t_c_decada", " °C/década", dec=2)}.
Anomalía nacional de los últimos 5 años: {", ".join(f"{int(a)}: {v:+.2f} °C" for a, v in zip(ult.anio, ult.anomalia_t_c))}.
Mayor aumento de lluvia (últimos 15 años vs primeros 15): {lista(ind, "cambio_prec_pct", " %")}.
Mayor disminución: {lista(ind, "cambio_prec_pct", " %", asc=True)}.

## 5. Índice compuesto (0-100)
Departamentos con el clima más variable: {lista(dep, "indice_variabilidad", "", nombre="departamento")}.
Departamentos con el clima más estable: {lista(dep, "indice_variabilidad", "", asc=True, nombre="departamento")}.
"""
(OUT / "hallazgos.md").write_text(texto, encoding="utf-8")
print(texto)
print("Gráficos guardados en", OUT)
