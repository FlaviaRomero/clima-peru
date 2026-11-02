"""
PARTE 2 - Dashboard interactivo
===============================
¿Qué territorios del Perú presentan mayores variaciones de temperatura o precipitación?

Uso local:  streamlit run app.py
"""
import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

BASE = Path(__file__).resolve().parent
PROC = BASE / "data" / "processed"
RAW = BASE / "data" / "raw"
NORMAL = (1991, 2020)
ANIOS_NINO = {1998: "El Niño 1997-98", 2017: "El Niño costero 2017", 2023: "El Niño 2023-24"}

st.set_page_config(page_title="Variabilidad climática del Perú", page_icon="🌦️", layout="wide")


# ---------------------------------------------------------------- datos
@st.cache_data
def cargar():
    ind = pd.read_csv(PROC / "indicadores_provincias.csv", dtype={"id_prov": str, "id_dep": str})
    dep = pd.read_csv(PROC / "indicadores_departamentos.csv", dtype={"id_dep": str})
    anual = pd.read_csv(PROC / "anual_provincias.csv", dtype={"id_prov": str})
    anual = anual.merge(ind[["id_prov", "provincia", "departamento"]], on="id_prov")
    geo = json.loads((RAW / "provincias.geojson").read_text(encoding="utf-8"))
    for df in (ind, dep, anual):
        for c in ("provincia", "departamento"):
            if c in df:
                df[c] = df[c].str.title()
    return ind, dep, anual, geo


ind, dep, anual, geo = cargar()
ANIO_MIN, ANIO_MAX = int(anual.anio.min()), int(anual.anio.max())

INDICADORES = {
    "Índice de variabilidad (0-100)": ("indice_variabilidad", "", "Reds"),
    "A. Rango térmico diario (°C)": ("rango_termico_c", " °C", "YlOrRd"),
    "B. Amplitud estacional de temperatura (°C)": ("amplitud_estacional_t_c", " °C", "PuRd"),
    "B. % de lluvia entre diciembre y marzo": ("pct_lluvia_dic_mar", " %", "GnBu"),
    "C. Variación de la lluvia entre años (CV %)": ("cv_prec_pct", " %", "Blues"),
    "D. Calentamiento (°C por década)": ("tendencia_t_c_decada", " °C", "Reds"),
    "D. Cambio de la lluvia (%)": ("cambio_prec_pct", " %", "BrBG"),
    "Temperatura media (°C)": ("t_media_c", " °C", "RdYlBu_r"),
    "Lluvia anual (mm)": ("prec_anual_mm", " mm", "Blues"),
}

# ---------------------------------------------------------------- controles
st.sidebar.title("🎛️ Controles")
nombre_ind = st.sidebar.selectbox("1. Indicador del mapa y del ranking", list(INDICADORES))
col, unidad, escala = INDICADORES[nombre_ind]

deps = sorted(ind.departamento.unique())
sel_deps = st.sidebar.multiselect("2. Departamentos (vacío = todo el Perú)", deps)
rango = st.sidebar.slider("3. Años de las series", ANIO_MIN, ANIO_MAX, (ANIO_MIN, ANIO_MAX))
top_n = st.sidebar.slider("4. Provincias en el ranking", 5, 30, 10)

st.sidebar.markdown("---")
st.sidebar.caption("Fuente: NASA POWER (1991-2025) y límites provinciales del INEI. "
                   "Clima normal: 1991-2020.")

ind_f = ind[ind.departamento.isin(sel_deps)] if sel_deps else ind
anual_f = anual[anual.departamento.isin(sel_deps)] if sel_deps else anual
ambito = ", ".join(sel_deps) if sel_deps else "todo el Perú"

# ---------------------------------------------------------------- encabezado
st.title("🌦️ ¿Qué territorios del Perú tienen el clima más variable?")
st.markdown(
    f"Variación de **temperatura** y **lluvia** en **{ind.id_prov.nunique()} provincias**, de "
    f"{ANIO_MIN} a {ANIO_MAX}, medida en cuatro dimensiones: **A.** entre el día y la noche, "
    "**B.** entre estaciones, **C.** entre años y **D.** de largo plazo. "
    f"Ámbito seleccionado: **{ambito}**.")

# ---------------------------------------------------------------- KPIs
def fila_max(df, c):
    d = df.dropna(subset=[c])
    return d.loc[d[c].idxmax()] if len(d) else None


def kpi(columna, titulo, valor, detalle):
    with columna.container(border=True):
        st.metric(titulo, valor)
        st.caption(detalle)


k1, k2, k3, k4 = st.columns(4)
f = fila_max(ind_f, "rango_termico_c")
kpi(k1, "🌡️ Mayor rango térmico diario", f"{f.rango_termico_c:.1f} °C" if f is not None else "-",
    f"{f.provincia} ({f.departamento})" if f is not None else "")
