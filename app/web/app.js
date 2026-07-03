const KEY = "healing_agent_sessions_v1";
const DEV_KEY = "healing_agent_dev_mode_v1";
const $ = (id) => document.getElementById(id);

let sessions = JSON.parse(localStorage.getItem(KEY) || "[]");
let activeId = sessions[0]?.session_id || null;
let audioBlob = null;
let audioName = "";
let recorder = null;
let recordChunks = [];
let recordStartedAt = 0;
let micStream = null;

const fileInput = document.createElement("input");
fileInput.type = "file";
fileInput.accept = "audio/*";
fileInput.style.display = "none";
document.body.appendChild(fileInput);

function save() {
  localStorage.setItem(KEY, JSON.stringify(sessions));
}

function current() {
  return sessions.find((s) => s.session_id === activeId) || null;
}

function shortTitle(text) {
  const clean = (text || "新建对话").trim().replace(/\s+/g, " ");
  return clean.length > 18 ? clean.slice(0, 18) + "..." : clean;
}

async function makeId(text) {
  const raw = `${text}|${Date.now()}|${Math.random()}`;
  const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(raw));
  return Array.from(new Uint8Array(buf)).map((b) => b.toString(16).padStart(2, "0")).join("").slice(0, 24);
}

async function ensureSession(text) {
  if (current()) return current();
  const session = {
    session_id: await makeId(text || "语音对话"),
    title: shortTitle(text || "语音对话"),
    created_at: new Date().toISOString(),
    messages: [],
    metrics: [],
    lastTrace: null,
  };
  sessions.unshift(session);
  activeId = session.session_id;
  save();
  render();
  return session;
}

function render() {
  renderList();
  renderHeader();
  renderMessages();
  renderAudio();
  renderDevPanel();
}

function renderList() {
  const box = $("sessionList");
  box.innerHTML = "";
  if (!sessions.length) {
    box.innerHTML = '<div class="session-meta">暂无历史会话</div>';
    return;
  }
  for (const s of sessions) {
    const btn = document.createElement("button");
    btn.className = "session-item" + (s.session_id === activeId ? " active" : "");
    btn.innerHTML = '<div class="session-title"></div><div class="session-meta"></div>';
    btn.querySelector(".session-title").textContent = s.title;
    btn.querySelector(".session-meta").textContent = "id: " + s.session_id;
    btn.onclick = () => {
      activeId = s.session_id;
      audioBlob = null;
      audioName = "";
      render();
    };
    box.appendChild(btn);
  }
}

function renderHeader() {
  const s = current();
  $("chatTitle").textContent = s ? s.title : "新建对话";
  $("chatSubtitle").textContent = s ? "session_id: " + s.session_id : "输入第一句话后会自动生成会话标题和 session_id";
  $("deleteSessionBtn").disabled = !s;
}

function renderMessages() {
  const box = $("messages");
  const s = current();
  box.innerHTML = "";
  if (!s || !s.messages.length) {
    box.innerHTML = '<div class="empty-state"><div class="empty-icon">💬</div><h3>开始一次新的对话</h3><p>可以只输入文本，也可以先录音、试听后，再补充文本并发送。</p></div>';
    return;
  }
  for (const m of s.messages) {
    const div = document.createElement("div");
    div.className = "message " + m.role;
    div.textContent = m.text;
    if (m.meta) {
      const meta = document.createElement("div");
      meta.className = "meta-line";
      meta.textContent = m.meta;
      div.appendChild(meta);
    }
    box.appendChild(div);
  }
  box.scrollTop = box.scrollHeight;
}

function showTyping() {
  const box = $("messages");
  const div = document.createElement("div");
  div.id = "typingIndicator";
  div.className = "message typing";
  div.innerHTML = '<span>对方正在输入</span><span class="typing-dots"></span>';
  box.appendChild(div);
  box.scrollTop = box.scrollHeight;
}

function hideTyping() {
  const node = $("typingIndicator");
  if (node) node.remove();
}

function renderAudio() {
  const draft = $("audioDraft");
  const preview = $("audioPreview");
  if (!audioBlob) {
    draft.classList.add("hidden");
    preview.removeAttribute("src");
    return;
  }
  draft.classList.remove("hidden");
  preview.src = URL.createObjectURL(audioBlob);
  $("audioStatus").textContent = "已暂存语音";
  $("audioMeta").textContent = `${audioName || "audio"}，${Math.round(audioBlob.size / 1024)} KB`;
}

