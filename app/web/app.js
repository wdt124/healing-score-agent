const KEY = "healing_agent_sessions_v1";
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
    addMessage(session, "agent", data.reply, `level: ${data.risk_level} | score: ${Number(data.score).toFixed(1)}`);
  } catch (err) {
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