f = fila_max(ind_f, "cv_prec_pct")
kpi(k2, "🌧️ Lluvia más irregular (CV)", f"{f.cv_prec_pct:.0f} %" if f is not None else "sin dato",
    f"{f.provincia} ({f.departamento})" if f is not None else "zona desértica")
pct = (ind_f.tendencia_t_c_decada > 0).mean() * 100
kpi(k3, "🔥 Provincias que se calientan", f"{pct:.0f} %",
    f"promedio {ind_f.tendencia_t_c_decada.mean():+.2f} °C por década")

serie = anual_f.groupby("anio")[["t_media", "prec_anual_mm"]].mean().reset_index()
base = serie[serie.anio.between(*NORMAL)]
serie["anom_t"] = serie.t_media - base.t_media.mean()
serie["anom_p"] = 100 * (serie.prec_anual_mm / base.prec_anual_mm.mean() - 1)
caliente = serie.loc[serie.anom_t.idxmax()]
kpi(k4, "📅 Año más cálido", f"{int(caliente.anio)}", f"{caliente.anom_t:+.2f} °C sobre el promedio 1991-2020")

# ---------------------------------------------------------------- pestañas
t_mapa, t_rank, t_series, t_rel, t_met = st.tabs(
    ["🗺️ Mapa", "🏆 Rankings", "📈 Series de tiempo", "⛰️ Altitud", "📘 Metodología y limitaciones"])

with t_mapa:
    ids = set(ind_f.id_prov)
    geo_f = {"type": "FeatureCollection",
             "features": [ft for ft in geo["features"] if ft["properties"]["id_prov"] in ids]}
    # centro y zoom según los departamentos elegidos
    alto = max(ind_f.lat.max() - ind_f.lat.min(), (ind_f.lon.max() - ind_f.lon.min()) * 1.3, 0.8)
    zoom = 4.6 if not sel_deps else float(max(4.0, min(8.0, 7.6 - 1.45 * (alto ** 0.5))))
    fig = px.choropleth_map(ind_f, geojson=geo_f, locations="id_prov", featureidkey="properties.id_prov",
                            color=col, color_continuous_scale=escala, opacity=0.85,
                            map_style="white-bg", zoom=zoom,
                            center={"lat": float(ind_f.lat.mean()), "lon": float(ind_f.lon.mean())},
                            hover_name="provincia",
                            hover_data={"departamento": True, "id_prov": False, col: ":.2f",
                                        "rango_termico_c": ":.1f", "cv_prec_pct": ":.0f",
                                        "tendencia_t_c_decada": ":.2f"},
                            labels={col: nombre_ind, "rango_termico_c": "Rango térmico (°C)",
                                    "cv_prec_pct": "CV lluvia (%)",
                                    "tendencia_t_c_decada": "Calentamiento (°C/década)"})
    fig.update_layout(height=680, margin=dict(l=0, r=0, t=10, b=0),
                      coloraxis_colorbar=dict(title=""))
    st.subheader(nombre_ind)
    st.plotly_chart(fig, width="stretch")
    if col in ("cv_prec_pct", "cambio_prec_pct"):
        st.caption("Las provincias en blanco son desierto costero (menos de 100 mm de lluvia al año): "
                   "ahí el porcentaje no es interpretable.")

with t_rank:
    c1, c2 = st.columns(2)
    d = ind_f.dropna(subset=[col]).nlargest(top_n, col).sort_values(col)
    fig = px.bar(d, x=col, y="provincia", orientation="h", color=col, color_continuous_scale=escala,
                 hover_data=["departamento"], labels={col: nombre_ind, "provincia": ""})
    fig.update_layout(height=max(350, 28 * len(d)), coloraxis_showscale=False,
                      margin=dict(l=0, r=0, t=30, b=0))
    c1.subheader(f"Top {top_n} provincias")
    c1.plotly_chart(fig, width="stretch")

    dd = dep[dep.departamento.isin(sel_deps)] if sel_deps else dep
    dd = dd.dropna(subset=[col]).sort_values(col)
    fig = px.bar(dd, x=col, y="departamento", orientation="h", color=col,
                 color_continuous_scale=escala, labels={col: nombre_ind, "departamento": ""})
    fig.update_layout(height=max(350, 28 * len(dd)), coloraxis_showscale=False,
                      margin=dict(l=0, r=0, t=30, b=0))
    c2.subheader("Departamentos (promedio ponderado por superficie)")
    c2.plotly_chart(fig, width="stretch")