function addMessage(session, role, text, meta = "") {
  session.messages.push({ role, text, meta, time: new Date().toISOString() });
  save();
  render();
}

async function uploadAudio(sessionId) {
  if (!audioBlob) return null;
  const form = new FormData();
  form.append("session_id", sessionId);
  form.append("file", audioBlob, audioName || "audio.webm");
  const resp = await fetch("/audio/upload", { method: "POST", body: form });
  if (!resp.ok) throw new Error(await resp.text());
  return (await resp.json()).audio_path;
}

function riskToValue(level) {
  const key = String(level || "").toLowerCase();
  if (key === "high") return 3;
  if (key === "medium") return 2;
  if (key === "low") return 1;
  return 0;
}

function buildTrace(data, audioPath) {
  return {
    provider: data.model_provider || "-",
    model: data.model_name || "-",
    input: audioPath ? "文本 + 语音" : "文本",
    scoring: audioPath ? "scoring_step：V2 多模态评分（文本语义 + 音频特征）" : "scoring_step：V1 文本评分",
    memory: "memory_step：会话历史 + EMA 平滑",
    risk: "risk_assessment_step：规则信号 + 趋势信号 + 综合等级",
    safety: `safety_policy_step：${data.safety_mode || "默认安全策略"}`,
    reply: "reply_step：带安全约束的 LLM 回复",
    note: "展示的是可观测执行链路，不展示模型私有推理。",
  };
}

function addMetric(session, data, audioPath) {
  if (!session.metrics) session.metrics = [];
  session.metrics.push({
    t: new Date().toLocaleTimeString(),
    score: Number(data.score || 0),
    riskLevel: data.risk_level || "unknown",
    riskValue: riskToValue(data.risk_level),
    model: data.model_name || "-",
    provider: data.model_provider || "-",
    audio: Boolean(audioPath),
  });
  session.lastTrace = buildTrace(data, audioPath);
  save();
}

function renderDevPanel() {
  const shell = $("shell");
  const enabled = localStorage.getItem(DEV_KEY) === "1";
  shell.classList.toggle("dev-on", enabled);
  const btn = $("toggleDevBtn");
  if (btn) btn.textContent = enabled ? "关闭开发者模式" : "开发者模式";

  const s = current();
  const trace = $("devTrace");
  if (!trace) return;
  if (!s || !s.lastTrace) {
    trace.textContent = "暂无请求";
  } else {
    trace.innerHTML = Object.entries(s.lastTrace).map(([k, v]) => `<div class="trace-row"><div class="trace-key">${k}</div><div class="trace-value">${v}</div></div>`).join("");
  }
  drawChart("scoreCanvas", s?.metrics || [], "score");
  drawChart("riskCanvas", s?.metrics || [], "riskValue");
}

function drawChart(canvasId, points, key) {
  const canvas = $(canvasId);
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  const w = canvas.width;
  const h = canvas.height;
  ctx.clearRect(0, 0, w, h);
  ctx.fillStyle = "#fffaf7";
  ctx.fillRect(0, 0, w, h);
  ctx.strokeStyle = "#eadfd2";
  ctx.lineWidth = 1;
  for (let i = 1; i <= 3; i++) {
    const y = (h / 4) * i;
    ctx.beginPath(); ctx.moveTo(10, y); ctx.lineTo(w - 10, y); ctx.stroke();
  }
  if (!points.length) {
    ctx.fillStyle = "#7b7167";
    ctx.font = "13px sans-serif";
    ctx.fillText("暂无数据", 20, 80);
    return;
  }
  const values = points.map((p) => Number(p[key] || 0));
  const max = key === "riskValue" ? 3 : Math.max(30, ...values);
  const min = 0;
  const xStep = points.length > 1 ? (w - 40) / (points.length - 1) : 0;
  ctx.strokeStyle = "#8c5f3f";
  ctx.lineWidth = 2;
  ctx.beginPath();
  values.forEach((v, i) => {
    const x = 20 + i * xStep;
    const y = h - 20 - ((v - min) / (max - min || 1)) * (h - 40);
    if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
  });
  ctx.stroke();
  ctx.fillStyle = "#8c5f3f";
  values.forEach((v, i) => {
    const x = 20 + i * xStep;
    const y = h - 20 - ((v - min) / (max - min || 1)) * (h - 40);
    ctx.beginPath(); ctx.arc(x, y, 3, 0, Math.PI * 2); ctx.fill();
  });
}

