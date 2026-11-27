const $ = (id) => document.getElementById(id); // cheap jQuery :)
const isTrue = (v) => v === true || String(v).toLowerCase() === "true";

const statusLabels = {
  100: "CONTINUE",
  101: "SWITCHING_PROTOCOLS",
  200: "OK",
  201: "CREATED",
  202: "ACCEPTED",
  204: "NO_CONTENT",
  206: "PARTIAL_CONTENT",
  301: "MOVED_PERMANENTLY",
  302: "FOUND",
  304: "NOT_MODIFIED",
  307: "TEMPORARY_REDIRECT",
  308: "PERMANENT_REDIRECT",
  400: "BAD_REQUEST",
  401: "UNAUTHORIZED",
  403: "FORBIDDEN",
  404: "NOT_FOUND",
  405: "METHOD_NOT_ALLOWED",
  408: "REQUEST_TIMEOUT",
  409: "CONFLICT",
  410: "GONE",
  413: "PAYLOAD_TOO_LARGE",
  415: "UNSUPPORTED_MEDIA_TYPE",
  422: "UNPROCESSABLE_ENTITY",
  429: "TOO_MANY_REQUESTS",
  500: "INTERNAL_SERVER_ERROR",
  501: "NOT_IMPLEMENTED",
  502: "BAD_GATEWAY",
  503: "SERVICE_UNAVAILABLE",
  504: "GATEWAY_TIMEOUT",
};

let chart = null;
let logs = [];
let chartContentWidth = 400;

function updateBadge(id, ok, upText, downText) {
  const el = $(id);
  if (!el) return;
  el.textContent = `• ${ok ? upText : downText}`;
  el.classList.toggle("status-up", ok);
  el.classList.toggle("status-down", !ok);
}

async function fetchStatus() {
  try {
    const res = await fetch("/api/status");
    if (!res.ok) return;
    const d = await res.json();

    updateBadge("dns-status", isTrue(d.dns_up), "UP", "DOWN");
    updateBadge("gateway-status", isTrue(d.gateway_up), "UP", "DOWN");

    $("ssid-signal").textContent =
      d.signal_strength != null ? `${d.signal_strength} dBm` : "N/A";

    $("ssid-status").textContent = isTrue(d.ssid_visible)
      ? `${d.ssid_name}`
      : "N/A";

    updateBadge("internet-status", d.internet_up, "REACHABLE", "UNREACHABLE");
  } catch (e) {
    console.error(e);
  }
}

function parseEntry(row) {
  const internet = isTrue(row.internet_up);
  const gateway = isTrue(row.gateway_up);
  const dns = isTrue(row.dns_up);
  const ssid = isTrue(row.ssid_visible);
  const code = Number(row.status_code) || 0;
  const validCode = code in statusLabels;

  const issues = [];
  if (!internet) issues.push("Internet");
  if (!gateway) issues.push("Gateway");
  if (!dns) issues.push("DNS");
  if (!ssid) issues.push("SSID");
  if (!validCode) issues.push(code ? `HTTP ${code}` : "Timeout");

  let state = 1;
  if (!internet || !gateway) state = 0;
  else if (!dns || !ssid || !validCode) state = 2;

  return { ts: Number(row.timestamp), state, code, issues };
}

const fmtTime = (sec) =>
  new Date(sec * 1000).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });

const labels = { 0: "[ DOWN ]", 1: "[ UP ]", 2: "[ DEGRADED ]" };
const colors = {
  0: ["#EF4444", "#F87171"],
  1: ["#C75CE0", "#E879F9"],
  2: ["#F59E0B", "#FBBF24"],
};

function setupChartScroll() {
  const el = $("uptime-chart");
  if (!el) return null;

  let wrapper = el.parentElement;

  if (!wrapper.classList.contains("chart-scroll-wrapper")) {
    const scroll = document.createElement("div");

    scroll.className = "chart-scroll-wrapper";
    scroll.style.width = "100%";
    scroll.style.overflowX = "auto";
    scroll.style.overflowY = "hidden";
    scroll.style.scrollbarWidth = "thin";
    scroll.style.scrollbarColor = "#9635BD #050505";

    el.parentNode.insertBefore(scroll, el);
    scroll.appendChild(el);

    wrapper = scroll;
  }

  return wrapper;
}

