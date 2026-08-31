const API_BASE = window.location.origin; // same-origin, since FastAPI serves the frontend too

const chatWindow = document.getElementById("chatWindow");
const chatForm = document.getElementById("chatForm");
const chatInput = document.getElementById("chatInput");
const sendBtn = document.getElementById("sendBtn");
const typingIndicator = document.getElementById("typingIndicator");
const statusDot = document.getElementById("statusDot");
const statusText = document.getElementById("statusText");
const newChatBtn = document.getElementById("newChatBtn");
const streamToggle = document.getElementById("streamToggle");

let sessionId = localStorage.getItem("mediaegis_session_id") || null;

function scrollToBottom() {
  chatWindow.scrollTop = chatWindow.scrollHeight;
}

function addUserMessage(text) {
  const el = document.createElement("div");
  el.className = "msg user";
  el.innerHTML = `
    <div class="avatar">🧑</div>
    <div class="bubble"></div>
  `;
  el.querySelector(".bubble").textContent = text;
  chatWindow.appendChild(el);
  scrollToBottom();
}

function riskChipClass(risk) {
  if (risk === "critical" || risk === "blocked") return "risk-critical";
  if (risk === "elevated") return "risk-elevated";
  return "risk-low";
}

function addAssistantMessage(data) {
  const el = document.createElement("div");
  el.className = "msg assistant";

  const sourcesHtml = (data.sources || [])
    .filter(s => s.url)
    .map(s => `<a class="source-link" href="${s.url}" target="_blank" rel="noopener">🔗 ${s.title || s.url} <span style="color:#8aa39c">(quality ${s.quality ?? "-"})</span></a>`)
    .join("");

  const evalChips = data.evaluation ? `
    <span class="chip">Confidence ${Math.round((data.confidence ?? 0) * 100)}%</span>
    <span class="chip">Faithfulness ${data.evaluation.faithfulness ?? "-"}</span>
    <span class="chip">Relevance ${data.evaluation.relevance ?? "-"}</span>
    <span class="chip">Hallucination risk ${data.evaluation.hallucination_risk ?? "-"}</span>
    <span class="chip">Latency ${Math.round(data.evaluation.latency_ms ?? 0)} ms</span>
  ` : "";

  const riskChip = data.risk_level
    ? `<span class="chip ${riskChipClass(data.risk_level)}">Risk: ${data.risk_level}</span>`
    : "";

  el.innerHTML = `
    <div class="avatar assistant-avatar">🩺</div>
    <div class="bubble">
      <div class="answer-text"></div>
      <div class="meta-panel">
        <div class="meta-row">${riskChip}${evalChips}${data.from_cache ? '<span class="chip">⚡ cached</span>' : ""}</div>
        ${sourcesHtml ? `<div class="meta-row" style="flex-direction:column;align-items:flex-start;">${sourcesHtml}</div>` : ""}
        ${data.disclaimers && data.disclaimers.length ? `<div class="disclaimer-line">${data.disclaimers.join(" ")}</div>` : ""}
      </div>
    </div>
  `;
  el.querySelector(".answer-text").textContent = data.answer;
  chatWindow.appendChild(el);
  scrollToBottom();
}

function metaPanelHtml(data) {
  const sourcesHtml = (data.sources || [])
    .filter(s => s.url || s.title)
    .map(s => s.url
      ? `<a class="source-link" href="${s.url}" target="_blank" rel="noopener">🔗 ${s.title || s.url} <span style="color:#8aa39c">(quality ${s.quality ?? "-"})</span></a>`
      : `<span class="source-link">${s.title} <span style="color:#8aa39c">(quality ${s.quality ?? "-"})</span></span>`)
    .join("");

  const evalChips = data.evaluation ? `
    <span class="chip">Confidence ${Math.round((data.confidence ?? 0) * 100)}%</span>
    <span class="chip">Faithfulness ${data.evaluation.faithfulness ?? "-"}</span>
    <span class="chip">Relevance ${data.evaluation.relevance ?? "-"}</span>
    <span class="chip">Hallucination risk ${data.evaluation.hallucination_risk ?? "-"}</span>
    <span class="chip">Latency ${Math.round(data.evaluation.latency_ms ?? 0)} ms</span>
  ` : `<span class="chip">Confidence ${Math.round((data.confidence ?? 0) * 100)}%</span>`;

  const riskChip = data.risk_level
    ? `<span class="chip ${riskChipClass(data.risk_level)}">Risk: ${data.risk_level}</span>`
    : "";

  return `
    <div class="meta-row">${riskChip}${evalChips}${data.from_cache ? '<span class="chip">⚡ cached</span>' : ""}</div>
    ${sourcesHtml ? `<div class="meta-row" style="flex-direction:column;align-items:flex-start;">${sourcesHtml}</div>` : ""}
    ${data.disclaimers && data.disclaimers.length ? `<div class="disclaimer-line">${data.disclaimers.join(" ")}</div>` : ""}
  `;
}

