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
let pendingProfile = null;
let profileSetupDone = Boolean(activeId);
let quoteDraft = null;

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
    agentProfile: pendingProfile || null,
    profileSkipped: !pendingProfile,
  };
  sessions.unshift(session);
  activeId = session.session_id;
  pendingProfile = null;
  profileSetupDone = true;
  save();
  render();
  return session;
}

function getProfileFromForm() {
  return {
    agent_name: $("profileAgentName").value.trim().slice(0, 40),
    user_name: $("profileUserName").value.trim().slice(0, 40),
    tone_style: $("profileTone").value.trim().slice(0, 40),
    persona_role: $("profileRole").value.trim().slice(0, 80),
    custom_settings: $("profileCustom").value.trim().slice(0, 500),
  };
}

function showProfileModal() {
  const modal = $("profileModal");
  if (!modal) return;
  modal.classList.remove("hidden");
  $("profileCustom").value = "";
  $("profileAgentName").focus();
}

function hideProfileModal() {
  const modal = $("profileModal");
  if (modal) modal.classList.add("hidden");
}

function saveProfileFromModal() {
  pendingProfile = getProfileFromForm();
  profileSetupDone = true;
  hideProfileModal();
}

function skipProfileSetup() {
  pendingProfile = null;
  profileSetupDone = true;
  hideProfileModal();
}

function render() {
  renderList();
  renderHeader();
  renderMessages();
  renderAudio();
  renderQuoteDraft();
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
      quoteDraft = null;
      profileSetupDone = true;
      pendingProfile = null;
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
  if ($("exportTxtBtn")) $("exportTxtBtn").disabled = !s;
  if ($("exportCsvBtn")) $("exportCsvBtn").disabled = !s;
}

function roleLabel(role) {
  if (role === "user") return "用户";
  if (role === "agent") return "Agent";
  if (role === "system") return "系统";
  return role || "消息";
}

function clipText(text, max = 280) {
  const clean = String(text || "").trim();
  return clean.length > max ? clean.slice(0, max) + "..." : clean;
}

function getSelectedTextInside(node) {
  const selection = window.getSelection?.();
  if (!selection || selection.isCollapsed) return "";
  const text = selection.toString().trim();
  if (!text) return "";
  const anchor = selection.anchorNode;
  const focus = selection.focusNode;
  if ((anchor && node.contains(anchor)) || (focus && node.contains(focus))) return clipText(text, 500);
  return "";
}

function setQuoteDraft(role, text) {
  const clean = clipText(text, 500);
  if (!clean) return;
  quoteDraft = { role, text: clean, time: new Date().toISOString() };
  renderQuoteDraft();
  const input = $("textInput");
  if (input) input.focus();
}

function renderQuoteDraft() {
  const box = $("quoteDraft");
  if (!box) return;
  if (!quoteDraft) {
    box.classList.add("hidden");
    $("quoteDraftText").textContent = "";
    return;
  }
  box.classList.remove("hidden");
  $("quoteDraftText").textContent = `${roleLabel(quoteDraft.role)}：${quoteDraft.text}`;
}

