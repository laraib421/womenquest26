const $ = (id) => document.getElementById(id);
let currentBillId = null;
let historyChart = null;

function toast(msg) {
  const t = document.createElement("div");
  t.className = "toast";
  t.textContent = msg;
  $("toasts").appendChild(t);
  setTimeout(() => t.remove(), 5000);
}

function fmt(v) {
  if (v === null || v === undefined) return '<span class="na">— n/a</span>';
  if (typeof v === "number") return v.toLocaleString(undefined, { maximumFractionDigits: 2 });
  return v;
}
function money(v) {
  if (v === null || v === undefined) return "—";
  const n = Number(v);
  return (n < 0 ? "-Rs " : "Rs ") + Math.abs(n).toLocaleString(undefined, { maximumFractionDigits: 2 });
}

function fillTable(tableId, lines, emptyMsg) {
  const tbody = document.querySelector(`#${tableId} tbody`);
  tbody.innerHTML = "";
  if (!lines.length) {
    tbody.innerHTML = `<tr class="empty-row"><td colspan="2">${emptyMsg}</td></tr>`;
    return;
  }
  lines.forEach((l) => {
    const tr = document.createElement("tr");
    const typeLabel = l.type.replace(/_/g, " ");
    tr.innerHTML = `<td>${typeLabel}</td><td>${money(l.amount)}</td>`;
    tbody.appendChild(tr);
  });
}

function field(label, value) {
  const d = document.createElement("div");
  d.className = "field";
  d.innerHTML = `<small>${label}</small><b${value == null ? ' class="na"' : ""}>${fmt(value)}</b>`;
  return d;
}

const STAT_LABELS = {
  taxes_pct_of_current_bill: ["Taxes % of bill", (v) => v + "%"],
  charges_pct_of_current_bill: ["Charges % of bill", (v) => v + "%"],
  avg_cost_per_unit_pkr: ["Avg cost / unit", (v) => "Rs " + v],
  late_payment_surcharge_pkr: ["Late payment surcharge", (v) => money(v)],
  usage_history_avg: ["Avg monthly units", (v) => v],
  change_vs_previous_month_pct: ["Change vs last month", (v) => (v > 0 ? "+" : "") + v + "%"],
};

function renderStats(stats) {
  const row = $("statRow");
  row.innerHTML = "";
  Object.entries(STAT_LABELS).forEach(([key, [label, format]]) => {
    if (stats[key] === undefined || stats[key] === null) return;
    const d = document.createElement("div");
    d.className = "stat-tile";
    d.innerHTML = `<small>${label}</small><b>${format(stats[key])}</b>`;
    row.appendChild(d);
  });
}

function renderChart(history) {
  const box = $("chartBox");
  if (!history || !history.length) {
    box.classList.add("hidden");
    return;
  }
  box.classList.remove("hidden");
  if (historyChart) historyChart.destroy();
  const labels = history.map((h) => h.month);
  const values = history.map((h) => h.units);
  const current = values[values.length - 1];
  historyChart = new Chart($("historyChart"), {
    type: "bar",
    data: {
      labels,
      datasets: [{
        data: values,
        backgroundColor: values.map((v, i) => (i === values.length - 1 ? "#f5b942" : "#2dd4a7aa")),
        borderRadius: 4,
      }],
    },
    options: {
      responsive: true,
      plugins: { legend: { display: false } },
      scales: {
        x: { ticks: { color: "#8ba296", font: { size: 10 } }, grid: { display: false } },
        y: { ticks: { color: "#8ba296" }, grid: { color: "#1c2622" } },
      },
    },
  });
}

