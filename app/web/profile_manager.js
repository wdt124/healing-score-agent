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