function renderMessages() {
  const box = $("messages");
  const s = current();
  box.innerHTML = "";
  if (!s || !s.messages.length) {
    box.innerHTML = '<div class="empty-state"><div class="empty-icon">💬</div><h3>开始一次新的对话</h3><p>可以先完成 Agent 初始化设定，也可以跳过后直接开始。</p></div>';
    return;
  }
  s.messages.forEach((m, index) => {
    const div = document.createElement("div");
    div.className = "message " + m.role;
    div.dataset.index = String(index);

    if (m.quote) {
      const quote = document.createElement("div");
      quote.className = "quoted-block";
      const qr = document.createElement("div");
      qr.className = "quoted-role";
      qr.textContent = "引用 " + roleLabel(m.quote.role);
      const qt = document.createElement("div");
      qt.textContent = m.quote.text;
      quote.appendChild(qr);
      quote.appendChild(qt);
      div.appendChild(quote);
    }

    const body = document.createElement("div");
    body.className = "message-body";
    body.textContent = m.text;
    div.appendChild(body);

    if (m.meta) {
      const meta = document.createElement("div");
      meta.className = "meta-line";
      meta.textContent = m.meta;
      div.appendChild(meta);
    }

    if (m.role !== "system") {
      const quoteBtn = document.createElement("button");
      quoteBtn.className = "quote-btn";
      quoteBtn.type = "button";
      quoteBtn.textContent = "引用";
      quoteBtn.title = "引用整条消息；先选中文本再点则只引用选中文本";
      quoteBtn.onclick = (event) => {
        event.stopPropagation();
        const selected = getSelectedTextInside(div);
        setQuoteDraft(m.role, selected || m.text);
      };
      div.appendChild(quoteBtn);
      div.ondblclick = () => setQuoteDraft(m.role, m.text);
    }

    box.appendChild(div);
  });
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

function addMessage(session, role, text, meta = "", quote = null, extra = {}) {
  session.messages.push({ role, text, meta, quote, time: new Date().toISOString(), ...extra });
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
  if (key === "critical") return 4;
  if (key === "high") return 3;
  if (key === "medium") return 2;
  if (key === "low") return 1;
  return 0;
}

function describeProfile(profile) {
  if (!profile) return "未设置或已跳过";
  const parts = [];
  if (profile.agent_name) parts.push(`名称=${profile.agent_name}`);
  if (profile.user_name) parts.push(`称呼=${profile.user_name}`);
  if (profile.tone_style) parts.push(`语气=${profile.tone_style}`);
  if (profile.persona_role) parts.push(`定位=${profile.persona_role}`);
  if (profile.custom_settings) parts.push(`自定义=${profile.custom_settings}`);
  return parts.join("；") || "未设置或已跳过";
}

function buildTrace(data, audioPath, profile) {
  return {
    provider: data.model_provider || "-",
    model: data.model_name || "-",
    input: audioPath ? "文本 + 语音" : "文本",
    profile: describeProfile(profile),
    profileSafety: "人设设定仅影响称呼、语气和陪伴风格；不能覆盖心理支持安全策略。",
    scoring: audioPath ? "scoring_step：V2 多模态评分（文本语义 + 音频特征）" : "scoring_step：V1 文本评分",
    memory: "memory_step：会话历史 + EMA 平滑",
    risk: "risk_assessment_step：规则信号 + 趋势信号 + 综合等级",
    safety: `safety_policy_step：${data.safety_mode || "默认安全策略"}`,
    reply: "reply_step：带安全约束和人设偏好的 LLM 回复",
    note: "展示的是可观测执行链路，不展示模型私有推理。",
  };
}

function addMetric(session, data, audioPath) {
  if (!session.metrics) session.metrics = [];
  const metric = {
    t: new Date().toLocaleTimeString(),
    score: Number(data.score || 0),
    riskLevel: data.risk_level || "unknown",
    riskValue: riskToValue(data.risk_level),
    safetyMode: data.safety_mode || "-",
    model: data.model_name || "-",
    provider: data.model_provider || "-",
    audio: Boolean(audioPath),
  };
  session.metrics.push(metric);
  session.currentMetric = metric;
  session.lastTrace = buildTrace(data, audioPath, session.agentProfile);
  save();
}

function renderDevCurrent(session) {
  const box = $("devCurrent");
  if (!box) return;
  const metric = session?.currentMetric || session?.metrics?.[session.metrics.length - 1];
  if (!metric) {
    box.textContent = "暂无请求";
    return;
  }
  const score = Number.isFinite(metric.score) ? metric.score.toFixed(1) : "-";
  box.innerHTML = `
    <div class="metric-grid">
      <div class="metric-card">
        <div class="metric-label">本轮评分</div>
        <div class="metric-value">${score}</div>
        <div class="metric-sub">score / persistent_score</div>
      </div>
      <div class="metric-card">
        <div class="metric-label">风险等级</div>
        <div class="metric-value">${metric.riskLevel || "-"}</div>
        <div class="metric-sub">mode: ${metric.safetyMode || "-"}</div>
      </div>
    </div>
    <div class="metric-sub" style="margin-top:8px;">${metric.provider || "-"} / ${metric.model || "-"} / ${metric.audio ? "文本+语音" : "文本"} / ${metric.t}</div>
  `;
}

function renderDevPanel() {
  const shell = $("shell");
  const enabled = localStorage.getItem(DEV_KEY) === "1";
  shell.classList.toggle("dev-on", enabled);
  const btn = $("toggleDevBtn");
  if (btn) btn.textContent = enabled ? "关闭开发者模式" : "开发者模式";

  const s = current();
  renderDevCurrent(s);
  const trace = $("devTrace");
  if (!trace) return;
  if (!s || !s.lastTrace) {
    trace.textContent = s?.agentProfile ? `已设置人设：${describeProfile(s.agentProfile)}` : "暂无请求";
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
  for (let i = 1; i <= 4; i++) {
    const y = (h / 5) * i;
    ctx.beginPath(); ctx.moveTo(10, y); ctx.lineTo(w - 10, y); ctx.stroke();
  }
  if (!points.length) {
    ctx.fillStyle = "#7b7167";
    ctx.font = "13px sans-serif";
    ctx.fillText("暂无数据", 20, 80);
    return;
  }
  const values = points.map((p) => Number(p[key] || 0));
  const max = key === "riskValue" ? 4 : Math.max(30, ...values);
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

function buildOutboundText(text, quote) {
  if (!quote) return text || "请根据我的语音内容进行回应。";
  const quoted = `[引用${roleLabel(quote.role)}]\n${quote.text}`;
  const reply = text || "请根据引用内容和我的语音内容进行回应。";
  return `${quoted}\n\n[用户当前输入]\n${reply}`;
}

function messageTextForExport(message) {
  if (!message) return "";
  if (!message.quote) return message.text || "";
  return `[引用${roleLabel(message.quote.role)}]\n${message.quote.text}\n\n[用户当前输入]\n${message.text || ""}`;
}

function buildExportRows(session) {
  if (!session) return [];
  const rows = [];
  const messages = session.messages || [];
  let metricIndex = 0;

  for (let i = 0; i < messages.length; i++) {
    const userMsg = messages[i];
    if (userMsg.role !== "user") continue;

    const agentMsg = messages.slice(i + 1).find((m) => m.role === "agent");
    const metric = (session.metrics || [])[metricIndex] || {};
    metricIndex += 1;

    rows.push({
      user_text: messageTextForExport(userMsg),
      user_audio: userMsg.audioPath || userMsg.audioName || "",
      risk_level: metric.riskLevel || "",
      model_score: Number.isFinite(Number(metric.score)) ? String(Number(metric.score)) : "",
      agent_reply: agentMsg?.text || "",
    });
  }
  return rows;
}

function safeFileName(value) {
  return String(value || "chat")
    .trim()
    .replace(/[\\/:*?"<>|]+/g, "_")
    .replace(/\s+/g, "_")
    .slice(0, 60) || "chat";
}

function downloadTextFile(filename, text, mimeType) {
  const blob = new Blob([text], { type: `${mimeType};charset=utf-8` });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

function csvEscape(value) {
  const text = String(value ?? "");
  return `"${text.replace(/"/g, '""')}"`;
}

function exportCurrentChat(format) {
  const session = current();
  if (!session) {
    alert("当前没有可导出的对话。");
    return;
  }
  const rows = buildExportRows(session);
  if (!rows.length) {
    alert("当前对话还没有完整轮次可导出。");
    return;
  }

  const stamp = new Date().toISOString().slice(0, 19).replace(/[T:]/g, "-");
  const base = `${safeFileName(session.title)}_${session.session_id}_${stamp}`;
  const headers = ["用户输入文本", "用户输入语音", "风险等级预测", "模型评分", "agent回复文本"];

  if (format === "csv") {
    const lines = [headers.map(csvEscape).join(",")];
    rows.forEach((row) => {
      lines.push([
        row.user_text,
        row.user_audio,
        row.risk_level,
        row.model_score,
        row.agent_reply,
      ].map(csvEscape).join(","));
    });
    downloadTextFile(`${base}.csv`, "\ufeff" + lines.join("\r\n"), "text/csv");
    return;
  }

  const blocks = [];
  blocks.push(`会话标题：${session.title}`);
  blocks.push(`session_id：${session.session_id}`);
  blocks.push(`导出时间：${new Date().toLocaleString()}`);
  blocks.push("字段：用户输入文本 / 用户输入语音 / 风险等级预测 / 模型评分 / agent回复文本");
  rows.forEach((row, index) => {
    blocks.push(`\n===== 第 ${index + 1} 轮 =====`);
    blocks.push(`用户输入文本：\n${row.user_text || ""}`);
    blocks.push(`用户输入语音：${row.user_audio || ""}`);
    blocks.push(`风险等级预测：${row.risk_level || ""}`);
    blocks.push(`模型评分：${row.model_score || ""}`);
    blocks.push(`agent回复文本：\n${row.agent_reply || ""}`);
  });
  downloadTextFile(`${base}.txt`, blocks.join("\n"), "text/plain");
}

async function sendMessage() {
  const input = $("textInput");
  const text = input.value.trim();
  if (!current() && !profileSetupDone) {
    showProfileModal();
    return;
  }
  if (!text && !audioBlob) {
    alert("请输入文本，或先录制/选择一段语音。");
    return;
  }

  $("sendBtn").disabled = true;
  $("recordBtn").disabled = true;
  try {
    const quoteToSend = quoteDraft ? { ...quoteDraft } : null;
    const session = await ensureSession(text || "语音对话");
    const selectedAudioName = audioName || "";
    const audioPath = await uploadAudio(session.session_id);
    addMessage(session, "user", text || "[语音输入]", audioPath ? "已附带语音" : "", quoteToSend, {
      audioPath: audioPath || "",
      audioName: audioPath ? selectedAudioName : "",
    });
    showTyping();

    input.value = "";
    audioBlob = null;
    audioName = "";
    quoteDraft = null;
    renderAudio();
    renderQuoteDraft();

    const payload = {
      user_text: buildOutboundText(text, quoteToSend),
      session_id: session.session_id,
      agent_profile: session.agentProfile || undefined,
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
  quoteDraft = null;
  pendingProfile = null;
  profileSetupDone = false;
  render();
  showProfileModal();
};

$("deleteSessionBtn").onclick = () => {
  if (!activeId || !confirm("删除当前对话？这只会删除浏览器本地记录。")) return;
  sessions = sessions.filter((s) => s.session_id !== activeId);
  activeId = sessions[0]?.session_id || null;
  quoteDraft = null;
  profileSetupDone = Boolean(activeId);
  save();
  render();
};

$("toggleDevBtn").onclick = () => {
  const next = localStorage.getItem(DEV_KEY) === "1" ? "0" : "1";
  localStorage.setItem(DEV_KEY, next);
  renderDevPanel();
};

$("saveProfileBtn").onclick = saveProfileFromModal;
$("skipProfileBtn").onclick = skipProfileSetup;
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

$("clearQuoteBtn").onclick = () => {
  quoteDraft = null;
  renderQuoteDraft();
};

if ($("exportTxtBtn")) $("exportTxtBtn").onclick = () => exportCurrentChat("txt");
if ($("exportCsvBtn")) $("exportCsvBtn").onclick = () => exportCurrentChat("csv");

$("sendBtn").onclick = sendMessage;
$("textInput").addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    sendMessage();
  }
});

render();
if (!current()) setTimeout(showProfileModal, 150);