function chartViewportWidth() {
  const wrapper = setupChartScroll();
  return wrapper?.clientWidth || 400;
}

function chartWidth() {
  return chartContentWidth || chartViewportWidth();
}

const WINDOW_SECONDS = 1200;
const BAR_WIDTH = 8;
const BAR_GAP = 18;

function updateChartWidth() {
  const viewport = chartViewportWidth();

  if (!logs.length) {
    chartContentWidth = viewport;
    return;
  }

  const duration =
    logs.length > 1 ? logs[logs.length - 1].ts - logs[0].ts : WINDOW_SECONDS;

  const timeWidth = viewport * (duration / WINDOW_SECONDS);
  const countWidth = logs.length * (BAR_WIDTH + BAR_GAP) + 72;

  chartContentWidth = Math.max(viewport, timeWidth, countWidth);
}

const barsPlugin = {
  hooks: {
    draw: [
      (u) => {
        const { ctx } = u;
        const [xs, ys] = u.data;
        if (!xs.length) return;

        const px = uPlot.pxRatio;
        const gap = BAR_GAP * px;
        const step =
          xs.length > 1
            ? Math.abs(
                u.valToPos(xs[1], "x", true) - u.valToPos(xs[0], "x", true),
              )
            : (BAR_WIDTH + BAR_GAP) * px;

        const MAX_BAR_WIDTH = 12;
        const w = Math.max(
          BAR_WIDTH * px,
          Math.min(MAX_BAR_WIDTH * px, step - gap),
        );

        const base = u.valToPos(0, "y", true);

        ctx.save();

        for (let i = 0; i < xs.length; i++) {
          const x = u.valToPos(xs[i], "x", true);
          const y = u.valToPos(ys[i], "y", true);
          const left = Math.round(x - w / 2);
          const top = Math.round(y);
          const width = Math.round(w);
          const height = Math.round(base - top);

          const r = Math.min(width / 2, height / 2);

          ctx.fillStyle = colors[logs[i].state][i === u.cursor.idx ? 1 : 0];
          ctx.beginPath();
          ctx.roundRect(left, top, width, height, r);
          ctx.fill();
        }

        ctx.restore();
      },
    ],
  },
};

function drawChart(rows) {
  const readout = $("hover-readout");
  const summary = document.querySelector(".chart-summary");

  if (!Array.isArray(rows) || !rows.length) {
    readout.textContent = "No uptime logs available yet";
    return;
  }

  const wrapper = setupChartScroll();

  const wasAtEnd =
    !chart ||
    wrapper.scrollWidth - wrapper.scrollLeft - wrapper.clientWidth < 40;

  logs = rows
    .map(parseEntry)
    .filter((l) => Number.isFinite(l.ts))
    .sort((a, b) => a.ts - b.ts);

  if (!logs.length) {
    readout.textContent = "No valid uptime logs available";
    return;
  }

  const times = logs.map((l) => l.ts);
  const heights = logs.map(() => 80);

  updateChartWidth();

  if (summary) {
    const up = logs.filter((l) => l.state !== 0).length;
    summary.textContent = `${((up / logs.length) * 100).toFixed(1)}%`;
  }

  if (chart) {
    chart.setData([times, heights]);
    chart.setSize({ width: chartWidth(), height: 80 });
  } else {
    chart = new uPlot(
      {
        width: chartWidth(),
        height: 64,
        padding: [8, 36, 0, 36],
        plugins: [barsPlugin],

        cursor: {
          drag: { x: false, y: false },
          points: { show: false },
          y: false,
        },

        scales: {
          x: { time: true },
          y: { range: [0, 105] },
        },

        axes: [
          {
            stroke: "#D46CE5",
            grid: { show: false },
            ticks: { show: false },
            size: 24,
            space: 55,
            font: "12px TerminalFont, ui-monospace, monospace",
            values: (_, vals) => vals.map(fmtTime),
          },
          { show: false },
        ],

        series: [
          {},
          {
            label: "Uptime",
            paths: () => null,
            points: { show: false },
          },
        ],
        hooks: {
          setCursor: [
            (u) => {
              const i = u.cursor.idx;

              if (i == null || i < 0 || i >= logs.length) {
                readout.textContent = "Hover a bar to inspect interval status";
                return;
              }

              const item = logs[i];
              const info = item.issues.length
                ? `Issues: ${item.issues.join(", ")}`
                : `HTTP ${item.code}`;

              readout.textContent = `${fmtTime(item.ts)} · ${labels[item.state]} · ${info}`;
            },
          ],
        },
      },
      [times, heights],
      $("uptime-chart"),
    );
  }

  if (wasAtEnd) {
    requestAnimationFrame(() => {
      wrapper.scrollLeft = wrapper.scrollWidth;
    });
  }
}

