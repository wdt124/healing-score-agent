const PROFILE_KEY = "healing_agent_profiles_v1";

function loadSavedProfiles() {
  try {
    return JSON.parse(localStorage.getItem(PROFILE_KEY) || "[]");
  } catch {
    return [];
  }
}

function saveSavedProfiles(items) {
  localStorage.setItem(PROFILE_KEY, JSON.stringify(items));
}

function profileLabel(profile, index) {
  const name = profile.agent_name || "未命名 Agent";
  const tone = profile.tone_style ? ` / ${profile.tone_style}` : "";
  const role = profile.persona_role ? ` / ${profile.persona_role}` : "";
  return `${index + 1}. ${name}${tone}${role}`;
}

function profileHasContent(profile) {
  return Object.values(profile || {}).some((value) => String(value || "").trim());
}

function profileFingerprint(profile) {
  return JSON.stringify({
    agent_name: profile.agent_name || "",
    user_name: profile.user_name || "",
    tone_style: profile.tone_style || "",
    persona_role: profile.persona_role || "",
    custom_settings: profile.custom_settings || "",
  });
}

function rememberProfile(profile) {
  if (!profileHasContent(profile)) return;
  const items = loadSavedProfiles();
  const fp = profileFingerprint(profile);
  const filtered = items.filter((item) => profileFingerprint(item) !== fp);
  filtered.unshift(profile);
  saveSavedProfiles(filtered.slice(0, 20));
}

function fillProfileForm(profile) {
  profile = profile || {};
  $("profileAgentName").value = profile.agent_name || "";
  $("profileUserName").value = profile.user_name || "";
  $("profileTone").value = profile.tone_style || "温柔";
  $("profileRole").value = profile.persona_role || "";
  $("profileCustom").value = profile.custom_settings || "";
}

function ensureProfileControls() {
  if (!$('editProfileBtn')) {
    const editBtn = document.createElement("button");
    editBtn.id = "editProfileBtn";
    editBtn.className = "ghost";
    editBtn.textContent = "人设设定";
    const actions = document.querySelector(".header-actions");
    actions?.insertBefore(editBtn, actions.firstChild);
    editBtn.onclick = () => {
      const session = current();
      fillProfileForm(session?.agentProfile || pendingProfile || null);
      showProfileModal();
    };
  }

  if (!$('profileSelect')) {
    const selectWrap = document.createElement("div");
    selectWrap.style.margin = "12px 0";
    selectWrap.innerHTML = '<label style="display:flex;flex-direction:column;gap:6px;color:#7b7167;font-size:13px;">复用已有设定<select id="profileSelect" style="border:1px solid #eadfd2;border-radius:12px;padding:10px 12px;background:#fff;"></select></label>';
    const card = $("profileModal")?.querySelector("section");
    const paragraph = card?.querySelector("p");
    paragraph?.insertAdjacentElement("afterend", selectWrap);
    $("profileSelect").onchange = () => {
      const index = Number($("profileSelect").value);
      if (Number.isInteger(index) && index >= 0) fillProfileForm(loadSavedProfiles()[index]);
    };
  }
}

function renderProfileSelect() {
  ensureProfileControls();
  const select = $("profileSelect");
  if (!select) return;
  const profiles = loadSavedProfiles();
  select.innerHTML = '<option value="-1">新建或不复用</option>';
  profiles.forEach((profile, index) => {
    const option = document.createElement("option");
    option.value = String(index);
    option.textContent = profileLabel(profile, index);
    select.appendChild(option);
  });
}

const originalShowProfileModal = showProfileModal;
showProfileModal = function () {
  renderProfileSelect();
  originalShowProfileModal();
};

riskToValue = function (level) {
  const key = String(level || "").toLowerCase();
  if (key === "critical") return 4;
  if (key === "high") return 3;
  if (key === "medium") return 2;
  if (key === "low") return 1;
  return 0;
};

drawChart = function (canvasId, points, key) {
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
    ctx.beginPath();
    ctx.moveTo(10, y);
    ctx.lineTo(w - 10, y);
    ctx.stroke();
  }
  if (!points.length) {
    ctx.fillStyle = "#7b7167";
    ctx.font = "13px sans-serif";
    ctx.fillText("暂无数据", 20, 80);
    return;
  }
  const values = points.map((p) => Number(p[key] || 0));
  const max = key === "riskValue" ? 4 : Math.max(30, ...values);
  const xStep = points.length > 1 ? (w - 40) / (points.length - 1) : 0;
  ctx.strokeStyle = "#8c5f3f";
  ctx.lineWidth = 2;
  ctx.beginPath();
  values.forEach((v, i) => {
    const x = 20 + i * xStep;
    const y = h - 20 - (v / (max || 1)) * (h - 40);
    if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
  });
  ctx.stroke();
  ctx.fillStyle = "#8c5f3f";
  values.forEach((v, i) => {
    const x = 20 + i * xStep;
    const y = h - 20 - (v / (max || 1)) * (h - 40);
    ctx.beginPath();
    ctx.arc(x, y, 3, 0, Math.PI * 2);
    ctx.fill();
  });
};

$("saveProfileBtn").onclick = () => {
  const profile = getProfileFromForm();
  rememberProfile(profile);
  const session = current();
  if (session) {
    session.agentProfile = profileHasContent(profile) ? profile : null;
    session.profileSkipped = !session.agentProfile;
    save();
    render();
  } else {
    pendingProfile = profileHasContent(profile) ? profile : null;
    profileSetupDone = true;
  }
  hideProfileModal();
};

$("skipProfileBtn").onclick = () => {
  if (!current()) {
    pendingProfile = null;
    profileSetupDone = true;
  }
  hideProfileModal();
};

ensureProfileControls();
renderProfileSelect();
render();