function renderBill(data) {
  const j = data.json;
  $("providerBadge").textContent = j.provider || "—";
  $("tariffBadge").textContent = j.tariff ? "Tariff " + j.tariff : "";
  const grid = $("headGrid");
  grid.innerHTML = "";
  [
    ["Provider", j.provider], ["Tariff", j.tariff], ["Sanctioned load (kW)", j.sanctioned_load_kw],
    ["Bill month", j.bill_month], ["Reading date", j.reading_date], ["Issue date", j.issue_date],
    ["Due date", j.due_date], ["Previous reading", j.previous_reading], ["Current reading", j.current_reading],
    ["Units consumed", j.units_consumed],
  ].forEach(([label, val]) => grid.appendChild(field(label, val)));

  const row = $("amountRow");
  row.innerHTML = "";
  const amounts = [
    ["Current bill", j.current_bill, false], ["Arrears", j.arrears, j.arrears > 0],
    ["Payable within due date", j.payable_within_due_date, false],
    ["Payable after due date", j.payable_after_due_date, true],
  ];
  amounts.forEach(([label, val, warn]) => {
    const d = document.createElement("div");
    d.className = "amount-item" + (warn ? " warn" : "");
    d.innerHTML = `<small>${label}</small><b>${val == null ? "n/a" : money(val)}</b>`;
    row.appendChild(d);
  });

  fillTable("chargesTable", j.charges, "No itemized charges printed");
  fillTable("taxesTable", j.taxes, `Combined total: ${j.total_taxes != null ? money(j.total_taxes) : "n/a"}`);
  renderStats(data.stats || {});
  renderChart(data.usage_history || []);

  if (data.notes) {
    $("noteBox").textContent = "Note: " + data.notes;
    $("noteBox").classList.remove("hidden");
  } else {
    $("noteBox").classList.add("hidden");
  }

  const suggestions = ["How much of my bill is taxes?", "What is my average cost per unit?"];
  if (data.stats?.months_above_200_units) suggestions.push("How many months went above 200 units?");
  suggestions.push("Is there anything unusual about this bill?");
  $("qaChips").innerHTML = "";
  suggestions.forEach((q) => {
    const c = document.createElement("button");
    c.className = "chip";
    c.type = "button";
    c.textContent = q;
    c.onclick = () => askQuestion(q);
    $("qaChips").appendChild(c);
  });
  $("qaLog").innerHTML = "";
  $("qaPanel").classList.remove("hidden");
}

function enterLoadingState(imgSrc) {
  $("billImg").src = imgSrc;
  $("workspace").classList.remove("hidden");
  $("uploadPanel").classList.add("hidden");
  $("loadingPanel").classList.remove("hidden");
  $("dataPanel").classList.add("hidden");
  $("qaPanel").classList.add("hidden");
}

async function finishLoading(reqPromise) {
  try {
    const res = await reqPromise;
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail || "Request failed (" + res.status + ")");
    }
    const data = await res.json();
    currentBillId = data.bill_id;
    renderBill(data);
    $("loadingPanel").classList.add("hidden");
    $("dataPanel").classList.remove("hidden");
  } catch (e) {
    toast(e.message);
    $("loadingPanel").classList.add("hidden");
    resetUpload();
  }
}

async function uploadFile(file) {
  enterLoadingState(URL.createObjectURL(file));
  const fd = new FormData();
  fd.append("file", file);
  await finishLoading(fetch("/api/upload", { method: "POST", body: fd }));
}

async function loadSample(name) {
  enterLoadingState(`/api/samples/${name}`);
  await finishLoading(fetch(`/api/samples/${name}/load`, { method: "POST" }));
}

async function initSamples() {
  try {
    const names = await fetch("/api/samples").then((r) => r.json());
    const box = $("sampleList");
    box.innerHTML = "";
    if (!names.length) { $("samplesBox").classList.add("hidden"); return; }
    names.forEach((name) => {
      const provider = name.split("_")[0];
      const b = document.createElement("button");
      b.className = "sample-chip";
      b.type = "button";
      b.innerHTML = `<span class="dot"></span>${provider} sample`;
      b.onclick = () => loadSample(name);
      box.appendChild(b);
    });
  } catch {
    $("samplesBox").classList.add("hidden");
  }
}
initSamples();

async function askQuestion(question) {
  const log = $("qaLog");
  const box = document.createElement("div");
  box.className = "qa-item";
  const qEl = document.createElement("div");
  qEl.className = "q";
  qEl.textContent = question;
  const aEl = document.createElement("div");
  aEl.className = "a";
  aEl.innerHTML = '<span class="typing"><span></span><span></span><span></span></span>';
  box.append(qEl, aEl);
  log.prepend(box);

  try {
    const res = await fetch("/api/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ bill_id: currentBillId, question }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Could not get an answer.");
    aEl.textContent = data.answer || "No answer.";
  } catch (e) {
    aEl.textContent = "Something went wrong.";
    toast(e.message);
  }
}

$("askForm").addEventListener("submit", (e) => {
  e.preventDefault();
  const v = $("askInput").value.trim();
  if (!v) return;
  $("askInput").value = "";
  askQuestion(v);
});

$("fileInput").addEventListener("change", (e) => {
  if (e.target.files[0]) uploadFile(e.target.files[0]);
});

const drop = $("drop");
["dragenter", "dragover"].forEach((ev) => drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.add("over"); }));
["dragleave", "drop"].forEach((ev) => drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.remove("over"); }));
drop.addEventListener("drop", (e) => {
  const f = e.dataTransfer.files[0];
  if (f) uploadFile(f);
});

function resetUpload() {
  $("workspace").classList.add("hidden");
  $("uploadPanel").classList.remove("hidden");
  $("fileInput").value = "";
  currentBillId = null;
  if (historyChart) { historyChart.destroy(); historyChart = null; }
}
$("resetBtn").addEventListener("click", resetUpload);
