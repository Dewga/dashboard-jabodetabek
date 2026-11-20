"""Small browser interactions that don't need a frontend build."""
import streamlit as st


_MOTION_JS = """
  function reveal(enabled, duration, draw) {
    if (!enabled || matchMedia("(prefers-reduced-motion: reduce)").matches) {
      draw(1);
      return () => {};
    }
    const start = performance.now();
    let frame;
    function tick(now) {
      const progress = Math.min(1, Math.max(0, (now - start) / duration));
      draw(progress);
      if (progress < 1) frame = requestAnimationFrame(tick);
    }
    draw(0);
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }
  function barProgress(progress, index, count) {
    const offset = .24 * index / Math.max(1, count - 1);
    const local = Math.max(0, Math.min(1, (progress - offset) / .76));
    return 1 - (1 - local) ** 3;
  }
"""


region_bars = st.components.v2.component(
    "region_bars",
    html="""
      <div class="chart" role="group" aria-label="Luas bangunan per wilayah">
        <div class="legend">Titik: median · Garis: 50% tengah</div>
        <div class="rows"></div>
        <div class="axis" aria-hidden="true"></div>
        <div class="footer">
          <span class="summary" role="status"></span>
          <button type="button" class="clear">Hapus fokus</button>
        </div>
      </div>
    """,
    css="""
      .chart { color: #213126; font: inherit; font-size: .82rem; }
      .legend { color: #4c6052; font-size: .75rem; }
      .row {
        display: grid; grid-template-columns: var(--city, 5.5rem) minmax(0, 1fr) 5.1rem;
        align-items: center; gap: .5rem; width: 100%; min-height: 44px;
        text-align: left; padding: 0; border: 0; background: transparent;
        color: inherit; font: inherit; cursor: pointer;
      }
      .row:focus-visible, .clear:focus-visible { outline: 2px solid #436b53; outline-offset: 2px; }
      .track {
        position: relative; min-width: 0; height: 34px;
        background: repeating-linear-gradient(90deg, #e2e9df 0 1px, transparent 1px 25%);
      }
      .bar {
        position: absolute; top: 14px; height: 6px; border-radius: 3px;
        background: #789480; transition: background-color 200ms;
      }
      .dot {
        position: absolute; top: 17px; width: 10px; height: 10px; border-radius: 50%;
        background: #355842; transform: translate(-50%, -50%); transition: transform 200ms, background-color 200ms;
      }
      .rows.focused .bar, .rows.focused .dot { background: #858f87; }
      .rows .row[aria-pressed="true"] { font-weight: 650; }
      .rows .row[aria-pressed="true"] :is(.bar, .dot) { background: #355842; }
      .rows .row[aria-pressed="true"] .dot, .row:is(:hover, :focus-visible) .dot {
        transform: translate(-50%, -50%) scale(1.2);
      }
      .stat { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }
      .stat small { display: block; color: #4c6052; font-size: .69rem; font-weight: 400; }
      .axis {
        display: flex; justify-content: space-between; margin: .15rem 5.6rem .35rem calc(var(--city, 5.5rem) + .5rem);
        color: #4c6052; font-size: .72rem;
      }
      .footer {
        display: flex; flex-wrap: wrap; align-items: center; gap: .35rem .65rem;
        min-height: 44px; border-top: 1px solid #d9ded5; padding-top: .25rem;
      }
      .summary { flex: 1 1 13rem; }
      .clear {
        color: #30513c; background: transparent; border: 1px solid #b9c9bc;
        border-radius: 8px; min-height: 44px; padding: 0 .6rem; font: inherit; cursor: pointer;
      }
      .clear:hover { background: #e2ece0; }
      @media (max-width: 540px) {
        .chart { --city: 4.1rem; }
      }
      @media (prefers-reduced-motion: reduce) { .bar, .dot { transition: none; } }
    """,
    js=_MOTION_JS + """
      export default function({ parentElement, data, setTriggerValue }) {
        const rows = parentElement.querySelector(".rows");
        const axis = parentElement.querySelector(".axis");
        const summary = parentElement.querySelector(".summary");
        const clear = parentElement.querySelector(".clear");
        const buttons = new Map([...rows.children].map(button => [button.dataset.city, button]));
        const fmt = new Intl.NumberFormat("id-ID", {maximumFractionDigits: 1});
        let selected = data.selected;
        function paint() {
          rows.classList.toggle("focused", selected !== null);
          for (const button of rows.children) {
            button.setAttribute("aria-pressed", String(button.dataset.city === selected));
          }
          summary.textContent = data.rows.find(row => row.city === selected)?.summary
            ?? "Pilih wilayah untuk melihat rincian.";
          clear.hidden = selected === null;
        }
        function select(city) {
          selected = city === selected ? null : city;
          if (selected === null && parentElement.activeElement === clear) {
            buttons.get(clear.dataset.city)?.focus();
          }
          paint();
          setTriggerValue("selected", {city: selected});
        }
        for (const [index, row] of data.rows.entries()) {
          let button = buttons.get(row.city);
          if (!button) {
            button = document.createElement("button");
            button.type = "button";
            button.className = "row";
            button.dataset.city = row.city;
            button.innerHTML = '<span class="city"></span><span class="track" aria-hidden="true"><span class="bar"></span><span class="dot"></span></span><span class="stat"><span class="value"></span><small></small></span>';
            buttons.set(row.city, button);
          }
          button.querySelector(".city").textContent = row.city;
          button.querySelector("small").textContent = row.count + " listing";
          button.title = row.tooltip;
          button.setAttribute("aria-label", row.tooltip);
          button.onclick = () => select(row.city);
          if (rows.children[index] !== button) rows.insertBefore(button, rows.children[index] ?? null);
        }
        for (const button of [...rows.children].slice(data.rows.length)) button.remove();
        axis.replaceChildren(...data.ticks.map(label => {
          const tick = document.createElement("span");
          tick.textContent = label;
          return tick;
        }));
        clear.onclick = () => {
          clear.dataset.city = selected;
          select(null);
        };
        paint();
        return reveal(data.animate, 620, progress => {
          for (const [index, row] of data.rows.entries()) {
            const fraction = barProgress(progress, index, data.rows.length);
            const button = buttons.get(row.city);
            const bar = button.querySelector(".bar");
            bar.style.left = row.left * fraction + "%";
            bar.style.width = (row.right - row.left) * fraction + "%";
            button.querySelector(".dot").style.left = row.position * fraction + "%";
            button.querySelector(".value").textContent = fraction === 1
              ? row.value : fmt.format(row.median * fraction) + " m²";
          }
        });
      }
    """,
)


