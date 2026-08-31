const API_BASE = window.location.origin;
let volumeChart, scoreChart, latencyChart, metricsChart;

function fmtPct(x) {
  return `${Math.round((x || 0) * 100)}%`;
}

async function loadStats() {
  const res = await fetch(`${API_BASE}/api/admin/stats`);
  if (!res.ok) throw new Error("Failed to load stats");
  return res.json();
}

function renderStatCards(stats) {
  document.getElementById("statTotalQueries").textContent = stats.total_queries;
  document.getElementById("statTotalSessions").textContent = stats.total_sessions;
  document.getElementById("statTotalDocs").textContent = stats.total_documents;
  document.getElementById("statOverallScore").textContent = fmtPct(stats.averages.overall_score);
  document.getElementById("statLatency").textContent = `${Math.round(stats.averages.latency_ms)} ms`;
  document.getElementById("statHallucination").textContent = fmtPct(stats.averages.hallucination_risk);
}

function renderCharts(stats) {
  const labels = stats.daily_series.map(d => d.date);
  const counts = stats.daily_series.map(d => d.count);
  const scores = stats.daily_series.map(d => d.avg_overall_score);
  const latencies = stats.daily_series.map(d => d.avg_latency_ms);

  const baseOpts = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: { legend: { display: false } },
    scales: { x: { ticks: { font: { size: 10 } } }, y: { beginAtZero: true } },
  };

  volumeChart?.destroy();
  volumeChart = new Chart(document.getElementById("volumeChart"), {
    type: "bar",
    data: { labels, datasets: [{ label: "Queries", data: counts, backgroundColor: "#1AA88A" }] },
    options: baseOpts,
  });

  scoreChart?.destroy();
  scoreChart = new Chart(document.getElementById("scoreChart"), {
    type: "line",
    data: { labels, datasets: [{ label: "Overall score", data: scores, borderColor: "#0F6E5B", backgroundColor: "rgba(15,110,91,0.15)", fill: true, tension: 0.3 }] },
    options: { ...baseOpts, scales: { x: baseOpts.scales.x, y: { beginAtZero: true, max: 1 } } },
  });

  latencyChart?.destroy();
  latencyChart = new Chart(document.getElementById("latencyChart"), {
    type: "line",
    data: { labels, datasets: [{ label: "Latency (ms)", data: latencies, borderColor: "#1596C8", backgroundColor: "rgba(21,150,200,0.15)", fill: true, tension: 0.3 }] },
    options: baseOpts,
  });

  metricsChart?.destroy();
  metricsChart = new Chart(document.getElementById("metricsChart"), {
    type: "radar",
    data: {
      labels: ["Faithfulness", "Relevance", "Context Relevance", "1 - Hallucination Risk"],
      datasets: [{
        label: "Average",
        data: [
          stats.averages.faithfulness,
          stats.averages.relevance,
          stats.averages.context_relevance,
          1 - stats.averages.hallucination_risk,
        ],
        backgroundColor: "rgba(26,168,138,0.25)",
        borderColor: "#1AA88A",
      }],
    },
    options: { responsive: true, maintainAspectRatio: false, scales: { r: { min: 0, max: 1 } } },
  });
}

function renderRecentTable(stats) {
  const tbody = document.querySelector("#recentTable tbody");
  tbody.innerHTML = "";
  for (const r of stats.recent_queries) {
    const tr = document.createElement("tr");
    const time = new Date(r.created_at * 1000).toLocaleString();
    tr.innerHTML = `
      <td class="truncate" title="${escapeHtml(r.query)}">${escapeHtml(r.query)}</td>
      <td>${fmtPct(r.overall_score)}</td>
      <td>${fmtPct(r.hallucination_risk)}</td>
      <td>${Math.round(r.latency_ms)} ms</td>
      <td>${time}</td>
    `;
    tbody.appendChild(tr);
  }
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str || "";
  return div.innerHTML;
}

async function loadDocuments() {
  const res = await fetch(`${API_BASE}/api/documents`);
  const docs = await res.json();
  const tbody = document.querySelector("#docsTable tbody");
  tbody.innerHTML = "";
  for (const d of docs) {
    const tr = document.createElement("tr");
    const time = new Date(d.uploaded_at * 1000).toLocaleDateString();
    tr.innerHTML = `
      <td class="truncate" title="${escapeHtml(d.title)}">${escapeHtml(d.title)}</td>
      <td>${d.chunk_count}</td>
      <td>${time}</td>
      <td><button class="delete-btn" data-id="${d.id}">Delete</button></td>
    `;
    tbody.appendChild(tr);
  }
  tbody.querySelectorAll(".delete-btn").forEach(btn => {
    btn.addEventListener("click", async () => {
      await fetch(`${API_BASE}/api/documents/${btn.dataset.id}`, { method: "DELETE" });
      loadDocuments();
    });
  });
}

document.getElementById("uploadForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const fileInput = document.getElementById("docFile");
  const titleInput = document.getElementById("docTitle");
  const statusEl = document.getElementById("uploadStatus");

  if (!fileInput.files.length) return;

  const formData = new FormData();
  formData.append("file", fileInput.files[0]);
  if (titleInput.value.trim()) formData.append("title", titleInput.value.trim());

  statusEl.textContent = "Uploading and embedding document…";
  try {
    const res = await fetch(`${API_BASE}/api/documents`, { method: "POST", body: formData });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "Upload failed");
    }
    const data = await res.json();
    statusEl.textContent = `✅ "${data.title}" ingested: ${data.embedded_chunks}/${data.chunk_count} chunks embedded.`;
    fileInput.value = "";
    titleInput.value = "";
    loadDocuments();
  } catch (err) {
    statusEl.textContent = `⚠️ ${err.message}`;
  }
});

async function refreshAll() {
  try {
    const stats = await loadStats();
    renderStatCards(stats);
    renderCharts(stats);
    renderRecentTable(stats);
  } catch (e) {
    console.error(e);
  }
  loadDocuments();
}

refreshAll();
setInterval(refreshAll, 20000);
