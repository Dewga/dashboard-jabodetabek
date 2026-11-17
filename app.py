"""Dashboard harga rumah; jalankan dengan streamlit run app.py."""
from pathlib import Path
from html import escape

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parent
DATA_PATH = ROOT / "data" / "Data_Rumah_Jabodetabek.xlsx"
MENUS = ["Harga Antarwilayah", "Harga & Spesifikasi Rumah"]
COLORS = {"Jakarta": "#ff6b20", "Bogor": "#f5ae42", "Depok": "#79b5df",
          "Tangerang": "#89c77b", "Bekasi": "#b18ad4"}


def number(value):
    return f"{value:,.0f}".replace(",", ".")


def rupiah(value, compact=True):
    if pd.isna(value):
        return "—"
    if not compact:
        return f"Rp{number(value)}"
    unit, suffix = (1e9, "miliar") if abs(value) >= 1e9 else (1e6, "juta")
    if abs(value) < 1e6:
        return f"Rp{number(value)}"
    amount = f"{value / unit:.2f}".rstrip("0").rstrip(".").replace(".", ",")
    return f"Rp{amount} {suffix}"


@st.cache_data(show_spinner=False)
def load_data(path, modified_ns):
    # The modification timestamp invalidates the cache when the Excel source changes.
    data = pd.read_excel(path, sheet_name="Data", engine="openpyxl")
    required = {"Kota", "Nama", "Lokasi", "Harga_Rp", "Luas_Tanah_m2",
                "Luas_Bangunan_m2", "Kamar_Tidur", "Kamar_Mandi"}
    if missing := required.difference(data.columns):
        raise ValueError(f"Kolom wajib tidak tersedia: {', '.join(sorted(missing))}")
    data["Kota"] = data["Kota"].astype("string").str.strip()
    data["Harga_Rp"] = pd.to_numeric(data["Harga_Rp"], errors="coerce")
    for col in ["Luas_Tanah_m2", "Luas_Bangunan_m2", "Kamar_Tidur", "Kamar_Mandi"]:
        data[col] = pd.to_numeric(data[col], errors="coerce")
    return data


def filter_data(data, regions, low, high):
    price = data["Harga_Rp"]
    return data.loc[data["Kota"].isin(regions) & price.gt(0)
                    & np.isfinite(price) & price.between(low, high)].copy()


def summarize(data):
    return (data.groupby("Kota")["Harga_Rp"]
            .agg(n="size", median="median", q1=lambda s: s.quantile(.25),
                 q3=lambda s: s.quantile(.75))
            .reset_index().sort_values(["median", "Kota"], ascending=[False, True]))


def style_chart(fig, height):
    fig.update_layout(height=height, paper_bgcolor="rgba(0,0,0,0)",
                      plot_bgcolor="rgba(0,0,0,0)", font=dict(color="#e8e8e8", size=14),
                      margin=dict(l=12, r=35, t=20, b=45), showlegend=False,
                      hoverlabel=dict(bgcolor="#252729", font_color="#ffffff"))
    fig.update_xaxes(gridcolor="#353638", zerolinecolor="#55565a")
    fig.update_yaxes(gridcolor="#353638", zerolinecolor="#55565a")
    return fig


def emphasis(city):
    selected = st.session_state.get("highlight", "Tanpa sorotan")
    return 1.0 if selected == "Tanpa sorotan" or city == selected else .25


def median_chart(summary):
    fig = go.Figure(go.Bar(
        x=summary["median"], y=summary["Kota"], orientation="h",
        marker_color=[COLORS.get(city, "#ff6b20") for city in summary["Kota"]],
        marker_opacity=[emphasis(city) for city in summary["Kota"]],
        text=[rupiah(v) for v in summary["median"]], textposition="outside", cliponaxis=False,
        customdata=[[number(r.n), rupiah(r.median, False)] for r in summary.itertuples()],
        hovertemplate="<b>%{y}</b><br>Median: %{customdata[1]}<br>%{customdata[0]} listing<extra></extra>"))
    fig.update_yaxes(autorange="reversed", tickvals=summary["Kota"],
                     ticktext=[f"{r.Kota} · {number(r.n)} listing" for r in summary.itertuples()])
    maximum = float(summary["median"].max())
    ticks = [0, maximum]
    fig.update_xaxes(range=[0, maximum * 1.40], tickvals=ticks,
                     ticktext=[rupiah(v) for v in ticks], tickangle=0, title="Median harga penawaran")
    fig = style_chart(fig, max(300, len(summary) * 52 + 65))
    # Reserve physical pixels for outside labels, including on a 390px screen.
    fig.update_layout(margin=dict(l=8, r=108, t=20, b=65))
    fig.update_yaxes(ticktext=[f"{r.Kota}<br>{number(r.n)} listing" for r in summary.itertuples()])
    fig.update_traces(textfont_size=12, constraintext="none")
    return fig


