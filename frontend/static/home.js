const $ = (id) => document.getElementById(id); // cheap jQuery :)
const isTrue = (v) => v === true || String(v).toLowerCase() === "true";

const statusLabels = {
  200: "OK",
  204: "OK",
  301: "REDIRECT",
  302: "REDIRECT",
};

let chart = null;
let logs = [];

function updateBadge(id, ok, upText, downText) {
  const el = $(id);
  if (!el) return;
  el.textContent = `[ ${ok ? upText : downText} ]`;
  el.classList.toggle("status-up", ok);
  el.classList.toggle("status-down", !ok);
}

async function fetchStatus() {
  try {
    const res = await fetch("/api/status");
    if (!res.ok) return;
    const d = await res.json();

    updateBadge("ssid-status", isTrue(d.ssid_visible), "VISIBLE", "HIDDEN");
    updateBadge("dns-status", isTrue(d.dns_up), "UP", "DOWN");
    updateBadge("gateway-status", isTrue(d.gateway_up), "UP", "DOWN");

    $("ssid-signal").textContent =
      d.signal_strength != null
        ? `Signal: [ ${d.signal_strength} dBm ]`
        : "Signal: [ N/A ]";
    $("dns-server").textContent = d.dns_server
      ? `DNS: [ ${d.dns_server} ]`
      : "DNS: [ N/A ]";
    $("gateway-server").textContent = d.gateway_ip
      ? `[ ${d.gateway_ip} ]`
      : "[ N/A ]";

    if ("internet_up" in d) {
      updateBadge(
        "internet-status",
        isTrue(d.internet_up),
        "REACHABLE",
        "UNREACHABLE",
      );
    }
    if ("status_code" in d) {
      const code = Number(d.status_code);

      if (code && statusLabels[code]) {
        $("internet-response-code").textContent =
          `[ ${code} ${statusLabels[code]} ]`;
      } else if (code) {
        $("internet-response-code").textContent = `[ ${code} ERR ]`;
      } else {
        $("internet-response-code").textContent = "[ TIMEOUT ]";
      }
    }
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
  1: ["#166534", "#22C55E"],
  2: ["#F59E0B", "#FBBF24"],
};

const barsPlugin = {
  hooks: {
    draw: [
      (u) => {
        const { ctx } = u;
        const [xs, ys] = u.data;
        if (!xs.length) return;

        const gap = 4 * uPlot.pxRatio;
        const step =
          xs.length > 1
            ? Math.abs(
                u.valToPos(xs[1], "x", true) - u.valToPos(xs[0], "x", true),
              )
            : 24 * uPlot.pxRatio;
        const w = Math.max(
          4 * uPlot.pxRatio,
          Math.min(28 * uPlot.pxRatio, step - gap),
        );
        const base = u.valToPos(0, "y", true);

        ctx.save();
        for (let i = 0; i < xs.length; i++) {
          const x = u.valToPos(xs[i], "x", true);
          const y = u.valToPos(ys[i], "y", true);
          ctx.fillStyle = colors[logs[i].state][i === u.cursor.idx ? 1 : 0];
          ctx.fillRect(
            Math.round(x - w / 2),
            Math.round(y),
            Math.round(w),
            Math.round(base - y),
          );
        }
        ctx.restore();
      },
    ],
  },
};

function chartWidth() {
  const el = $("uptime-chart");
  return el.clientWidth || el.parentElement.clientWidth - 32 || 400;
}

function drawChart(rows) {
  const readout = $("hover-readout");
  const summary = document.querySelector(".chart-summary");

  if (!Array.isArray(rows) || !rows.length) {
    readout.textContent = "No uptime logs available yet";
    return;
  }

  logs = rows.map(parseEntry).sort((a, b) => a.ts - b.ts);

  const times = logs.map((l) => l.ts);
  const heights = logs.map((l) =>
    l.state === 1 ? 100 : l.state === 2 ? 75 : 40,
  );

  if (summary) {
    const up = logs.filter((l) => l.state !== 0).length;
    summary.textContent = `UPTIME: [ ${((up / logs.length) * 100).toFixed(1)}% ]`;
  }

  if (chart) {
    chart.setData([times, heights]);
    return;
  }

  chart = new uPlot(
    {
      width: chartWidth(),
      height: 170,
      padding: [10, 12, 0, 12],
      plugins: [barsPlugin],
      cursor: {
        drag: { x: false, y: false },
        points: { show: false },
        y: false,
      },
      scales: { x: { time: true }, y: { range: [0, 105] } },
      axes: [
        {
          stroke: "#64748B",
          grid: { show: false },
          ticks: { stroke: "#223042", width: 1 },
          font: "11px TerminalFont, ui-monospace, monospace",
          values: (_, vals) => vals.map(fmtTime),
        },
        { show: false },
      ],
      series: [{}, { label: "Uptime", paths: () => null }],
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

async function fetchLogs() {
  try {
    const res = await fetch("/api/logs");
    if (!res.ok) return;
    drawChart(await res.json());
  } catch (e) {
    console.error(e);
  }
}

window.addEventListener("resize", () => {
  if (chart) chart.setSize({ width: chartWidth(), height: 170 });
});

fetchStatus();
fetchLogs();
setInterval(fetchStatus, 5000);
setInterval(fetchLogs, 30000);
