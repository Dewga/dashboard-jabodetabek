"""Dashboard harga rumah; jalankan dengan streamlit run app.py."""
from pathlib import Path
from zipfile import BadZipFile

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from dashboard_components import budget_slider, kpi_counter, region_bars, region_ranking

ROOT = Path(__file__).resolve().parent
DATA_PATH = ROOT / "data" / "Data_Rumah_Jabodetabek.xlsx"
MENUS = ["Pilihan menurut anggaran", "Spesifikasi rumah"]
DEFAULT_BUDGET = 1_000_000_000
PRESETS = [500_000_000, 750_000_000, DEFAULT_BUDGET, 1_500_000_000]
NAVIGATION = [("Anggaran", ":material/monitoring:"), ("Spesifikasi", ":material/house:")]


def number(value):
    return f"{value:,.0f}".replace(",", ".")


def rupiah(value, compact=True):
    if pd.isna(value):
        return "Tidak tersedia"
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


def style_chart(fig, height):
    fig.update_layout(height=height, paper_bgcolor="rgba(0,0,0,0)",
                      plot_bgcolor="rgba(0,0,0,0)", font=dict(color="#26372d", size=13),
                      margin=dict(l=12, r=18, t=24, b=48), showlegend=False,
                      hoverlabel=dict(bgcolor="#234235", bordercolor="#547360", font_color="#ffffff"))
    axis = dict(automargin=True, gridcolor="#dce4d9", zeroline=False,
                tickfont=dict(color="#46594d"), title_font=dict(color="#374a3e"))
    fig.update_xaxes(**axis)
    fig.update_yaxes(**axis)
    return fig


LISTING_COLUMNS = ["Nama", "Kota", "Lokasi", "Harga_Rp", "Luas_Tanah_m2",
                   "Luas_Bangunan_m2", "Kamar_Tidur", "Kamar_Mandi"]


def positive(series):
    return series.gt(0) & np.isfinite(series)


def area_text(value):
    if pd.isna(value):
        return "Tidak tersedia"
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


def heatmap_chart(grid, total):
    z = grid.values.tolist()
    percent = [[f"{100 * v / total:.1f}%".replace(".", ",") for v in row] for row in z]
    fig = go.Figure(go.Heatmap(x=list(grid.columns), y=list(grid.index), z=z,
        text=[[number(v) for v in row] for row in z], texttemplate="%{text}",
        textfont=dict(color="#172a20", size=12),
        customdata=percent, colorscale=[[0, "#eef2ea"], [.5, "#bed1bd"], [1, "#8caf95"]],
        zmin=0, xgap=3, ygap=3, showscale=False,
        hovertemplate="%{x} KT · %{y} KM<br>%{text} listing<br>%{customdata} dari hasil filter<extra></extra>"))
    fig = style_chart(fig, 300)
    fig.update_layout(margin=dict(l=10, r=10, t=10, b=42))
    fig.update_xaxes(title="Kamar tidur", dtick=1, showgrid=False)
    fig.update_yaxes(title="Kamar mandi", dtick=1, showgrid=False)
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
        left, right = st.columns(2)
        low = left.number_input("Luas bangunan minimum (m²)", min_value=0, value=50, key="similar_min")
        high = right.number_input("Luas bangunan maksimum (m²)", min_value=0, value=75, key="similar_max")
        if low > high:
            st.warning("Luas minimum melebihi maksimum. Perbaiki rentang luas panel ini.")
        results = similar_area_summary(data, cities, low, high)
        comparison = results.reset_index().rename(columns={"Kota": "Wilayah"})
        st.dataframe(
            comparison.style.set_properties(subset=["median"], **PRICE_CELL_STYLE),
            hide_index=True, width="stretch", column_config={
                "Wilayah": st.column_config.TextColumn("Wilayah", width="medium"),
                "median": st.column_config.NumberColumn("Median penawaran (Rp)", format="localized", width="medium"),
                "n": st.column_config.NumberColumn("Jumlah listing", format="localized"),
            },
        )
        st.caption("Hanya panel ini memakai rentang luas bangunan positif dengan batas inklusif. "
                   "Rumah dengan luas serupa masih bisa berbeda lokasi, kondisi, dan spesifikasi.")