def box_chart(data, summary):
    fig = go.Figure()
    for row in summary.itertuples():
        values = data.loc[data["Kota"].eq(row.Kota), "Harga_Rp"]
        iqr = row.q3 - row.q1
        inside = values.between(row.q1 - 1.5 * iqr, row.q3 + 1.5 * iqr)
        low, high = values[inside].min(), values[inside].max()
        details = (f"<b>{escape(row.Kota)}</b><br>{number(row.n)} listing valid"
                   f"<br>Q1: {rupiah(row.q1, False)}<br>Median: {rupiah(row.median, False)}"
                   f"<br>Q3: {rupiah(row.q3, False)}")
        fig.add_trace(go.Box(x=[row.Kota], q1=[row.q1], median=[row.median], q3=[row.q3],
                            lowerfence=[low], upperfence=[high], boxpoints=False,
                            marker_color=COLORS.get(row.Kota, "#ff6b20"),
                            opacity=emphasis(row.Kota), line_width=2, name=row.Kota, hovertext=[details], hoverinfo="text"))
        extremes = values[~inside]
        fig.add_trace(go.Scatter(x=[row.Kota] * len(extremes), y=extremes,
                                mode="markers", opacity=emphasis(row.Kota), marker=dict(size=5, opacity=.65,
                                color=COLORS.get(row.Kota, "#ff6b20")),
                                customdata=[rupiah(v, False) for v in extremes],
                                hovertemplate=f"{escape(row.Kota)}<br>%{{customdata}}<extra>Listing ekstrem</extra>"))
    min_price, max_price = data["Harga_Rp"].min(), data["Harga_Rp"].max()
    ticks = log_ticks(data["Harga_Rp"], max_ticks=5)
    fig.update_yaxes(type="log", tickvals=ticks, ticktext=[rupiah(v) for v in ticks],
                     title="Harga penawaran (Rp) · skala logaritmik")
    fig.update_xaxes(categoryorder="array", categoryarray=summary["Kota"].tolist(),
                     tickvals=summary["Kota"],
                     ticktext=[f"{r.Kota}<br>n = {number(r.n)}" for r in summary.itertuples()])
    return style_chart(fig, 420)


AREA_COLUMNS = {"Luas Bangunan": "Luas_Bangunan_m2", "Luas Tanah": "Luas_Tanah_m2"}
LISTING_COLUMNS = ["Nama", "Kota", "Lokasi", "Harga_Rp", "Luas_Tanah_m2",
                   "Luas_Bangunan_m2", "Kamar_Tidur", "Kamar_Mandi"]


def positive(series):
    return series.gt(0) & np.isfinite(series)


def area_text(value):
    if pd.isna(value):
        return "—"
    return f"{value:,.1f}".rstrip("0").rstrip(".").replace(",", "_").replace(".", ",").replace("_", ".") + " m²"


def room_counts(data):
    valid = (positive(data.Kamar_Tidur) & positive(data.Kamar_Mandi)
             & data.Kamar_Tidur.mod(1).eq(0) & data.Kamar_Mandi.mod(1).eq(0))
    return data.loc[valid].groupby(["Kamar_Tidur", "Kamar_Mandi"]).size().sort_values(ascending=False)


def room_grid(data):
    grid = pd.DataFrame(0, index=range(1, 7), columns=range(1, 7))
    for (bed, bath), count in room_counts(data).items():
        if 1 <= bed <= 6 and 1 <= bath <= 6:
            grid.loc[int(bath), int(bed)] = int(count)
    return grid


def log_ticks(values, max_ticks=5):
    low, high = float(values.min()), float(values.max())
    ticks = [m * 10.0**e for e in range(int(np.floor(np.log10(low))),
            int(np.ceil(np.log10(high))) + 1) for m in (1, 2, 5)
            if low <= m * 10.0**e <= high]
    if not ticks:
        return [low]
    if len(ticks) > max_ticks:
        ticks = [ticks[i] for i in np.linspace(0, len(ticks) - 1, max_ticks).round().astype(int)]
    return ticks


