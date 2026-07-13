// Adds a custom tone-style option to the Agent profile form without changing
// the existing profile payload shape. The resolved custom text is still sent as
// tone_style, so the backend and saved profiles remain compatible.

(function () {
  const toneSelect = $("profileTone");
  if (!toneSelect) return;

  if (![...toneSelect.options].some((option) => option.value === "__custom__")) {
    const option = document.createElement("option");
    option.value = "__custom__";
    option.textContent = "自定义";
    toneSelect.appendChild(option);
  }

  let customInput = $("profileToneCustom");
  if (!customInput) {
    customInput = document.createElement("input");
    customInput.id = "profileToneCustom";
    customInput.maxLength = 40;
    customInput.placeholder = "例如：克制、像熟人聊天、少用安慰套话";
    customInput.style.cssText = "width:100%;margin-top:8px;border:1px solid #eadfd2;border-radius:12px;padding:10px 12px;display:none;";
    toneSelect.insertAdjacentElement("afterend", customInput);
  }

  const presetValues = new Set(
    [...toneSelect.options]
      .map((option) => option.value)
      .filter((value) => value !== "__custom__"),
  );

  function syncCustomToneVisibility() {
    const custom = toneSelect.value === "__custom__";
    customInput.style.display = custom ? "block" : "none";
    if (custom) setTimeout(() => customInput.focus(), 0);
  }

  toneSelect.addEventListener("change", syncCustomToneVisibility);

  const originalGetProfileFromForm = getProfileFromForm;
  getProfileFromForm = function () {
    const profile = originalGetProfileFromForm();
    profile.tone_style = toneSelect.value === "__custom__"
      ? customInput.value.trim().slice(0, 40)
      : toneSelect.value.trim().slice(0, 40);
    return profile;
  };

  if (typeof fillProfileForm === "function") {
    const originalFillProfileForm = fillProfileForm;
    fillProfileForm = function (profile) {
      originalFillProfileForm(profile);
      const tone = String(profile?.tone_style || "温柔").trim();
      if (presetValues.has(tone)) {
        toneSelect.value = tone;
        customInput.value = "";
      } else if (tone) {
        toneSelect.value = "__custom__";
        customInput.value = tone;
      } else {
        toneSelect.value = "温柔";
        customInput.value = "";
      }
      syncCustomToneVisibility();
    };
  }

  syncCustomToneVisibility();
})();