def budget_breakdown(market, affordable):
    totals = market.groupby("Kota").size().rename("total")
    matches = affordable.groupby("Kota").size().reindex(totals.index, fill_value=0)
    result = totals.to_frame().assign(matches=matches)
    result["share"] = result.matches / result.total
    return result.reset_index().sort_values(
        ["share", "matches", "Kota"], ascending=[False, False, True]
    )


def percent(value):
    return f"{value:.1%}".replace(".0%", "%").replace(".", ",")


def budget_chart_data(prices, budget, comparison=None):
    ceiling = max(PRESETS[-1], int(np.ceil(prices.quantile(.90) / 100_000_000)) * 100_000_000)
    upper = max(ceiling, budget, comparison or 0)
    price_counts = prices.loc[prices.le(upper)].value_counts().sort_index().cumsum()
    start, end = sorted((budget, comparison if comparison is not None else budget))
    extra = int((prices.gt(start) & prices.le(end)).sum())
    return {"budget": budget, "comparison": comparison, "upper": upper, "total": len(prices),
            "extra": extra,
            "points": [[float(price), int(total)] for price, total in price_counts.items()]}


def commit_chart_budget():
    budget = st.session_state.budget_curve.committed
    if isinstance(budget, int) and 0 <= budget <= 1_000_000_000_000_000:
        st.session_state.chart_previous_budget = st.session_state.budget
        st.session_state.budget = budget


def commit_chart_comparison():
    comparison = st.session_state.budget_curve.compared
    if (st.session_state.get("comparison_enabled") and isinstance(comparison, int)
            and 0 <= comparison <= 1_000_000_000_000_000):
        st.session_state.comparison_budget = comparison
        save_comparison_budget()


def save_comparison_budget():
    st.session_state.saved_comparison_budget = st.session_state.comparison_budget


def save_comparison_toggle():
    st.session_state.comparison_enabled = st.session_state.show_comparison


def building_summary(sizes):
    return (sizes.groupby("Kota").Luas_Bangunan_m2
            .agg(median="median", size="size", q1=lambda group: group.quantile(.25),
                 q3=lambda group: group.quantile(.75))
            .sort_values("median", ascending=False, kind="stable"))


def region_chart_data(sizes, selected, animate=False):
    stats = building_summary(sizes)
    comparison = sizes.Luas_Bangunan_m2.median()
    step = max(1, int(np.ceil(stats.q3.max() / 4)))
    rows = []
    for city, median, count, q1, q3 in stats.itertuples():
        delta = median - comparison
        difference = (f"{'+' if delta > 0 else '−'}{area_text(abs(delta))} dari nilai tengah seluruh pilihan"
                      if delta else "sama dengan nilai tengah seluruh pilihan")
        value = area_text(median)
        samples = f"{number(count)} listing dengan luas valid"
        middle = f"Rentang tengah {area_text(q1)}–{area_text(q3)}"
        rows.append(dict(city=city, value=value, median=float(median), count=number(count),
                         position=median / (4 * step) * 100, left=q1 / (4 * step) * 100,
                         right=q3 / (4 * step) * 100,
                         tooltip=f"{city} · Median {value} · {samples} · {middle}",
                         summary=f"{city} · {value} · {difference} · {samples}"))
    return {"selected": selected, "rows": rows, "animate": animate,
            "ticks": [area_text(i * step) for i in range(5)]}


PRICE_CELL_STYLE = {"background-color": "#eaf1e9", "color": "#294735", "font-weight": "600"}


def select_region():
    st.session_state.region_focus = st.session_state.region_bars.selected["city"]


def metrics(items, animate, previous=None):
    page = st.session_state.page_index
    for index, (column, (label, value, format_value)) in enumerate(zip(st.columns(len(items), gap="small"), items)):
        with column, st.container(border=True, key=f"kpi-{index}"):
            if format_value is None:
                st.metric(label, value)
                continue
            start = 0 if animate else previous[index] if previous is not None else value
            frames = ([format_value(start + (value - start) * step / 36) for step in range(37)]
                      if pd.notna(start) and pd.notna(value) and start != value else [])
            kpi_counter(key=f"kpi-counter-{page}-{index}", width="stretch",
                        data={"label": label, "value": format_value(value), "frames": frames,
                              "primary": index == 0})