def scatter_chart(data, area_column, label):
    fig = go.Figure()
    cities = sorted(data.Kota.dropna().unique())
    selected = st.session_state.get("highlight", "Tanpa sorotan")
    for city in sorted(cities, key=lambda c: c == selected):
        group = data.loc[data.Kota.eq(city)]
        custom = [[escape(str(r.Nama)), escape(str(r.Lokasi)), rupiah(r.Harga_Rp, False),
                   area_text(r.Luas_Tanah_m2), area_text(r.Luas_Bangunan_m2),
                   "—" if pd.isna(r.Kamar_Tidur) else number(r.Kamar_Tidur),
                   "—" if pd.isna(r.Kamar_Mandi) else number(r.Kamar_Mandi)]
                  for r in group.itertuples()]
        fig.add_trace(go.Scatter(x=group[area_column].tolist(), y=group.Harga_Rp.tolist(),
            mode="markers", name=city, legendrank=cities.index(city), customdata=custom,
            marker=dict(color=COLORS.get(city, "#ff6b20"), size=5, line=dict(width=0),
                        opacity=(.8 if city == selected else .12) if selected != "Tanpa sorotan" else (.55 if len(cities) == 1 else .3)),
            hovertemplate=(f"<b>{escape(city)}</b> · %{{customdata[0]}}<br>%{{customdata[1]}}"
                           "<br>Harga: %{customdata[2]}<br>Tanah: %{customdata[3]}"
                           "<br>Bangunan: %{customdata[4]}<br>%{customdata[5]} KT · %{customdata[6]} KM<extra></extra>")))
    fig = style_chart(fig, 350)
    xticks, yticks = log_ticks(data[area_column]), log_ticks(data.Harga_Rp)
    fig.update_xaxes(type="log", title=f"{label} (m²) · skala logaritmik",
                     tickvals=xticks, ticktext=[area_text(v) for v in xticks])
    fig.update_yaxes(type="log", title="Harga penawaran (Rp) · skala logaritmik",
                     tickvals=yticks, ticktext=[rupiah(v) for v in yticks])
    fig.update_layout(showlegend=True, legend=dict(orientation="h", y=1.02, yanchor="bottom", x=0))
    return fig


def heatmap_chart(grid, total):
    z = grid.values.tolist()
    percent = [[f"{100 * v / total:.1f}%".replace(".", ",") for v in row] for row in z]
    fig = go.Figure(go.Heatmap(x=list(grid.columns), y=list(grid.index), z=z,
        text=[[number(v) for v in row] for row in z], texttemplate="%{text}",
        customdata=percent, colorscale=[[0, "#30231d"], [.4, "#a54516"], [1, "#ff801f"]],
        zmin=0, xgap=3, ygap=3, showscale=False,
        hovertemplate="%{x} KT · %{y} KM<br>%{text} listing<br>%{customdata} dari hasil filter<extra></extra>"))
    fig = style_chart(fig, 350)
    fig.update_xaxes(title="Kamar tidur", dtick=1)
    fig.update_yaxes(title="Kamar mandi", dtick=1)
    return fig


def area_comparison(data):
    cities = sorted(data.Kota.dropna().unique())
    fig = go.Figure()
    results = {}
    for label, col, color in [("Luas tanah", "Luas_Tanah_m2", "#ffc49c"),
                               ("Luas bangunan", "Luas_Bangunan_m2", "#ff6b20")]:
        medians, custom = [], []
        for city in cities:
            values = data.loc[data.Kota.eq(city) & positive(data[col]), col]
            median = float(values.median()) if len(values) else None
            medians.append(median)
            custom.append([area_text(median), number(len(values))])
        results[label] = medians
        fig.add_trace(go.Scatter(x=medians, y=cities, name=label, mode="markers",
            marker=dict(color=[COLORS[c] if st.session_state.get("highlight") == c else color for c in cities],
                        opacity=[emphasis(c) for c in cities], symbol="circle" if label == "Luas tanah" else "diamond", size=11), customdata=custom,
            hovertemplate="%{y}<br>" + label + ": %{customdata[0]}<br>%{customdata[1]} observasi positif<extra></extra>"))
    for i, city in enumerate(cities):
        a, b = results["Luas tanah"][i], results["Luas bangunan"][i]
        if a is not None and b is not None:
            fig.add_shape(type="line", x0=a, x1=b, y0=city, y1=city,
                          opacity=emphasis(city), line=dict(color="#777777", width=2), layer="below")
    fig = style_chart(fig, 350)
    fig.update_yaxes(autorange="reversed")
    fig.update_xaxes(title="Median luas (m²)", rangemode="tozero")
    fig.update_layout(showlegend=True, legend=dict(orientation="h", y=1.17, x=0))
    return fig


def listing_results(data, search):
    query = search.strip()
    if query:
        mask = (data.Nama.astype("string").str.contains(query, case=False, regex=False, na=False)
                | data.Lokasi.astype("string").str.contains(query, case=False, regex=False, na=False))
        data = data.loc[mask]
    return data[LISTING_COLUMNS].copy()


def similar_area_summary(data, cities, low, high):
    subset = data.loc[positive(data.Luas_Bangunan_m2)
                      & data.Luas_Bangunan_m2.between(low, high)]
    result = subset.groupby("Kota").Harga_Rp.agg(n="size", median="median").reindex(cities)
    result["n"] = result["n"].fillna(0).astype(int)
    return result