budget_slider = st.components.v2.component(
    "budget_slider",
    html="""
      <div class="readout"><strong aria-hidden="true"></strong><span aria-hidden="true"></span>
        <span class="difference" hidden></span>
      </div>
      <div class="plot">
        <canvas aria-hidden="true"></canvas>
        <input class="active" type="range" min="0" step="1" aria-label="Anggaran maksimal pada grafik" />
        <input class="comparison" type="range" min="0" step="1" aria-label="Anggaran pembanding pada grafik" hidden disabled />
      </div>
      <p class="hint">Geser penanda untuk mengubah anggaran aktif.</p>
    """,
    css="""
      .readout { display: flex; align-items: baseline; flex-wrap: wrap; gap: .2rem .7rem;
        padding: .15rem 0; color: #30513c; font-size: .85rem; font-variant-numeric: tabular-nums; }
      .readout span, .hint { color: #4c6052; font-size: .75rem; }
      .readout .difference { color: #213126; font-weight: 600; }
      .plot { position: relative; height: 244px; }
      canvas { display: block; width: 100%; height: 100%; }
      .active {
        position: absolute; inset: 0 12px 33px 47px; width: calc(100% - 59px);
        height: calc(100% - 33px); margin: 0; opacity: 0;
        cursor: ew-resize; touch-action: pan-y; appearance: none;
      }
      .active::-webkit-slider-thumb { appearance: none; width: 1px; height: 44px; }
      .active::-moz-range-thumb { width: 1px; height: 44px; border: 0; }
      .comparison {
        appearance: none; position: absolute; z-index: 1; top: 0; left: 25px;
        width: calc(100% - 15px); height: 44px; margin: 0;
        background: transparent; pointer-events: none; touch-action: pan-y;
      }
      .comparison::-webkit-slider-thumb {
        appearance: none; pointer-events: auto; cursor: ew-resize;
        width: 44px; height: 44px; border: 12px solid transparent; border-radius: 18px;
        background: #657269; background-clip: padding-box;
      }
      .comparison::-moz-range-thumb {
        box-sizing: border-box; pointer-events: auto; cursor: ew-resize;
        width: 44px; height: 44px; border: 12px solid transparent; border-radius: 18px;
        background: #657269; background-clip: padding-box;
      }
      .plot:has(input:focus-visible) { outline: 2px solid #436b53; outline-offset: 2px; }
      .hint { margin: .15rem 0 0; }
    """,
    js=_MOTION_JS + """
      export default function({ parentElement, data, setTriggerValue }) {
        const canvas = parentElement.querySelector("canvas");
        const input = parentElement.querySelector(".active");
        const compare = parentElement.querySelector(".comparison");
        const amount = parentElement.querySelector(".readout strong");
        const listing = parentElement.querySelector(".readout span");
        const difference = parentElement.querySelector(".difference");
        const ctx = canvas.getContext("2d");
        const fmt = new Intl.NumberFormat("id-ID", {maximumFractionDigits: 2});
        const countFmt = new Intl.NumberFormat("id-ID");
        const shareFmt = new Intl.NumberFormat("id-ID", {style: "percent", maximumFractionDigits: 1});
        const snap = 10_000_000;
        const formatPrice = (value) => value >= 1e9 ? "Rp" + fmt.format(value / 1e9) + " miliar"
          : value >= 1e6 ? "Rp" + fmt.format(value / 1e6) + " juta" : "Rp" + fmt.format(value);
        let current = data.budget;
        let committed = current;
        let comparison = data.comparison;
        const comparing = comparison !== null;
        let committedComparison = comparison;
        let displayed = current;
        let stopMotion = () => {};
        let visibleFraction = 1;
        input.max = String(data.upper);
        input.value = String(current);
        compare.hidden = compare.disabled = difference.hidden = !comparing;
        parentElement.querySelector(".hint").textContent = comparing
          ? "Penanda bawah: anggaran aktif. Penanda atas: pembanding."
          : "Geser penanda untuk mengubah anggaran aktif.";
        if (comparing) {
          compare.max = String(data.upper);
          compare.value = String(comparison);
        }
        function countAt(price) {
          let low = 0, high = data.points.length;
          while (low < high) {
            const mid = (low + high) >>> 1;
            if (data.points[mid][0] <= price) low = mid + 1;
            else high = mid;
          }
          return low ? data.points[low - 1][1] : 0;
        }
        function paint() {
          const price = Math.round(displayed);
          const count = countAt(price);
          amount.textContent = formatPrice(price);
          listing.textContent = countFmt.format(count) + " listing · " + shareFmt.format(count / data.total);
          listing.hidden = current === committed;
          if (comparing) {
            const lower = Math.min(price, comparison), upper = Math.max(price, comparison);
            const extra = countAt(upper) - countAt(lower);
            difference.textContent = lower === upper ? "Kedua anggaran sama · 0 listing tambahan"
              : formatPrice(lower) + " → " + formatPrice(upper) + " · +" + countFmt.format(extra) + " listing";
            compare.setAttribute("aria-valuetext", formatPrice(comparison) + ", "
              + countFmt.format(Math.abs(countAt(current) - countAt(comparison))) + " listing selisih");
          }
          const selectedCount = countAt(current);
          input.setAttribute("aria-valuetext", formatPrice(current) + ", "
            + countFmt.format(selectedCount) + " listing · " + shareFmt.format(selectedCount / data.total));
          const {width, height} = canvas.getBoundingClientRect();
          if (!width || !height) return;
          const dpr = window.devicePixelRatio || 1;
          const pixelWidth = Math.round(width * dpr), pixelHeight = Math.round(height * dpr);
          if (canvas.width !== pixelWidth || canvas.height !== pixelHeight) {
            canvas.width = pixelWidth;
            canvas.height = pixelHeight;
          }
          ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
          ctx.clearRect(0, 0, width, height);
          const left = 47, right = width - 12, top = comparing ? 31 : 14, bottom = height - 33;
          const maxCount = Math.max(4, countAt(data.upper));
          const countStep = Math.ceil(maxCount / 4);
          const x = (value) => left + value / data.upper * (right - left);
          const y = (value) => bottom - value / (countStep * 4) * (bottom - top);
          ctx.font = "12px system-ui";
          ctx.fillStyle = "#4c6052";
          ctx.strokeStyle = "#dce4d9";
          ctx.lineWidth = 1;
          ctx.textAlign = "right";
          for (let i = 0; i < 5; i++) {
            const pos = y(i * countStep);
            ctx.beginPath(); ctx.moveTo(left, pos); ctx.lineTo(right, pos); ctx.stroke();
            ctx.fillText(countFmt.format(i * countStep), left - 6, pos + 4);
          }
          const divisions = width < 460 ? 2 : 4;
          for (let i = 0; i <= divisions; i++) {
            const price = i * data.upper / divisions;
            ctx.textAlign = i === 0 ? "left" : i === divisions ? "right" : "center";
            ctx.fillText(formatPrice(price), x(price), bottom + 20);
          }
          ctx.save();
          ctx.beginPath();
          ctx.rect(left - 2, 0, (right - left) * visibleFraction + 4, height);
          ctx.clip();
          ctx.beginPath();
          ctx.moveTo(left, bottom);
          let prior = 0;
          for (const [price, total] of data.points) {
            ctx.lineTo(x(price), y(prior));
            ctx.lineTo(x(price), y(total));
            prior = total;
          }
          ctx.lineTo(right, y(prior));
          ctx.strokeStyle = "#436b53"; ctx.lineWidth = 2.5; ctx.stroke();
          ctx.lineTo(right, bottom); ctx.closePath();
          ctx.fillStyle = "#436b5324"; ctx.fill();
          ctx.restore();
          if (comparing && comparison !== current && visibleFraction >= comparison / data.upper) {
            const comparisonX = x(comparison);
            ctx.strokeStyle = "#657269";
            ctx.lineWidth = 1;
            ctx.setLineDash([2, 3]);
            ctx.beginPath(); ctx.moveTo(comparisonX, top); ctx.lineTo(comparisonX, bottom); ctx.stroke();
            ctx.setLineDash([]);
            ctx.beginPath(); ctx.arc(comparisonX, y(countAt(comparison)), 4, 0, 2 * Math.PI);
            ctx.fillStyle = "#fff"; ctx.fill(); ctx.stroke();
          }
          if (visibleFraction < price / data.upper) return;
          ctx.strokeStyle = "#436b53";
          ctx.beginPath(); ctx.setLineDash([3, 4]); ctx.lineWidth = 1;
          ctx.moveTo(x(price), top); ctx.lineTo(x(price), bottom); ctx.stroke(); ctx.setLineDash([]);
          ctx.beginPath(); ctx.arc(x(price), y(count), 6, 0, 2 * Math.PI);
          ctx.fillStyle = "#436b53"; ctx.fill();
          ctx.strokeStyle = "#fff"; ctx.lineWidth = 2; ctx.stroke();
          ctx.fillStyle = "#355842";
          ctx.beginPath(); ctx.roundRect(x(price) - 11, bottom - 9, 22, 18, 4); ctx.fill();
          ctx.strokeStyle = "#fff"; ctx.lineWidth = 1;
          for (const offset of [-3, 0, 3]) {
            ctx.beginPath(); ctx.moveTo(x(price) + offset, bottom - 3);
            ctx.lineTo(x(price) + offset, bottom + 3); ctx.stroke();
          }
        }
        function commit() {
          stopMotion();
          displayed = current;
          if (current !== committed) {
            committed = current;
            setTriggerValue("committed", current);
          }
          paint();
        }
        function finishReveal() {
          stopReveal();
          visibleFraction = 1;
        }
        function moveTo(value) {
          finishReveal();
          stopMotion();
          const from = displayed;
          current = value;
          stopMotion = reveal(from !== value, 100, progress => {
            displayed = from + (value - from) * (1 - (1 - progress) ** 2);
            paint();
          });
        }
        const snapValue = (value) => Math.min(data.upper, Math.round(Number(value) / snap) * snap);
        input.oninput = () => moveTo(snapValue(input.value));
        input.onchange = commit;
        compare.oninput = () => {
          finishReveal();
          comparison = snapValue(compare.value);
          paint();
        };
        function commitComparison() {
          if (comparison === committedComparison) return;
          committedComparison = comparison;
          compare.value = String(comparison);
          setTriggerValue("compared", comparison);
        }
        compare.onchange = commitComparison;
        function keyBudget(event, value) {
          const directions = {ArrowLeft: -1, ArrowDown: -1, ArrowRight: 1, ArrowUp: 1};
          const direction = directions[event.key];
          if (!direction && !["Home", "End"].includes(event.key)) return null;
          event.preventDefault();
          finishReveal();
          return event.key === "Home" ? 0 : event.key === "End" ? data.upper
            : Math.max(0, Math.min(data.upper, value + direction * snap));
        }
        input.onkeydown = (event) => {
          const value = keyBudget(event, current);
          if (value === null) return;
          current = value;
          input.value = String(current);
          commit();
        };
        compare.onkeydown = (event) => {
          const value = keyBudget(event, comparison);
          if (value === null) return;
          comparison = value;
          paint();
          commitComparison();
        };
        const observer = new ResizeObserver(paint);
        observer.observe(canvas);
        const stopReveal = reveal(data.animate, 560, progress => {
          visibleFraction = 1 - (1 - progress) ** 2;
          paint();
        });
        return () => {
          stopReveal();
          stopMotion();
          observer.disconnect();
        };
      }
    """,
)