def budget_metrics(market, affordable):
    return [
        (f"Dalam anggaran · dari {number(len(market))} listing", len(affordable), number),
        ("Persentase dalam anggaran", len(affordable) / len(market), percent),
        ("Harga tengah dalam anggaran", affordable.Harga_Rp.median(), rupiah),
    ]


def render_budget(market, affordable, budget, animate, previous_budget):
    previous = None if previous_budget is None else market.loc[market.Harga_Rp.le(previous_budget)]
    previous_values = None if previous is None else [value for _, value, _ in budget_metrics(market, previous)]
    metrics(budget_metrics(market, affordable), animate, previous_values)
    main, side = st.columns([1.85, 1], gap="small")
    with main, st.container(border=True, key="budget-chart"):
        title, compare = st.columns([1.25, 1], gap="small", vertical_alignment="center")
        title.subheader("Pilihan saat anggaran naik")
        comparison = None
        with compare, st.container(horizontal=True, vertical_alignment="center", gap="small"):
            enabled = st.toggle("Tampilkan pembanding", value=st.session_state.get("comparison_enabled", False),
                                key="show_comparison", on_change=save_comparison_toggle)
            if enabled:
                with st.popover("Atur nominal"):
                    comparison = st.number_input(
                        "Anggaran pembanding (Rp)", min_value=0, max_value=1_000_000_000_000_000,
                        value=st.session_state.get("saved_comparison_budget", 750_000_000),
                        step=50_000_000, key="comparison_budget", on_change=save_comparison_budget,
                    )
        budget_slider(key="budget_curve",
                      data={**budget_chart_data(market.Harga_Rp, budget, comparison), "animate": animate},
                      on_committed_change=commit_chart_budget, on_compared_change=commit_chart_comparison,
                      width="stretch")
    with side, st.container(border=True, key="budget-ranking"):
        st.subheader("Pilihan per wilayah")
        sorting = st.radio("Urutkan wilayah", ["Jumlah listing", "Persentase"], horizontal=True,
                           key="ranking_sort", label_visibility="collapsed")
        ranking = budget_breakdown(market, affordable)
        previous_ranking = ranking if previous is None else budget_breakdown(market, previous)
        by_count = sorting == "Jumlah listing"
        if by_count:
            ranking = ranking.sort_values(["matches", "share", "Kota"], ascending=[False, False, True])
        field = "matches" if by_count else "share"
        scale = max(1, ranking[field].max(), previous_ranking[field].max()) if by_count else 1
        old = previous_ranking.set_index("Kota")[field].to_dict()
        rows = [dict(city=city, value=value, label=number(value) if by_count else percent(value),
                     start=0 if animate else old[city],
                     samples=f"{percent(share)} dari {number(total)} listing"
                     if by_count else f"{number(matches)} dari {number(total)} listing")
                for city, matches, total, share, value in ranking.assign(value=ranking[field])[
                    ["Kota", "matches", "total", "share", "value"]].itertuples(index=False, name=None)]
        region_ranking(key="budget_ranking",
                       data={"rows": rows, "byCount": by_count, "scale": float(scale),
                             "animate": animate or previous is not None}, width="stretch")
    if affordable.empty:
        st.info("Belum ada listing dalam anggaran ini. Coba naikkan batas anggaran atau pilih wilayah lain.")
    with st.expander("Bandingkan rumah dengan luas serupa"):
        render_similar_area(affordable, sorted(market.Kota.unique()))
    with st.expander("Cara membaca grafik anggaran"):
        st.write("Garis menghitung semua listing di wilayah terpilih dengan harga paling tinggi sebesar angka pada sumbu bawah. Titik pada garis menandai anggaran aktif.")
        st.write("Persentase wilayah memakai semua listing berharga valid di wilayah itu sebagai penyebut. "
                 "Anggaran pembanding memakai wilayah yang sama dan tidak mengubah filter aktif.")
        st.write("Harga tengah (median) membagi urutan harga menjadi dua. Harga yang ditampilkan adalah harga penawaran rumah sekunder.")