def render_similar_area(data, cities):
    with st.container(border=True, key="similar_panel"):
        st.subheader("Bandingkan rumah dengan luas serupa")
        left, right = st.columns(2)
        low = left.number_input("Luas bangunan minimum (m²)", min_value=0, value=50, key="similar_min")
        high = right.number_input("Luas bangunan maksimum (m²)", min_value=0, value=75, key="similar_max")
        if low > high:
            st.warning("Luas minimum melebihi maksimum. Perbaiki rentang luas panel ini.")
        results = similar_area_summary(data, cities, low, high)
        rows = [{"Wilayah": city, "Median harga penawaran": rupiah(r["median"]) if r.n else "Tidak ada listing",
                 "n": int(r.n)} for city, r in results.iterrows()]
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
        st.caption("Hanya panel ini memakai rentang luas bangunan positif dengan batas inklusif. "
                   "Rumah dengan luas serupa masih bisa berbeda lokasi, kondisi, dan spesifikasi.")


def render_correlation(valid, col, label):
    n = len(valid)
    if n >= 10 and valid[col].nunique() > 1 and valid.Harga_Rp.nunique() > 1:
        corr = np.log10(valid[col]).corr(np.log10(valid.Harga_Rp))
        value = f"{corr:.3f}".replace(".", ",")
        st.write(f"Pearson log-log {label}: **{value}** · n = {number(n)}")
    else:
        st.caption(f"Pearson log-log {label}: belum tersedia · n = {number(n)}. Minimal 10 pasangan dan variasi kedua variabel diperlukan.")


def source_caption():
    st.caption("Listing rumah sekunder · harga penawaran. Sumber: Data_Rumah_Jabodetabek.xlsx, sheet Data. "
               "Periode pengumpulan tidak tercantum pada workbook.")