function createLiveAssistantBubble() {
  const el = document.createElement("div");
  el.className = "msg assistant";
  el.innerHTML = `
    <div class="avatar assistant-avatar">🩺</div>
    <div class="bubble">
      <div class="answer-text"></div>
      <div class="meta-panel"></div>
    </div>
  `;
  chatWindow.appendChild(el);
  scrollToBottom();
  return {
    el,
    answerTextEl: el.querySelector(".answer-text"),
    metaPanelEl: el.querySelector(".meta-panel"),
  };
}

async function sendMessageStreaming(query) {
  sendBtn.disabled = true;
  const { answerTextEl, metaPanelEl } = createLiveAssistantBubble();
  metaPanelEl.innerHTML = `<span class="chip">⏳ thinking…</span>`;

  try {
    const res = await fetch(`${API_BASE}/api/chat/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query, session_id: sessionId }),
    });

    if (!res.ok || !res.body) {
      const errBody = await res.json().catch(() => ({}));
      throw new Error(errBody.detail || `Request failed (${res.status})`);
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let answerText = "";

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      const events = buffer.split("\n\n");
      buffer = events.pop(); // last piece may be incomplete

      for (const raw of events) {
        if (!raw.trim()) continue;
        const eventMatch = raw.match(/^event: (.+)$/m);
        const dataMatch = raw.match(/^data: (.+)$/m);
        if (!eventMatch || !dataMatch) continue;

        const eventType = eventMatch[1].trim();
        const data = JSON.parse(dataMatch[1]);

        if (eventType === "meta") {
          metaPanelEl.innerHTML = `<div class="meta-row"><span class="chip ${riskChipClass(data.risk_level)}">Risk: ${data.risk_level}</span><span class="chip">Confidence ${Math.round((data.confidence ?? 0) * 100)}%</span></div>`;
        } else if (eventType === "token") {
          answerText += data.text;
          answerTextEl.textContent = answerText;
          scrollToBottom();
        } else if (eventType === "final") {
          sessionId = data.session_id;
          localStorage.setItem("mediaegis_session_id", sessionId);
          answerTextEl.textContent = data.answer;
          metaPanelEl.innerHTML = metaPanelHtml(data);
        } else if (eventType === "short_circuit") {
          sessionId = data.session_id;
          localStorage.setItem("mediaegis_session_id", sessionId);
          answerTextEl.textContent = data.answer;
          metaPanelEl.innerHTML = metaPanelHtml(data);
        } else if (eventType === "error") {
          answerTextEl.textContent = `Sorry, something went wrong: ${data.detail}`;
          metaPanelEl.innerHTML = "";
        }
      }
    }
  } catch (e) {
    metaPanelEl.innerHTML = "";
    answerTextEl.textContent = `Sorry, something went wrong: ${e.message}`;
  } finally {
    sendBtn.disabled = false;
  }
}

function addErrorMessage(text) {
  const el = document.createElement("div");
  el.className = "msg assistant";
  el.innerHTML = `<div class="avatar assistant-avatar">⚠️</div><div class="bubble"></div>`;
  el.querySelector(".bubble").textContent = text;
  chatWindow.appendChild(el);
  scrollToBottom();
}

async function checkHealth() {
  try {
    const res = await fetch(`${API_BASE}/api/health`);
    if (!res.ok) throw new Error("bad status");
    const data = await res.json();
    statusDot.classList.add("online");
    statusDot.classList.remove("offline");
    statusText.textContent = `Backend online · ${data.model}`;
  } catch (e) {
    statusDot.classList.add("offline");
    statusDot.classList.remove("online");
    statusText.textContent = "Backend offline — start the FastAPI server";
  }
}

async function sendMessage(query) {
  sendBtn.disabled = true;
  typingIndicator.classList.remove("hidden");
  scrollToBottom();

  try {
    const res = await fetch(`${API_BASE}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query, session_id: sessionId }),
    });

    if (!res.ok) {
      const errBody = await res.json().catch(() => ({}));
      throw new Error(errBody.detail || `Request failed (${res.status})`);
    }

    const data = await res.json();
    sessionId = data.session_id;
    localStorage.setItem("mediaegis_session_id", sessionId);
    addAssistantMessage(data);
  } catch (e) {
    addErrorMessage(`Sorry, something went wrong: ${e.message}`);
  } finally {
    typingIndicator.classList.add("hidden");
    sendBtn.disabled = false;
  }
}

chatForm.addEventListener("submit", (e) => {
  e.preventDefault();
  const text = chatInput.value.trim();
  if (!text) return;
  addUserMessage(text);
  chatInput.value = "";
  if (streamToggle.checked) {
    sendMessageStreaming(text);
  } else {
    sendMessage(text);
  }
});

newChatBtn.addEventListener("click", () => {
  sessionId = null;
  localStorage.removeItem("mediaegis_session_id");
  chatWindow.innerHTML = `
    <div class="msg assistant">
      <div class="avatar assistant-avatar">🩺</div>
      <div class="bubble">New session started. How can I help you today?</div>
    </div>`;
});

checkHealth();
setInterval(checkHealth, 15000);