async function sendMessage() {
  const input = $("textInput");
  const text = input.value.trim();
  if (!text && !audioBlob) {
    alert("请输入文本，或先录制/选择一段语音。");
    return;
  }

  $("sendBtn").disabled = true;
  $("recordBtn").disabled = true;
  try {
    const session = await ensureSession(text || "语音对话");
    const audioPath = await uploadAudio(session.session_id);
    addMessage(session, "user", text || "[语音输入]", audioPath ? "已附带语音" : "");
    showTyping();

    input.value = "";
    audioBlob = null;
    audioName = "";
    renderAudio();

    const payload = {
      user_text: text || "请根据我的语音内容进行回应。",
      session_id: session.session_id,
    };
    if (audioPath) payload.audio_path = audioPath;

    const resp = await fetch("/chat/message", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!resp.ok) throw new Error(await resp.text());
    const data = await resp.json();
    hideTyping();
    addMetric(session, data, audioPath);
    addMessage(session, "agent", data.reply);
  } catch (err) {
    hideTyping();
    const session = current();
    if (session) addMessage(session, "system", "请求失败：" + (err.message || err));
    else alert(err.message || err);
  } finally {
    $("sendBtn").disabled = false;
    $("recordBtn").disabled = false;
  }
}

function preferredMimeType() {
  const candidates = ["audio/webm;codecs=opus", "audio/webm", "audio/ogg;codecs=opus", "audio/ogg"];
  return candidates.find((type) => window.MediaRecorder && MediaRecorder.isTypeSupported(type)) || "";
}

async function startRecording() {
  if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
    alert("当前浏览器不支持麦克风录音，将改为选择语音文件。建议使用新版 Chrome 或 Edge。 ");
    fileInput.click();
    return;
  }

  micStream = await navigator.mediaDevices.getUserMedia({ audio: true });
  recordChunks = [];
  const mimeType = preferredMimeType();
  recorder = mimeType ? new MediaRecorder(micStream, { mimeType }) : new MediaRecorder(micStream);
  recordStartedAt = Date.now();

  recorder.ondataavailable = (event) => {
    if (event.data && event.data.size > 0) recordChunks.push(event.data);
  };

  recorder.onstop = () => {
    if (micStream) {
      micStream.getTracks().forEach((track) => track.stop());
      micStream = null;
    }
    const type = recorder.mimeType || "audio/webm";
    audioBlob = new Blob(recordChunks, { type });
    const suffix = type.includes("ogg") ? "ogg" : "webm";
    const seconds = Math.max(1, Math.round((Date.now() - recordStartedAt) / 1000));
    audioName = `recording-${Date.now()}.${suffix}`;
    $("recordBtn").classList.remove("recording");
    $("recordBtn").textContent = "🎙 录音";
    $("audioStatus").textContent = `已暂存语音 ${seconds}s`;
    renderAudio();
  };

  recorder.start();
  $("recordBtn").classList.add("recording");
  $("recordBtn").textContent = "■ 停止";
}

function stopRecording() {
  if (recorder && recorder.state === "recording") recorder.stop();
}

async function toggleRecording() {
  try {
    if (recorder && recorder.state === "recording") stopRecording();
    else await startRecording();
  } catch (err) {
    alert("无法启动麦克风：" + (err.message || err));
    if (micStream) micStream.getTracks().forEach((track) => track.stop());
    $("recordBtn").classList.remove("recording");
    $("recordBtn").textContent = "🎙 录音";
  }
}

$("newSessionBtn").onclick = () => {
  activeId = null;
  audioBlob = null;
  audioName = "";
  render();
  $("textInput").focus();
};

$("deleteSessionBtn").onclick = () => {
  if (!activeId || !confirm("删除当前对话？这只会删除浏览器本地记录。")) return;
  sessions = sessions.filter((s) => s.session_id !== activeId);
  activeId = sessions[0]?.session_id || null;
  save();
  render();
};

$("toggleDevBtn").onclick = () => {
  const next = localStorage.getItem(DEV_KEY) === "1" ? "0" : "1";
  localStorage.setItem(DEV_KEY, next);
  renderDevPanel();
};

$("recordBtn").onclick = toggleRecording;
fileInput.onchange = () => {
  const file = fileInput.files[0];
  if (!file) return;
  audioBlob = file;
  audioName = file.name;
  renderAudio();
  fileInput.value = "";
};

$("clearAudioBtn").onclick = () => {
  audioBlob = null;
  audioName = "";
  renderAudio();
};

$("sendBtn").onclick = sendMessage;
$("textInput").addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    sendMessage();
  }
});

render();