def render_specs(filtered, chosen, minimum, maximum, reset):
    st.title("Harga & Spesifikasi Rumah")
    st.write("Hubungan harga penawaran, luas, dan kombinasi kamar")
    scope = "Semua wilayah" if len(chosen) == 5 else (", ".join(chosen) if chosen else "Tidak ada wilayah dipilih")
    total = len(filtered)
    st.caption(f"{scope} · {rupiah(minimum)} – {rupiah(maximum)} · {number(total)} listing sesuai filter")
    source_caption()
    cards = st.columns(3)
    for i, (label, col) in enumerate([("Median luas tanah", "Luas_Tanah_m2"),
                                     ("Median luas bangunan", "Luas_Bangunan_m2")]):
        values = filtered.loc[positive(filtered[col]), col]
        with cards[i], st.container(border=True, key=f"spec_kpi_{i}"):
            st.metric(label, area_text(values.median()))
            st.caption(f"{number(len(values))} observasi positif")
    counts = room_counts(filtered)
    leaders = counts.loc[counts.eq(counts.max())] if not counts.empty else counts
    if len(leaders) == 1:
        bed, bath = leaders.index[0]
        mode = f"{int(bed)} KT · {int(bath)} KM"
    else:
        mode = f"Seri · {number(len(leaders))} kombinasi" if len(leaders) else "—"
    with cards[2], st.container(border=True, key="spec_kpi_2"):
        st.metric("Kombinasi kamar teratas", mode)
        st.caption(f"{number(leaders.iloc[0])} listing per kombinasi" if len(leaders) else "Tidak ada pasangan kamar bulat positif")
    if minimum > maximum:
        st.warning("Harga minimum lebih besar dari harga maksimum. Perbaiki rentang atau gunakan Reset filter.")
    if not total:
        st.info("Tidak ada listing yang cocok dengan filter ini")
        st.button("Reset filter", key="reset_specs_empty", on_click=reset)
        return
    with st.container(border=True, key="scatter_panel"):
        title, control = st.columns([1.5, 1], vertical_alignment="center")
        with title:
            st.subheader("Hubungan luas dan harga")
        with control:
            area = st.radio("Pilihan luas", list(AREA_COLUMNS), horizontal=True, key="scatter_area", label_visibility="collapsed")
        col = AREA_COLUMNS[area]
        valid = filtered.loc[positive(filtered.Harga_Rp) & positive(filtered[col])]
        st.caption(f"{number(len(valid))} titik valid dari {number(total)} listing · "
                   "kedua sumbu logaritmik · satu titik mewakili satu listing")
        if valid.empty:
            st.info(f"Tidak ada pasangan harga dan {area.lower()} positif untuk scatter ini.")
        else:
            st.plotly_chart(scatter_chart(valid, col, area), width="stretch", key="spec_scatter", config={"displayModeBar": False})
        render_correlation(valid, col, f"seluruh listing terpilih ({area.lower()})")
        selected = st.session_state.get("highlight", "Tanpa sorotan")
        if selected != "Tanpa sorotan":
            render_correlation(valid.loc[valid.Kota.eq(selected)], col, f"{selected} ({area.lower()})")
        st.caption("Hubungan ini tidak membuktikan sebab-akibat; lokasi dan spesifikasi lain juga memengaruhi harga.")
    with st.expander("Tentang perhitungan luas dan scatter"):
        for label, col in [("Luas tanah", "Luas_Tanah_m2"), ("Luas bangunan", "Luas_Bangunan_m2")]:
            n = int(positive(filtered[col]).sum())
            st.write(f"{label}: {number(n)} observasi positif; {number(total - n)} dikeluarkan dari median ukuran ini.")
        st.write("Scatter memakai harga dan luas yang keduanya positif serta terhingga. "
                 "Nilai ekstrem dipertahankan tanpa pemangkasan. Pearson menggunakan log₁₀ luas bangunan dan log₁₀ harga; "
                 "ambang 10 pasangan adalah aturan tampilan aplikasi.")
    heat, comparison = st.columns(2)
    grid = room_grid(filtered)
    coverage = int(grid.values.sum())
    with heat, st.container(border=True, key="heatmap_panel"):
        st.subheader("Kombinasi kamar")
        st.caption(f"Grid 1–6: {number(coverage)} dari {number(total)} listing · seluruh hasil filter, tanpa pengaruh sorotan")
        st.plotly_chart(heatmap_chart(grid, total), width="stretch", key="spec_heatmap")
        st.caption(f"Grid 1–6 mencakup {number(coverage)} dari {number(total)} listing; "
                   f"{number(int(counts.sum()) - coverage)} pasangan kamar valid di luar grid; "
                   f"{number(total - int(counts.sum()))} pasangan kamar tidak valid.")
        if len(leaders) > 1:
            st.write("Teratas seri: " + "; ".join(f"{int(b)} KT · {int(m)} KM" for b, m in leaders.index))
        elif len(leaders):
            st.caption(f"{mode}: {number(leaders.iloc[0])} listing ({100 * leaders.iloc[0] / total:.1f}% dari hasil filter)".replace(".0%", ",0%"))
    with comparison, st.container(border=True, key="area_panel"):
        st.subheader("Median luas per wilayah")
        st.plotly_chart(area_comparison(filtered), width="stretch", key="spec_area_comparison")
        st.caption("Median tiap ukuran memakai observasi positifnya sendiri; jumlahnya tersedia pada tooltip. Ukuran tanpa nilai positif tidak memiliki titik.")
    with st.expander("Tentang perhitungan kombinasi kamar"):
        st.write("Kombinasi teratas dihitung dari pasangan bilangan bulat positif, termasuk yang di luar grid. "
                 "Heatmap hanya mencakup 1–6 kamar tidur × 1–6 kamar mandi. "
                 "Persentase setiap sel menggunakan seluruh hasil filter sebagai penyebut; pasangan tidak valid tidak dianggap nol kamar.")
    with st.expander("Lihat Tabel Listing"):
        search = st.text_input("Cari nama atau lokasi", key="listing_search", placeholder="Ketik nama listing atau lokasi…")
        table = listing_results(filtered, search)
        st.caption(f"{number(len(table))} listing ditampilkan dari {number(total)} hasil filter. Pencarian hanya memengaruhi tabel dan CSV.")
        st.dataframe(table, hide_index=True, width="stretch", column_config={
            "Nama": "Nama listing", "Kota": "Wilayah", "Harga_Rp": st.column_config.NumberColumn("Harga (Rp)", format="localized"),
            "Luas_Tanah_m2": "Luas tanah (m²)", "Luas_Bangunan_m2": "Luas bangunan (m²)",
            "Kamar_Tidur": "Kamar tidur", "Kamar_Mandi": "Kamar mandi"})
        if table.empty:
            st.info("Tidak ada nama atau lokasi yang cocok dengan pencarian tabel.")
        st.download_button("Unduh CSV", data=table.to_csv(index=False).encode("utf-8-sig"),
                           file_name="listing_jabodetabek.csv", mime="text/csv", key="listing_csv")
    st.caption("Harga penawaran listing, bukan harga transaksi. Cakupan sampel berbeda antarwilayah.")