def render_specs(affordable, animate):
    if affordable.empty:
        st.info("Belum ada rumah dalam anggaran ini. Naikkan batas anggaran untuk melihat spesifikasinya.")
        return
    sizes = affordable.loc[positive(affordable.Luas_Bangunan_m2)]
    focus = st.session_state.get("region_focus")
    if focus is not None:
        affordable = affordable.loc[affordable.Kota.eq(focus)]
    focused_sizes = affordable.loc[positive(affordable.Luas_Bangunan_m2)]
    counts = room_counts(affordable)
    leaders = counts[counts.eq(counts.max())]
    if len(leaders) == 1:
        bed, bath = leaders.index[0]
        bedrooms = f"{int(bed)} KT · {int(bath)} KM"
    elif len(leaders) > 1:
        bedrooms = f"{number(len(leaders))} kombinasi seri"
    else:
        bedrooms = "Tidak tersedia"
    metrics([
        ("Luas bangunan tengah", focused_sizes.Luas_Bangunan_m2.median(), area_text),
        ("Kamar paling umum", bedrooms, None),
        ("Dalam anggaran", len(affordable), number),
    ], animate)
    main, side = st.columns([1.45, 1], gap="small")
    with main, st.container(border=True, key="size-chart"):
        st.subheader("Luas bangunan per wilayah")
        if sizes.empty:
            st.info("Belum ada luas bangunan yang tercatat untuk pilihan ini.")
        else:
            region_bars(key="region_bars", data=region_chart_data(sizes, focus, animate),
                        on_selected_change=select_region, width="stretch")
    grid = room_grid(affordable)
    coverage = int(grid.values.sum())
    with side, st.container(border=True, key="room-chart"):
        st.subheader("Kombinasi kamar")
        if coverage:
            with st.container(key="room-reveal" if animate else "room-steady"):
                st.plotly_chart(heatmap_chart(grid, len(affordable)), key="spec_heatmap",
                                width="stretch", config={"displayModeBar": False})
        else:
            st.info("Tidak ada kombinasi 1–6 kamar tidur dan kamar mandi.")
    with st.expander("Lihat tabel listing"):
        search_box, export_box = st.columns([3, 1], gap="small", vertical_alignment="bottom")
        search = search_box.text_input("Cari nama atau lokasi", key="listing_search",
                                       placeholder="Contoh: Bekasi atau nama perumahan")
        table = listing_results(affordable, search)
        export_box.download_button("Unduh CSV", data=table.to_csv(index=False).encode("utf-8-sig"),
                                   file_name="listing_jabodetabek.csv", mime="text/csv",
                                   key="listing_csv", width="stretch", disabled=table.empty)
        st.caption(f"{number(len(table))} dari {number(len(affordable))} listing")
        if table.empty:
            st.info("Tidak ada listing yang cocok. Coba nama atau lokasi lain.")
        st.dataframe(
            table.style.set_properties(subset=["Harga_Rp"], **PRICE_CELL_STYLE),
            hide_index=True, width="stretch", row_height=34,
            column_order=["Nama", "Harga_Rp", "Luas_Bangunan_m2", "Kota", "Lokasi",
                          "Kamar_Tidur", "Kamar_Mandi", "Luas_Tanah_m2"],
            column_config={
                "Nama": st.column_config.TextColumn("Nama listing", width="medium"),
                "Kota": "Wilayah",
                "Harga_Rp": st.column_config.NumberColumn("Harga (Rp)", format="localized", width=145),
                "Luas_Tanah_m2": "Luas tanah (m²)", "Luas_Bangunan_m2": "Luas bangunan (m²)",
                "Kamar_Tidur": "Kamar tidur", "Kamar_Mandi": "Kamar mandi",
            },
        )
    with st.expander("Cara membaca grafik rumah"):
        st.write("Luas tengah (median) membagi urutan luas bangunan menjadi dua. Perhitungan memakai luas bangunan positif dan terhingga.")
        st.write(f"KT berarti kamar tidur dan KM berarti kamar mandi. Grid menghitung {number(coverage)} listing dengan kombinasi 1–6 pada kedua ukuran.")
        if len(leaders) > 1:
            ties = ", ".join(f"{int(b)} KT · {int(m)} KM" for b, m in leaders.index)
            st.write(f"Kombinasi terbanyak yang seri: {ties}.")
        st.write("Ringkasan kamar memakai semua pasangan bilangan bulat positif, termasuk kombinasi di luar grid.")