async function fetchLogs() {
  try {
    const res = await fetch("/api/logs");
    if (!res.ok) return;
    drawChart(await res.json());
  } catch (e) {
    console.error(e);
  }
}

async function handleUrlCheck() {
  btn = $("url-check-btn");
  btnText = $("url-check-btn-text");
  btnLoader = $("url-check-btn-loader");
  url = $("website-url").value;
  dnsStatus = $("url-check-dns-status");
  responseCode = $("url-check-response-code");
  responseLength = $("url-check-response-length");
  dnsStatus.classList.remove("status-up");
  responseCode.classList.remove("status-up");
  responseLength.classList.remove("status-up");
  dnsStatus.classList.remove("status-down");
  responseCode.classList.remove("status-down");
  responseLength.classList.remove("status-down");

  if (!url.includes(".")) {
    return;
  }
  btn.disabled = true;
  btnText.classList.add("hidden");
  btnLoader.classList.remove("hidden");
  dnsStatus.innerHTML = `<span is-="spinner"></span>`;
  responseCode.innerHTML = `<span is-="spinner"></span>`;
  responseLength.innerHTML = `<span is-="spinner"></span>`;

  function stopLoading() {
    btn.disabled = false;
    btnText.classList.remove("hidden");
    btnLoader.classList.add("hidden");
    dnsStatus.innerHTML = `• ----`;
    responseCode.innerHTML = `• ----`;
    responseLength.innerHTML = `• ----`;
  }

  try {
    const res = await fetch("/api/check_website", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ url: url }),
    });
    if (!res.ok) {
      stopLoading();
      return;
    }
    data = await res.json();
    function setLabel(label, text, up) {
      label.innerText = `• ${text}`;
      if (up) {
        label.classList.remove("status-down");
        label.classList.add("status-up");
      } else {
        label.classList.add("status-down");
        label.classList.remove("status-up");
      }
    }
    stopLoading();
    setLabel(
      dnsStatus,
      data.dns_resolved ? "RESOLVED" : "UNRESOLVED",
      data.dns_resolved,
    );
    setLabel(
      responseCode,
      data.status_code
        ? `${data.status_code} ${statusLabels[data.status_code] || "OTHER"}`
        : "N/A",
      data.status_code && data.status_code > 100 && data.status_code < 400,
    );
    setLabel(
      responseLength,
      data.response_length ? `${data.response_length} BYTES` : "N/A",
      data.response_length,
    );
  } catch {
    stopLoading();
    dnsStatus.innerHTML = `• ----`;
    responseCode.innerHTML = `• ----`;
    responseLength.innerHTML = `• ----`;
  }
}

window.addEventListener("resize", () => {
  if (!chart) return;

  const wrapper = setupChartScroll();
  const wasAtEnd =
    wrapper.scrollWidth - wrapper.scrollLeft - wrapper.clientWidth < 40;

  updateChartWidth();

  chart.setSize({
    width: chartWidth(),
    height: 110,
  });

  if (wasAtEnd) {
    requestAnimationFrame(() => {
      wrapper.scrollLeft = wrapper.scrollWidth;
    });
  }
});

fetchStatus();
fetchLogs();
setInterval(fetchStatus, 5000);
setInterval(fetchLogs, 30000);