CSS = """
<style>
.stApp {background: #101112; color: #f5f5f5;}
[data-testid="stSidebar"] {background: #080909; border-right: 1px solid #292a2b;}
[data-testid="stSidebarContent"] {padding: 0; overflow-x: hidden;}
.block-container {padding-top: 2.2rem; padding-bottom: 3rem; max-width: 1550px;}
h1 {font-size: 2.25rem !important; letter-spacing: -.035em; padding-top: .2rem !important;}
h3 {font-size: 1.2rem !important; letter-spacing: -.015em;}
.st-key-kpi_0, .st-key-kpi_1, .st-key-kpi_2, .st-key-median_panel,
.st-key-finding_panel, .st-key-box_panel, .st-key-similar_panel, .st-key-spec_kpi_0, .st-key-spec_kpi_1,
.st-key-spec_kpi_2, .st-key-scatter_panel, .st-key-heatmap_panel, .st-key-area_panel {
background: linear-gradient(130deg, #252729, #191b1d); border-radius: 18px;
}
.st-key-kpi_0 {background: linear-gradient(125deg, #c44812, #f87832);}
.st-key-spec_kpi_2 {background: linear-gradient(125deg, #86330f, #ce4e15);}
.st-key-spec_kpi_2 [data-testid="stMetricValue"] {white-space: normal; font-size: 1.7rem;}
.st-key-kpi_0 [data-testid="stCaptionContainer"] {color: #fff3eb;}
[data-testid="stMetricValue"] {font-size: clamp(1.3rem, 2.3vw, 2.15rem); font-weight: 750;}
[data-testid="stMetricLabel"] {color: #e8e8e8; font-size: 1rem;}
.st-key-kpi_2 [data-testid="stMetricValue"] {
font-size: clamp(1.2rem, 1.7vw, 1.65rem); white-space: normal; overflow-wrap: anywhere;
}
.brand {display: flex; align-items: center; gap: 10px; margin-bottom: 8px;}
.brand-icon {
position: relative; display: block; width: 40px; height: 40px; flex: 0 0 40px;
border-radius: 11px; background: #ff681f; color: white;
}
.brand-icon::before, .brand-icon::after {content: ""; position: absolute; box-sizing: border-box;}
.brand-icon::before {
width: 16px; height: 12px; left: 12px; top: 17px;
border: 2px solid currentColor; border-top: 0; border-radius: 0 0 2px 2px;
}
.brand-icon::after {
width: 13px; height: 13px; left: 13.5px; top: 12px;
border-top: 2px solid currentColor; border-left: 2px solid currentColor;
border-top-left-radius: 2px; transform: rotate(45deg);
}
.brand-title {font-size: 15px; font-weight: 750; line-height: 1.25; text-wrap: balance;}
.brand .muted {color: #b5b5b7; font-size: 12px; line-height: 1.4; margin-top: 2px;}
.eyebrow {color: #b5b5b7; font-size: 14px; margin-bottom: 4px;}
.finding {font-size: 2rem; font-weight: 750; color: #ff783d; margin: 16px 0 8px;}
[data-testid="stSidebar"] [role="radiogroup"] {gap: 6px; align-items: stretch;}
[data-testid="stSidebar"] [role="radiogroup"] label {
box-sizing: border-box; width: 100%; min-height: 44px; display: flex; align-items: center;
padding: 8px 9px; border-radius: 9px; background: #151617; border-left: 3px solid transparent;
}
[data-testid="stSidebar"] [role="radiogroup"] label p {font-size: 13px; line-height: 1.25;}
[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) {
background: #462819; border-left-color: #ff6b20;
}
[data-testid="stSidebar"] [data-testid="stButton"] button {border-radius: 9px; min-height: 40px;}
@media(max-width: 700px) {.block-container {padding: 1.4rem 1rem;} h1 {font-size: 1.8rem !important;}}

[data-testid="stMainBlockContainer"] {padding: 1.2rem 1.6rem 2rem;}
[data-testid="stVerticalBlock"] {gap: .65rem;}
[data-testid="stHeader"] {height: 1rem; background: transparent;}
[data-testid="stSidebar"] {width: 255px !important; min-width: 255px !important;}
[data-testid="stSidebarUserContent"] {padding: 8px 12px 16px;}
[data-testid="stSidebar"] [data-testid="stMultiSelectTagsContainer"] {
flex-wrap: wrap !important; overflow: visible !important; height: auto !important;
max-height: none !important;
}
[data-testid="stSidebar"] [data-testid="stMultiSelectTagsContainer"] [data-tag] {
flex-shrink: 0; max-width: 100%;
}
[data-testid="stSidebar"] [data-testid="stMultiSelect"] [data-baseweb="select"] > div {
height: auto !important; max-height: none !important; overflow: visible !important;
}
[data-testid="stSidebar"] [data-testid="stMultiSelect"] [role="group"][aria-label="Selected values"] {
display: flex; flex-wrap: wrap; height: auto; max-height: none; overflow: visible;
}
[data-testid="stSidebar"] [data-testid="stMultiSelect"] [data-baseweb="tag"] {
max-width: 100%; flex-shrink: 0;
}
[data-testid="stSidebar"] hr {margin: .4rem 0;}
[data-testid="stSidebar"] h3 {padding: .2rem 0;}
h1 {font-size: 2rem !important; padding-bottom: .2rem !important;}
.st-key-kpi_0, .st-key-kpi_1, .st-key-kpi_2,
.st-key-spec_kpi_0, .st-key-spec_kpi_1, .st-key-spec_kpi_2 {min-height: 122px; padding: 12px !important;}
[data-testid="stMetricLabel"] {min-height: 24px;}
[data-testid="stMetricValue"] {white-space: normal;}
.st-key-finding_panel {min-height: 390px;}
@media(max-width: 850px) {
[data-testid="stMainBlockContainer"] {padding-top: 3.5rem;}
[data-testid="stHorizontalBlock"] {flex-wrap: wrap;}
[data-testid="stColumn"] {min-width: 100% !important; width: 100% !important; flex: 1 1 100% !important;}
.st-key-finding_panel {min-height: auto;}
}
</style>
"""