def apply_preset(preset):
    st.session_state.budget = preset


def reset_filters(regions):
    st.session_state.budget = DEFAULT_BUDGET
    st.session_state.regions = regions
    st.session_state.region_focus = None


def select_page(index):
    st.session_state.page_index = index


def render_navigation(index):
    with st.container(key="nav-rail"):
        expanded = st.session_state.get("nav_expanded", True)
        st.button("Ringkas sidebar" if expanded else "Lebarkan sidebar",
                  icon=":material/chevron_left:" if expanded else ":material/chevron_right:",
                  key="nav-toggle", type="tertiary" if expanded else "secondary", width="stretch",
                  on_click=toggle_navigation)
        for position, (label, icon) in enumerate(NAVIGATION):
            st.button(label, icon=icon, key=f"nav-{position}", width="stretch",
                      type="primary" if index == position else "secondary",
                      on_click=select_page, args=(position,))


def toggle_navigation():
    st.session_state.nav_expanded = not st.session_state.get("nav_expanded", True)


def main():
    st.set_page_config(page_title="Potret Harga Rumah Jabodetabek", layout="wide")
    st.html(Path(__file__).with_name("dashboard.css"))
    try:
        with st.spinner("Memuat listing rumah…"):
            data = load_data(str(DATA_PATH), DATA_PATH.stat().st_mtime_ns)
    except (OSError, ValueError, ImportError, BadZipFile):
        st.error("Data listing tidak bisa dibaca. Periksa file Excel sumber.")
        return

    market = data.loc[positive(data.Harga_Rp) & data.Kota.notna() & data.Kota.ne("")]
    if market.empty:
        st.error("Tidak ada listing dengan wilayah dan harga yang valid.")
        return
    regions = sorted(market.Kota.unique())
    st.session_state.setdefault("budget", DEFAULT_BUDGET)

    index = st.session_state.setdefault("page_index", 0)
    render_navigation(index)
    render_page(index, market, regions)


def render_page(index, market, regions):
    animate = st.session_state.get("rendered_page") != index
    previous_budget = st.session_state.pop("chart_previous_budget", None)
    st.session_state.rendered_page = index
    title, control = st.columns([3, 1], gap="small", vertical_alignment="center")
    title.title(MENUS[index])
    with control, st.popover("Anggaran & wilayah", icon=":material/tune:", width="stretch"):
        st.caption("Pintasan anggaran")
        with st.container(horizontal=True, gap="small"):
            for preset in PRESETS:
                st.button(rupiah(preset), key=f"preset-{preset}", on_click=apply_preset, args=(preset,))
        budget = st.number_input("Anggaran maksimal (Rp)", min_value=0, max_value=1_000_000_000_000_000,
                                 step=50_000_000, key="budget")
        chosen = st.multiselect("Wilayah", regions, default=regions, key="regions")
        st.button("Reset filter", key="reset_filters", on_click=reset_filters, args=(regions,))

    scope = "Semua wilayah" if len(chosen) == len(regions) else ", ".join(chosen)
    if not chosen:
        st.session_state.region_focus = None
        st.info("Pilih setidaknya satu wilayah untuk melihat listing.")
        return
    st.caption(f"{scope} · Anggaran hingga {rupiah(budget)}")
    market = market.loc[market.Kota.isin(chosen)]
    affordable = market.loc[market.Harga_Rp.le(budget)]
    if st.session_state.get("region_focus") not in affordable.loc[
            positive(affordable.Luas_Bangunan_m2), "Kota"].unique():
        st.session_state.region_focus = None
    with st.container(key=f"view-{index}"):
        if index == 0:
            render_budget(market, affordable, budget, animate, previous_budget)
        else:
            render_specs(affordable, animate)
    st.caption("Sumber: Data_Rumah_Jabodetabek.xlsx · Harga penawaran rumah sekunder")


if __name__ == "__main__":
    main()
