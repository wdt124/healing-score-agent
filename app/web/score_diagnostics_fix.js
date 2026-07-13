// Developer-mode score diagnostics patch.
// Loaded after app.js/profile_manager.js so it can replace display helpers without
// changing the chat transport or session UI.

(function () {
  const numberOrNull = (value) => {
    if (value === null || value === undefined || value === "") return null;
    const number = Number(value);
    return Number.isFinite(number) ? number : null;
  };

  addMetric = function (session, data, audioPath) {
    if (!session.metrics) session.metrics = [];

    const instantScore = numberOrNull(data.instant_score);
    const persistentScore = numberOrNull(data.persistent_score ?? data.smoothed_score);
    const compatibilityScore = numberOrNull(data.score);

    const metric = {
      t: new Date().toLocaleTimeString(),
      // 新后端会明确返回拆分字段；旧后端不再被伪装成两条完全相同的曲线。
      instantScore,
      persistentScore,
      score: compatibilityScore,
      scoreFieldsPresent: instantScore !== null && persistentScore !== null,
      riskAdjustedScore: numberOrNull(data.risk_adjusted_score),
      riskLevel: data.risk_level || "unknown",
      riskValue: riskToValue(data.risk_level),
      safetyMode: data.safety_mode || "-",
      evidence: Array.isArray(data.evidence) ? data.evidence : [],
      riskSignals: Array.isArray(data.risk_signals) ? data.risk_signals : [],
      model: data.model_name || "-",
      provider: data.model_provider || "-",
      audio: Boolean(audioPath),
    };

    session.metrics.push(metric);
    session.currentMetric = metric;
    session.lastTrace = buildTrace(data, audioPath, session.agentProfile);
    save();
  };

  metricInstant = function (metric) {
    return numberOrNull(metric?.instantScore);
  };

  metricPersistent = function (metric) {
    return numberOrNull(metric?.persistentScore);
  };

  renderDevCurrent = function (session) {
    const box = $("devCurrent");
    if (!box) return;
    const metric = session?.currentMetric || session?.metrics?.[session.metrics.length - 1];
    if (!metric) {
      box.textContent = "暂无请求";
      return;
    }

    const instant = metricInstant(metric);
    const persistent = metricPersistent(metric);
    const backendReady = instant !== null && persistent !== null;
    const evidence = (metric.evidence || []).map((item) => `<li>${String(item)}</li>`).join("");
    const signals = (metric.riskSignals || [])
      .map((item) => `${item.source || "-"}:${item.name || "-"}(${Number(item.severity || 0).toFixed(2)})`)
      .join("；");

    box.innerHTML = `
      <div class="metric-grid three">
        <div class="metric-card">
          <div class="metric-label">本轮模型评分</div>
          <div class="metric-value">${instant === null ? "未返回" : instant.toFixed(1)}</div>
          <div class="metric-sub">instant_score</div>
        </div>
        <div class="metric-card">
          <div class="metric-label">持续趋势评分</div>
          <div class="metric-value">${persistent === null ? "未返回" : persistent.toFixed(1)}</div>
          <div class="metric-sub">persistent_score</div>
        </div>
        <div class="metric-card">
          <div class="metric-label">风险等级</div>
          <div class="metric-value">${metric.riskLevel || "-"}</div>
          <div class="metric-sub">mode: ${metric.safetyMode || "-"}</div>
        </div>
      </div>
      ${backendReady ? "" : '<div class="metric-warning">后端没有返回拆分评分字段。请确认 Python 服务已重启；前端不会再用同一个 score 伪造两条曲线。</div>'}
      <div class="metric-sub metric-note">风险等级由当前规则信号、持续分和历史趋势共同决定，不是把本轮模型分直接换算成等级。</div>
      ${evidence ? `<div class="metric-evidence"><strong>本轮判定依据</strong><ul>${evidence}</ul></div>` : ""}
      ${signals ? `<div class="metric-sub"><strong>风险信号：</strong>${signals}</div>` : ""}
      <div class="metric-sub" style="margin-top:8px;">${metric.provider || "-"} / ${metric.model || "-"} / ${metric.audio ? "文本+语音" : "文本"} / ${metric.t}</div>
    `;
  };

  function finiteSeries(points, key) {
    return points.map((point) => numberOrNull(point?.[key]));
  }

  function drawAvailableSeries(ctx, values, yFor, xFor, dashed) {
    const available = values
      .map((value, index) => ({ value, index }))
      .filter((item) => item.value !== null);
    if (!available.length) return;

    ctx.setLineDash(dashed ? [5, 4] : []);
    ctx.beginPath();
    available.forEach((item, position) => {
      const x = xFor(item.index);
      const y = yFor(item.value);
      if (position === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
    });
    ctx.stroke();
    ctx.setLineDash([]);

    available.forEach((item) => {
      ctx.beginPath();
      ctx.arc(xFor(item.index), yFor(item.value), 2.8, 0, Math.PI * 2);
      ctx.fill();
    });
  }

  drawScoreChart = function (canvasId, points) {
    const canvas = $(canvasId);
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    const w = canvas.width;
    const h = canvas.height;
    const left = 36;
    const right = 10;
    const top = 25;
    const bottom = 20;

    ctx.clearRect(0, 0, w, h);
    ctx.fillStyle = "#fffaf7";
    ctx.fillRect(0, 0, w, h);

    if (!points.length) {
      drawEmptyChart(ctx, w, h);
      return;
    }

    const instant = finiteSeries(points, "instantScore");
    const persistent = finiteSeries(points, "persistentScore");
    const available = [...instant, ...persistent].filter((value) => value !== null);

    if (!available.length) {
      ctx.fillStyle = "#7b7167";
      ctx.font = "12px sans-serif";
      ctx.fillText("后端未返回 instant_score / persistent_score", 18, 75);
      return;
    }

    let min = Math.max(0, Math.floor((Math.min(...available) - 5) / 10) * 10);
    let max = Math.min(100, Math.ceil((Math.max(...available) + 5) / 10) * 10);
    if (max - min < 20) {
      min = Math.max(0, min - 10);
      max = Math.min(100, max + 10);
    }
    if (max <= min) max = min + 20;

    const yFor = (value) => h - bottom - ((value - min) / (max - min)) * (h - top - bottom);
    const xFor = (index) => chartPointX(index, points.length, left, right, w);

    ctx.strokeStyle = "#eadfd2";
    ctx.fillStyle = "#7b7167";
    ctx.font = "11px sans-serif";
    ctx.lineWidth = 1;
    for (let i = 0; i <= 4; i++) {
      const value = min + (max - min) * (i / 4);
      const y = yFor(value);
      ctx.beginPath(); ctx.moveTo(left, y); ctx.lineTo(w - right, y); ctx.stroke();
      ctx.fillText(value.toFixed(0), 4, y + 4);
    }

    if (instant.some((value) => value !== null)) {
      ctx.strokeStyle = "#8c5f3f";
      ctx.fillStyle = "#8c5f3f";
      ctx.lineWidth = 2;
      drawAvailableSeries(ctx, instant, yFor, xFor, false);
    }

    if (persistent.some((value) => value !== null)) {
      ctx.strokeStyle = "#8a7f74";
      ctx.fillStyle = "#8a7f74";
      ctx.lineWidth = 2;
      drawAvailableSeries(ctx, persistent, yFor, xFor, true);
    }

    ctx.fillStyle = "#8c5f3f";
    ctx.fillRect(left, 7, 13, 2);
    ctx.fillStyle = "#5f554d";
    ctx.fillText("本轮模型评分", left + 18, 11);
    ctx.strokeStyle = "#8a7f74";
    ctx.setLineDash([5, 4]);
    ctx.beginPath(); ctx.moveTo(left + 112, 8); ctx.lineTo(left + 125, 8); ctx.stroke();
    ctx.setLineDash([]);
    ctx.fillStyle = "#5f554d";
    ctx.fillText("持续趋势", left + 130, 11);
  };

  // 导出中的“模型评分”应为本轮模型原始分，而不是持续分或风险修正分。
  const originalBuildExportRows = buildExportRows;
  buildExportRows = function (session) {
    const rows = originalBuildExportRows(session);
    rows.forEach((row, index) => {
      const metric = (session?.metrics || [])[index] || {};
      const instant = numberOrNull(metric.instantScore);
      if (instant !== null) row.model_score = String(instant);
    });
    return rows;
  };

  // 已有 localStorage 中由旧前端生成的重合字段无法还原，标记为旧格式，避免继续画成两条有效曲线。
  sessions.forEach((session) => {
    (session.metrics || []).forEach((metric) => {
      if (metric.scoreFieldsPresent === undefined) {
        metric.instantScore = null;
        metric.persistentScore = null;
      }
    });
  });
  save();
  renderDevPanel();
})();