def main():
    st.set_page_config(page_title="Potret Harga Rumah Jabodetabek", page_icon="⌂", layout="wide")
    st.markdown(CSS, unsafe_allow_html=True)
    try:
        data = load_data(str(DATA_PATH), DATA_PATH.stat().st_mtime_ns)
    except (OSError, ValueError, ImportError) as exc:
        st.error(f"Data Excel belum bisa dibaca: {exc}")
        st.stop()
    prices = data.loc[data["Harga_Rp"].gt(0) & np.isfinite(data["Harga_Rp"]), "Harga_Rp"]
    if prices.empty:
        st.error("Workbook tidak memiliki harga positif yang valid.")
        st.stop()
    regions = sorted(data["Kota"].dropna().unique().tolist())
    lower, upper = int(prices.min()), int(prices.max())

    def reset():
        st.session_state.regions = regions
        st.session_state.price_min = lower
        st.session_state.price_max = upper
        st.session_state.highlight = "Tanpa sorotan"

    for key, default in [("regions", regions), ("price_min", lower), ("price_max", upper)]:
        if key not in st.session_state:
            st.session_state[key] = default
    with st.sidebar:
        st.markdown('<div class="brand"><span class="brand-icon" aria-hidden="true"></span><div>'
                    '<div class="brand-title">Potret Harga Rumah</div>'
                    '<div class="muted">Jabodetabek</div></div></div>', unsafe_allow_html=True)
        menu = st.radio("Navigasi", MENUS, key="menu", label_visibility="collapsed", width="stretch")
        st.divider()
        st.subheader("Wilayah")
        summary_label = "Semua wilayah" if len(st.session_state.regions) == len(regions) else "Pilih wilayah"
        with st.expander(summary_label):
            chosen = st.multiselect("Pilih wilayah", regions, key="regions", label_visibility="collapsed")
        highlight_slot = st.container()
        st.subheader("Rentang harga")
        minimum = st.number_input("Harga minimum (Rp)", min_value=0, step=10_000_000, key="price_min")
        maximum = st.number_input("Harga maksimum (Rp)", min_value=0, step=10_000_000, key="price_max")
        st.caption(f"{rupiah(minimum)} – {rupiah(maximum)}")
        st.button("Reset filter", on_click=reset, width="stretch")

    filtered = filter_data(data, chosen, minimum, maximum)
    options = ["Tanpa sorotan"] + sorted(filtered.Kota.dropna().unique().tolist())
    if st.session_state.get("highlight") not in options:
        st.session_state.highlight = "Tanpa sorotan"
    with highlight_slot:
        st.selectbox("Sorot kota", options, key="highlight", help="Hanya penekanan visual; tidak mengubah cakupan data.")
        st.caption("Sorotan hanya mengubah penekanan visual.")
    # Keep filter widgets mounted for both menus so their state survives navigation.
    st.markdown('<div class="eyebrow">PSD Kelompok 3</div>', unsafe_allow_html=True)
    if menu == MENUS[1]:
        render_specs(filtered, chosen, minimum, maximum, reset)
        return
    st.title("Harga Antarwilayah")
    st.markdown("Harga penawaran rumah sekunder di Jabodetabek")
    scope = "Semua wilayah" if len(chosen) == 5 else (", ".join(chosen) if chosen else "Tidak ada wilayah dipilih")
    st.caption(f"{scope} · {rupiah(minimum)} – {rupiah(maximum)} · {number(len(filtered))} listing")
    source_caption()
    q1, median, q3 = (filtered["Harga_Rp"].quantile([.25, .5, .75]).tolist()
                      if not filtered.empty else [float("nan")] * 3)
    cards = st.columns([1, 1.2, 1.5])
    for index, (column, label, value, note) in enumerate(zip(cards,
            ["Listing sesuai filter", "Median seluruh listing terpilih", "Rentang 50% harga tengah"],
            [number(len(filtered)), rupiah(median), f"{rupiah(q1)} – {rupiah(q3)}" if len(filtered) else "—"],
            ["Satu baris = satu listing", "Dari harga positif sesuai filter", "Q1 hingga Q3 · 50% data di tengah"])):
        with column, st.container(border=True, key=f"kpi_{index}"):
            st.metric(label, value)
            st.caption(note)
    if minimum > maximum:
        st.warning("Harga minimum lebih besar dari harga maksimum. Perbaiki rentang atau gunakan Reset filter.")
    if filtered.empty:
        st.info("Tidak ada listing yang cocok dengan filter ini")
        st.button("Reset filter", key="reset_empty", on_click=reset)
        return

    summary = summarize(filtered)
    chart, finding = st.columns([2.5, 1])
    with chart, st.container(border=True, key="median_panel"):
        st.subheader("Median harga penawaran per wilayah")
        st.plotly_chart(median_chart(summary), width="stretch", config={"displayModeBar": False})
    with finding, st.container(border=True, key="finding_panel"):
        st.subheader("Temuan utama")
        selected = st.session_state.get("highlight", "Tanpa sorotan")
        highest = summary.iloc[0]
        leaders = summary.loc[summary["median"].eq(highest["median"]), "Kota"].tolist()
        st.markdown(f'<div class="finding">{escape(selected if selected != "Tanpa sorotan" else ", ".join(leaders))}</div>', unsafe_allow_html=True)
        if selected != "Tanpa sorotan":
            row = summary.loc[summary.Kota.eq(selected)].iloc[0]
            st.write(f"Median **{rupiah(row['median'])}** · **{number(row['n'])} listing**")
            st.caption(f"Median seluruh listing terpilih: {rupiah(median)}")
        elif len(summary) == 1:
            st.write(f"Median penawaran **{rupiah(median)}** dari **{number(len(filtered))} listing**.")
            st.write(f"Rentang tengah: {rupiah(q1)} hingga {rupiah(q3)}.")
        else:
            st.write(f"Median penawaran tertinggi{' (seri)' if len(leaders) > 1 else ''}: **{rupiah(highest['median'])}**.")
            st.write(" · ".join(f"{r.Kota}: {number(r.n)} listing" for r in summary.itertuples() if r.Kota in leaders))
            lowest = summary.iloc[-1]
            st.caption(f"Median terendah: {lowest['Kota']} · {rupiah(lowest['median'])} · {number(lowest['n'])} listing.")
    render_similar_area(filtered, chosen)
    with st.expander("Tentang perhitungan median"):
        st.write("Filter harga bersifat inklusif. Median dan kuartil memakai harga positif dan terhingga. "
                 "Jumlah listing dihitung per baris tanpa menghapus duplikat. Kuartil memakai interpolasi linear. "
                 "Luas bangunan nol tetap masuk dalam analisis harga ini.")
        st.caption(f"Sumber: sheet Data · {number(len(data))} baris keseluruhan · "
                   f"{number(len(data) - len(prices))} baris dengan harga tidak valid.")
    with st.container(border=True, key="box_panel"):
        st.subheader("Bagaimana harga tersebar di tiap wilayah?")
        st.caption("Skala logaritmik · label menunjukkan rupiah asli · titik menunjukkan listing ekstrem")
        st.plotly_chart(box_chart(filtered, summary), width="stretch", config={"displayModeBar": False})
    with st.expander("Tentang perhitungan sebaran harga"):
        st.write("Kotak membentang dari Q1 ke Q3 dan garis tengah menunjukkan median. "
                 "Whisker mencapai nilai terjauh yang masih dalam 1,5 × IQR dari kotak (IQR = Q3 − Q1). "
                 "Titik di luarnya tetap disertakan dalam seluruh perhitungan. "
                 "Kuartil dihitung dari harga rupiah sebelum memakai sumbu logaritmik.")
        table = summary.rename(columns={"Kota": "Wilayah", "n": "Listing valid", "median": "Median", "q1": "Q1", "q3": "Q3"}).copy()
        for col in ["Median", "Q1", "Q3"]:
            table[col] = table[col].map(lambda v: rupiah(v, False))
        st.dataframe(table, hide_index=True, width="stretch")
    st.caption("Harga penawaran listing, bukan harga transaksi. Cakupan sampel berbeda antarwilayah.")


if __name__ == "__main__":
    main()