with t_series:
    s = serie[serie.anio.between(*rango)]
    st.subheader(f"Anomalía de temperatura, {ambito}")
    fig = go.Figure(go.Bar(x=s.anio, y=s.anom_t,
                           marker_color=["#c0392b" if v > 0 else "#2e86c1" for v in s.anom_t],
                           hovertemplate="%{x}: %{y:+.2f} °C<extra></extra>"))
    fig.update_layout(height=330, yaxis_title="°C respecto a 1991-2020", margin=dict(t=10, b=0))
    st.plotly_chart(fig, width="stretch")

    st.subheader("Lluvia anual por provincia")
    por_defecto = ind_f.dropna(subset=["cv_prec_pct"]).nlargest(3, "cv_prec_pct").provincia.tolist()
    provs = st.multiselect("Elige provincias (por defecto, las de lluvia más irregular)",
                           sorted(ind_f.provincia.unique()), default=por_defecto)
    a = anual_f[anual_f.provincia.isin(provs) & anual_f.anio.between(*rango)]
    fig = px.line(a, x="anio", y="prec_anual_mm", color="provincia", markers=True,
                  labels={"anio": "", "prec_anual_mm": "Precipitación anual (mm)", "provincia": ""})
    for anio, etiqueta in ANIOS_NINO.items():
        if rango[0] <= anio <= rango[1]:
            fig.add_vline(x=anio, line_dash="dot", line_color="grey",
                          annotation_text=etiqueta, annotation_position="top left")
    fig.update_layout(height=420, margin=dict(t=30, b=0))
    st.plotly_chart(fig, width="stretch")

with t_rel:
    st.subheader("A mayor altitud, ¿más diferencia entre el día y la noche?")
    r = ind_f.dropna(subset=["elev_celda_m", "rango_termico_c"])
    fig = px.scatter(r, x="elev_celda_m", y="rango_termico_c", color="departamento",
                     hover_name="provincia",
                     labels={"elev_celda_m": "Altitud de la celda NASA POWER (m s. n. m.)",
                             "rango_termico_c": "Rango térmico diario (°C)", "departamento": ""})
    fig.update_layout(height=500)
    st.plotly_chart(fig, width="stretch")
    if len(r) > 2:
        st.caption(f"Correlación entre altitud y rango térmico ({ambito}): "
                   f"{r.elev_celda_m.corr(r.rango_termico_c):.2f}")

with t_met:
    st.markdown("""
### Contexto
El Perú tiene casi todos los climas del mundo en poco espacio: desierto en la costa, altiplano sobre los
3,800 m y selva amazónica. Saber **dónde el clima varía más** (entre el día y la noche, entre estaciones o
entre años) ayuda a anticipar heladas, sequías e inundaciones como las de El Niño.

### Metodología
1. **Datos:** NASA POWER, API mensual (reanálisis MERRA-2, celdas de unos 50 km), 1991-2025: temperatura
   media, máxima, mínima, rango térmico y precipitación. Un punto representativo dentro de cada una de las
   195 provincias del mapa del INEI.
2. **Limpieza:** se eliminó el "mes 13" que agrega NASA, los -999 pasaron a vacíos, se quitaron duplicados,
   la lluvia pasó de mm/día a mm/mes y solo se usan años completos. Dos provincias venían partidas en el mapa
   ("PUIRA" y "VICTOR FAFARDO") y se unieron por código.
3. **Indicadores** (clima normal 1991-2020):
   - **A. Diaria:** rango térmico medio (máxima menos mínima).
   - **B. Estacional:** diferencia entre el mes más cálido y el más frío; % de la lluvia anual entre diciembre y marzo.
   - **C. Entre años:** coeficiente de variación de la lluvia anual (solo donde llueve más de 100 mm al año).
   - **D. Largo plazo:** tendencia lineal de temperatura (°C por década) y cambio de lluvia entre los
     últimos 15 años y los primeros 15.
4. **Índice de variabilidad (0-100):** promedio de los percentiles del rango térmico, la amplitud estacional,
   el coeficiente de variación de la lluvia y la tendencia de temperatura.
5. **Departamentos:** promedio de sus provincias ponderado por superficie.

### Limitaciones
- Un punto por provincia y celdas de unos 50 km: las provincias pequeñas pueden compartir celda.
- Es un reanálisis, no una medición de estación; puede diferir de SENAMHI, sobre todo en la sierra.
- Los aumentos de lluvia de Castrovirreyna (+158 %) y Chupaca (+99 %) probablemente son artefactos del modelo.
- El calentamiento de Ucayali y el enfriamiento de algunas provincias entre Cusco y Madre de Dios deberían
  validarse con estaciones.
- El índice es una construcción propia: cambia con otros componentes o pesos.
- El mapa no incluye la provincia de Putumayo (creada en 2014).

### Fuentes
- NASA POWER: https://power.larc.nasa.gov
- Límites provinciales (INEI): https://github.com/juaneladio/peru-geojson
""")
    st.download_button("⬇️ Descargar indicadores por provincia (CSV)",
                       ind.to_csv(index=False).encode("utf-8"), "indicadores_provincias.csv", "text/csv")