kpi_counter = st.components.v2.component(
    "kpi_counter",
    html='<div class="label"></div><div class="value" role="img"><span aria-hidden="true"></span></div>',
    css="""
      .label { font: inherit; font-size: .875rem; color: #213126; }
      .value { margin-top: .18rem; min-height: 1.55em; color: #213126;
        font-size: clamp(1.25rem, 2.2vw, 1.8rem); line-height: 1.35;
        font-weight: 670; font-variant-numeric: tabular-nums; overflow-wrap: anywhere; }
      .value.primary { color: #355842; }
    """,
    js=_MOTION_JS + """
      export default function({ parentElement, data }) {
        const slot = parentElement.querySelector(".value");
        const display = slot.querySelector("span");
        parentElement.querySelector(".label").textContent = data.label;
        slot.setAttribute("aria-label", data.value);
        slot.classList.toggle("primary", data.primary);
        return reveal(data.frames.length > 0, 430, progress => {
          const eased = 1 - (1 - progress) ** 3;
          display.textContent = progress === 1 ? data.value
            : data.frames[Math.floor(eased * (data.frames.length - 1))];
        });
      }
    """,
)


region_ranking = st.components.v2.component(
    "region_ranking",
    html='<div class="ranking" role="list" aria-label="Pilihan per wilayah"></div>',
    css="""
      .ranking { display: grid; gap: .2rem; color: #213126; }
      .rank { padding-block: 1px; }
      .label { display: flex; justify-content: space-between; gap: .5rem; font-size: .875rem; }
      .track { height: 4px; background: #dce6da; margin-top: 4px; border-radius: 2px; }
      .bar { display: block; height: 100%; border-radius: inherit; background: #436b53; }
      .samples { color: #4c6052; font-size: .75rem; }
      .share { font-variant-numeric: tabular-nums; }
    """,
    js=_MOTION_JS + """
      export default function({ parentElement, data }) {
        const ranking = parentElement.querySelector(".ranking");
        const fmt = new Intl.NumberFormat("id-ID", data.byCount
          ? {maximumFractionDigits: 0} : {style: "percent", maximumFractionDigits: 1});
        const nodes = data.rows.map(row => {
          const node = document.createElement("div");
          node.className = "rank";
          node.setAttribute("role", "listitem");
          node.innerHTML = '<div class="label"><strong></strong><span class="share" role="img"></span></div>'
            + '<div class="track" aria-hidden="true"><span class="bar"></span></div><small class="samples"></small>';
          node.querySelector("strong").textContent = row.city;
          node.querySelector(".samples").textContent = row.samples;
          const share = node.querySelector(".share");
          share.setAttribute("aria-label", row.label);
          return {node, share, bar: node.querySelector(".bar")};
        });
        ranking.replaceChildren(...nodes.map(({node}) => node));
        return reveal(data.animate, 620, progress => {
          for (const [index, row] of data.rows.entries()) {
            const fraction = barProgress(progress, index, data.rows.length);
            const {share, bar} = nodes[index];
            const value = row.start + (row.value - row.start) * fraction;
            bar.style.width = value / data.scale * 100 + "%";
            share.textContent = fraction === 1 ? row.label : fmt.format(value);
          }
        });
      }
    """,
)
