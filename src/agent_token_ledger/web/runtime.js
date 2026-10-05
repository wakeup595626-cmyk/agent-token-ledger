(() => {
  const translations = window.AgentTokenLedgerTranslations || {};
  const defaultPreferences = {
    language: "zh-CN",
    currency: "CNY",
    exchange_rate: 7.2,
    refresh_seconds: 30,
    theme: "light",
  };
  const reportRangeOptions = ["7d", "30d", "90d", "month", "all", "custom"];
  const chartTypeOptions = ["bar", "line", "heatmap"];
  const chartMetricOptions = ["agent", "model"];
  const dimensionOptions = ["agent", "model", "source", "account", "date", "kind"];
  const chartHeight = 360;
  const svgNamespace = "http://www.w3.org/2000/svg";

  let state = null;
  let currentReport = null;
  let currentPage = "overview";
  let currentDimension = "agent";
  let currentChartType = "bar";
  let currentChartMetric = "agent";
  let currentReportRange = "all";
  let customStartDate = "";
  let customEndDate = "";
  let searchText = "";
  let reportRequestId = 0;
  let lastStateSignature = "";
  let priceSaveTimer = null;
  let priceSaveGeneration = 0;
  let priceSavePromise = Promise.resolve();
  let lastPriceTableSignature = "";
  let pendingPriceTableRender = false;
  let settingsSaveTimer = null;
  let startupBusy = false;
  let currentChartPoints = [];
  let currentHeatmapPoints = new Map();
  let systemThemeQuery = null;

  const byId = (id) => document.getElementById(id);
  const number = (value) => {
    const parsed = Number(value || 0);
    return Number.isFinite(parsed) ? parsed : 0;
  };
  const preferences = () => ({
    ...defaultPreferences,
    ...(state?.preferences || {}),
  });
  const locale = () => preferences().language || "zh-CN";
  const localeGroup = () => (locale().startsWith("zh") ? "zh" : "western");
  const t = (key, values = {}) => {
    const activeLocale = locale();
    const template =
      translations[activeLocale]?.[key] ??
      translations["zh-CN"]?.[key] ??
      key;
    return String(template).replace(/\{(\w+)\}/g, (_, name) =>
      Object.prototype.hasOwnProperty.call(values, name)
        ? String(values[name])
        : `{${name}}`,
    );
  };
  const text = (element, value) => {
    if (element) element.textContent = value;
  };
  const escapeHtml = (value) =>
    String(value ?? "").replace(
      /[&<>"']/g,
      (character) =>
        ({
          "&": "&amp;",
          "<": "&lt;",
          ">": "&gt;",
          '"': "&quot;",
          "'": "&#39;",
        })[character],
    );
  const integer = (value) =>
    number(value).toLocaleString(locale(), { maximumFractionDigits: 0 });
  const fixed = (value, digits = 2) =>
    number(value).toLocaleString(locale(), {
      minimumFractionDigits: digits,
      maximumFractionDigits: digits,
    });
  const tokenValue = (value) => {
    const numeric = number(value);
    if (localeGroup() === "western") {
      if (Math.abs(numeric) >= 1_000_000_000) {
        return `${fixed(numeric / 1_000_000_000, numeric >= 10_000_000_000 ? 1 : 2)} B`;
      }
      if (Math.abs(numeric) >= 1_000_000) {
        return `${fixed(numeric / 1_000_000, numeric >= 100_000_000 ? 1 : 2)} M`;
      }
      if (Math.abs(numeric) >= 1_000) {
        return `${fixed(numeric / 1_000, numeric >= 1_000_000 ? 0 : 1)} K`;
      }
      return integer(numeric);
    }
    if (Math.abs(numeric) >= 100_000_000) {
      return `${fixed(numeric / 100_000_000, numeric >= 1_000_000_000 ? 2 : 3)} 亿`;
    }
    if (Math.abs(numeric) >= 10_000) {
      return `${fixed(numeric / 10_000, numeric >= 1_000_000 ? 1 : 2)} 万`;
    }
    return integer(numeric);
  };
  const compactNumber = (value) => tokenValue(value);
  const money = (usd, currency = preferences().currency) => {
    const value = number(usd);
    const rate = number(preferences().exchange_rate) || 7.2;
    const amount = currency === "USD" ? value : value * rate;
    const digits = currency === "USD" && value < 1 ? 4 : 2;
    try {
      return amount.toLocaleString(locale(), {
        style: "currency",
        currency,
        minimumFractionDigits: digits,
        maximumFractionDigits: digits,
      });
    } catch (error) {
      const sign = currency === "USD" ? "$" : "¥";
      return `${sign}${fixed(amount, digits)}`;
    }
  };
  const fullTime = (value) => {
    if (!value) return "—";
    const parsed = typeof value === "number" ? new Date(value) : new Date(value);
    if (Number.isNaN(parsed.getTime())) return String(value);
    return parsed.toLocaleString(locale(), { hour12: false });
  };
  const parseDay = (value) => {
    const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(value || ""));
    if (!match) return null;
    return new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]));
  };
  const dayKey = (value) => {
    const year = value.getFullYear();
    const month = String(value.getMonth() + 1).padStart(2, "0");
    const day = String(value.getDate()).padStart(2, "0");
    return `${year}-${month}-${day}`;
  };
  const inputDay = (value) => dayKey(value);
  const addDays = (value, count) => {
    const next = new Date(value.getFullYear(), value.getMonth(), value.getDate());
    next.setDate(next.getDate() + count);
    return next;
  };
  const shortDay = (value) =>
    value.toLocaleDateString(locale(), { month: "short", day: "numeric" });
  const fullDay = (value) =>
    value.toLocaleDateString(locale(), {
      year: "numeric",
      month: "long",
      day: "numeric",
    });
  const niceMaximum = (value) => {
    if (!(value > 0)) return 1;
    const power = 10 ** Math.floor(Math.log10(value));
    const normalized = value / power;
    const factor =
      [1, 1.5, 2, 2.5, 5, 10].find((item) => normalized <= item) || 10;
    return factor * power;
  };
  const relativeTime = (ms) => {
    if (!ms) return "—";
    const seconds = Math.max(0, Math.round((number(ms) - Date.now()) / 1000));
    if (seconds <= 1) return t("time.soon");
    if (seconds < 60) return t("time.seconds", { count: seconds });
    return t("time.minutes", { count: Math.ceil(seconds / 60) });
  };
  const clipLabel = (value, maximum = 14) => {
    const current = String(value || "—");
    return current.length > maximum
      ? `${current.slice(0, maximum - 1)}…`
      : current;
  };
  const sourceKindLabel = (value) =>
    t(`sourceKind.${value}`) === `sourceKind.${value}`
      ? t("sourceKind.other")
      : t(`sourceKind.${value}`);
  const precisionLabel = (value) =>
    t(`precision.${value}`) === `precision.${value}`
      ? t("precision.local")
      : t(`precision.${value}`);
  const sourceStatusLabel = (value) =>
    t(`source.${value}`) === `source.${value}` ? value || "—" : t(`source.${value}`);
  const issueSourceLabel = (value) =>
    t(`issueSource.${value}`) === `issueSource.${value}`
      ? t("issueSource.local")
      : t(`issueSource.${value}`);
  const issueCodeLabel = (value) =>
    t(`issueCode.${value}`) === `issueCode.${value}`
      ? t("issueCode.other")
      : t(`issueCode.${value}`);
  const severityLabel = (value) => t(`severity.${value}`) || value;
  const windowModeLabel = (value) =>
    t(`window.${value}`) === `window.${value}`
      ? t("window.webview")
      : t(`window.${value}`);
  const costStatus = (group) => {
    const status = String(group?.cost_status || "missing");
    if (
      number(group?.cost_total_usd) <= 0 &&
      !number(group?.cost_estimated_usd) &&
      status === "missing"
    ) {
      return "missing";
    }
    return ["complete", "partial", "estimated", "missing"].includes(status)
      ? status
      : "estimated";
  };
  const costDisplay = (group, currency = preferences().currency) => {
    const status = costStatus(group);
    if (status === "missing" && number(group?.cost_total_usd) <= 0) {
      return t("cost.missing");
    }
    const value = money(group?.cost_total_usd, currency);
    return status === "complete" ? value : `≈${value}`;
  };
  const costStateLabel = (group) => t(`cost.${costStatus(group)}`);
  const costStateDetail = (group) => {
    const status = costStatus(group);
    if (status === "complete") return "";
    return status === "estimated"
      ? t("cost.estimatedDetail")
      : status === "partial"
        ? t("cost.partialDetail")
        : t("metric.costMissing");
  };
  const rangeLabel = (value) =>
    t(`range.${String(value || "all").replace(/d$/, "")}`);

  function applyStaticTranslations() {
    document.documentElement.lang = locale();
    document.title = t("app.name");
    document.querySelectorAll("[data-i18n]").forEach((element) => {
      element.textContent = t(element.dataset.i18n);
    });
    document.querySelectorAll("[data-i18n-title]").forEach((element) => {
      element.title = t(element.dataset.i18nTitle);
    });
    document.querySelectorAll("[data-i18n-placeholder]").forEach((element) => {
      element.placeholder = t(element.dataset.i18nPlaceholder);
    });
    document.querySelectorAll("[data-i18n-aria-label]").forEach((element) => {
      element.setAttribute("aria-label", t(element.dataset.i18nAriaLabel));
    });
    document.querySelectorAll("option[data-i18n]").forEach((option) => {
      option.textContent = t(option.dataset.i18n);
    });
  }

  function resolvedTheme(theme) {
    if (theme === "system") return systemThemeQuery?.matches ? "dark" : "light";
    return theme === "dark" ? "dark" : "light";
  }

  function applyTheme() {
    document.documentElement.dataset.theme = resolvedTheme(preferences().theme);
  }

  function renderNavigation() {
    document.querySelectorAll(".nav-item").forEach((button) => {
      const active = button.dataset.page === currentPage;
      button.classList.toggle("active", active);
      button.setAttribute("aria-current", active ? "page" : "false");
    });
  }

  function renderPage() {
    text(byId("pageTitle"), t(`page.${currentPage}.title`));
    text(byId("pageSubtitle"), t(`page.${currentPage}.subtitle`));
    document.querySelectorAll("[data-page-view]").forEach((view) => {
      view.hidden = view.dataset.pageView !== currentPage;
    });
  }

  function renderStatus() {
    const status = state?.status || "starting";
    const pill = byId("statusPill");
    if (pill) {
      pill.className = `status-pill ${status}`;
      text(pill, t(`status.${status}`) === `status.${status}` ? status : t(`status.${status}`));
    }
    byId("progressTrack")?.classList.toggle("active", status === "scanning");
    byId("progressTrack")?.closest(".scan-band")?.classList.toggle(
      "paused",
      Boolean(state?.paused),
    );
    const refreshButton = byId("refreshButton");
    if (refreshButton) {
      refreshButton.disabled = status === "scanning" || status === "stopping";
    }
    const pauseButton = byId("pauseButton");
    if (pauseButton) {
      const label = pauseButton.querySelector(".btn-label");
      const paused = Boolean(state?.paused);
      text(label, paused ? t("action.pauseContinue") : t("action.pause"));
      pauseButton.title = paused ? t("action.continueTitle") : t("action.pauseTitle");
      pauseButton.setAttribute("aria-label", pauseButton.title);
      pauseButton.classList.toggle("pause-active", paused);
      pauseButton.setAttribute("aria-pressed", paused ? "true" : "false");
      pauseButton.disabled = status === "stopping";
    }
    const settingsStopButton = byId("settingsStopButton");
    if (settingsStopButton) {
      settingsStopButton.disabled = status === "stopping";
    }
    const settingsPauseButton = byId("settingsPauseButton");
    if (settingsPauseButton) {
      const paused = Boolean(state?.paused);
      const label = paused ? t("settings.continueAuto") : t("settings.pauseAuto");
      text(byId("settingsPauseTitle"), label);
      settingsPauseButton.classList.toggle("pause-active", paused);
      settingsPauseButton.setAttribute("aria-pressed", paused ? "true" : "false");
      settingsPauseButton.title = label;
      settingsPauseButton.setAttribute("aria-label", label);
      settingsPauseButton.disabled = status === "stopping";
    }
    const error = state?.last_error || "";
    const banner = byId("errorBanner");
    if (banner) {
      banner.textContent = error ? `${t("status.error")}: ${error}` : "";
      banner.classList.toggle("visible", Boolean(error));
    }
  }

  function renderTotals() {
    const overall = currentReport?.overall;
    const recordText = overall
      ? t("metric.recordSessions", {
          events: integer(overall.events),
          sessions: integer(overall.sessions),
        })
      : t("scan.waiting");
    text(byId("totalCostValue"), overall ? costDisplay(overall) : "—");
    if (overall) {
      const selectedCurrency = preferences().currency;
      const secondaryCurrency = selectedCurrency === "CNY" ? "USD" : "CNY";
      const status = costStatus(overall);
      const coverage = `${integer(overall.costed_events)}/${integer(overall.events)}`;
      const sub =
        status === "missing" && number(overall.cost_total_usd) <= 0
          ? t("metric.costMissing")
          : `${t("chart.estimatedCost")} · ${money(
              overall.cost_total_usd,
              secondaryCurrency,
            )} · ${t("cost.complete")} ${money(
              overall.cost_known_usd,
              selectedCurrency,
            )} · ${t("metric.costCoverage", {
              covered: coverage.split("/")[0],
              events: coverage.split("/")[1],
            })}`;
      text(byId("totalCostSub"), sub);
      byId("totalCostValue").title = t("metric.costEstimateHint");
    } else {
      text(byId("totalCostSub"), recordText);
    }

    text(byId("totalInputValue"), overall ? tokenValue(overall.input_tokens_total) : "—");
    text(
      byId("totalInputSub"),
      overall
        ? `${t("metric.precise")} ${integer(overall.input_tokens_total)}`
        : recordText,
    );
    text(byId("totalOutputValue"), overall ? tokenValue(overall.output_tokens) : "—");
    text(
      byId("totalOutputSub"),
      overall
        ? `${t("metric.precise")} ${integer(overall.output_tokens)}`
        : recordText,
    );
    text(byId("totalCachedValue"), overall ? tokenValue(overall.cached_input_tokens) : "—");
    text(
      byId("totalCachedSub"),
      overall
        ? `${t("metric.precise")} ${integer(overall.cached_input_tokens)} · ${t("metric.cacheIncluded")}`
        : recordText,
    );
  }

  function renderScanFacts() {
    text(
      byId("lastScan"),
      state?.last_scan_finished_at
        ? fullTime(state.last_scan_finished_at)
        : t("scan.waiting"),
    );
    text(
      byId("nextScan"),
      state?.paused ? t("time.paused") : relativeTime(state?.next_scan_ms),
    );
    text(
      byId("duration"),
      state?.last_scan_duration_ms == null
        ? "—"
        : t("time.ms", { count: integer(state.last_scan_duration_ms) }),
    );
    text(
      byId("eventCount"),
      currentReport?.overall ? integer(currentReport.overall.events) : "—",
    );
  }

  function makeSegmented(container, values, active, labelFor, onSelect) {
    if (!container) return;
    const fragment = document.createDocumentFragment();
    values.forEach((value) => {
      const button = document.createElement("button");
      button.type = "button";
      button.dataset.value = value;
      button.textContent = labelFor(value);
      button.classList.toggle("active", value === active);
      button.setAttribute("aria-pressed", value === active ? "true" : "false");
      button.addEventListener("click", () => onSelect(value));
      fragment.appendChild(button);
    });
    container.replaceChildren(fragment);
  }

  function renderReportRange() {
    makeSegmented(
      byId("reportRangeTabs"),
      reportRangeOptions,
      currentReportRange,
      rangeLabel,
      (value) => {
        currentReportRange = value;
        if (value === "custom") {
          const end = parseDay(customEndDate) || new Date();
          const start = parseDay(customStartDate) || addDays(end, -29);
          customEndDate = dayKey(end);
          customStartDate = dayKey(start);
          byId("customEndInput").value = customEndDate;
          byId("customStartInput").value = customStartDate;
        }
        renderReportRange();
        loadReport();
      },
    );
    const customFields = byId("customRangeFields");
    if (customFields) customFields.hidden = currentReportRange !== "custom";
    text(
      byId("reportPeriodLabel"),
      currentReportRange === "custom" && customStartDate && customEndDate
        ? t("filter.rangeJoin", {
            start: customStartDate,
            end: customEndDate,
          })
        : rangeLabel(currentReportRange),
    );
  }

  function renderComparison() {
    const band = byId("comparisonBand");
    const items = byId("comparisonItems");
    const comparison = currentReport?.comparison;
    if (!band || !items) return;
    if (!comparison?.has_previous) {
      band.hidden = true;
      items.replaceChildren();
      return;
    }
    band.hidden = false;
    const entries = [
      ["metric.input", comparison.input_tokens_total],
      ["metric.output", comparison.output_tokens],
      ["metric.cached", comparison.cached_input_tokens],
      ["metric.cost", comparison.cost_total_usd],
      ["scan.events", comparison.events],
    ];
    items.innerHTML = entries
      .filter(([, value]) => value)
      .map(([labelKey, value]) => {
        const direction =
          value.direction === "up" ? "↑" : value.direction === "down" ? "↓" : "→";
        const percent =
          value.percent === null || value.percent === undefined
            ? "—"
            : `${fixed(Math.abs(value.percent), 1)}%`;
        const formatted =
          labelKey === "metric.cost"
            ? money(value.current)
            : compactNumber(value.current);
        return `<div class="comparison-item">
          <span>${escapeHtml(t(labelKey))}</span>
          <strong>${escapeHtml(formatted)}</strong>
          <small class="${escapeHtml(value.direction)}">${escapeHtml(direction)} ${escapeHtml(percent)}</small>
        </div>`;
      })
      .join("");
    text(byId("comparisonPeriod"), currentReport.range_label || "");
  }

  function renderChartToolbar() {
    makeSegmented(
      byId("chartTypeTabs"),
      chartTypeOptions,
      currentChartType,
      (value) => t(`chart.type${value[0].toUpperCase()}${value.slice(1)}`),
      (value) => {
        currentChartType = value;
        renderChartPanel();
      },
    );
    makeSegmented(
      byId("chartMetricTabs"),
      chartMetricOptions,
      currentChartMetric,
      (value) => t(`chart.${value}`),
      (value) => {
        currentChartMetric = value;
        renderChartPanel();
      },
    );
    const metricGroup = byId("chartMetricGroup");
    if (metricGroup) metricGroup.hidden = currentChartType === "heatmap";
    const legend = byId("heatmapLegend");
    if (legend) legend.hidden = currentChartType !== "heatmap";
    const titleKey =
      currentChartType === "heatmap"
        ? "chart.heatmapTitle"
        : currentChartType === "line"
          ? `chart.line${currentChartMetric[0].toUpperCase()}${currentChartMetric.slice(1)}Title`
          : `chart.bar${currentChartMetric[0].toUpperCase()}${currentChartMetric.slice(1)}Title`;
    const descKey =
      currentChartType === "heatmap"
        ? "chart.heatmapDesc"
        : currentChartType === "line"
          ? `chart.line${currentChartMetric[0].toUpperCase()}${currentChartMetric.slice(1)}Desc`
          : `chart.bar${currentChartMetric[0].toUpperCase()}${currentChartMetric.slice(1)}Desc`;
    text(byId("chartPanelTitle"), t(titleKey));
    text(byId("chartPanelDescription"), t(descKey));
  }

  function renderChartPanel() {
    renderChartToolbar();
    if (currentChartType === "heatmap") {
      renderHeatmapChart();
    } else {
      renderUsageChart();
    }
  }

  function chartGroups() {
    return (currentReport?.reports?.[currentChartMetric]?.groups || [])
      .filter((item) => number(item.processed_tokens) > 0)
      .sort(
        (left, right) =>
          number(right.processed_tokens) - number(left.processed_tokens),
      );
  }

  function pointFromGroup(group) {
    return {
      name: group.group || "—",
      value: number(group.processed_tokens),
      events: number(group.events),
      input: number(group.input_tokens_total),
      cached: number(group.cached_input_tokens),
      output: number(group.output_tokens),
      cost: number(group.cost_total_usd),
      costStatus: costStatus(group),
    };
  }

  function summaryValues(values) {
    const container = byId("chartSummary");
    if (!container) return;
    container.innerHTML = values
      .map(
        ([label, value]) =>
          `<div class="chart-summary-item"><span>${escapeHtml(label)}</span><strong title="${escapeHtml(value)}">${escapeHtml(value)}</strong></div>`,
      )
      .join("");
  }

  function makeSvg(svg, width, height) {
    svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
    svg.style.height = `${height}px`;
    svg.style.minHeight = `${height}px`;
    svg.replaceChildren();
    const scroll = byId("chartScroll");
    if (scroll) scroll.scrollLeft = 0;
    return (name, attributes = {}) => {
      const node = document.createElementNS(svgNamespace, name);
      Object.entries(attributes).forEach(([key, value]) =>
        node.setAttribute(key, value),
      );
      svg.appendChild(node);
      return node;
    };
  }

  function renderUsageChart() {
    const groups = chartGroups();
    currentChartPoints = groups.map(pointFromGroup);
    const empty = byId("chartEmpty");
    if (empty) empty.hidden = currentChartPoints.length > 0;
    const svg = byId("usageChart");
    if (!svg) return;
    const total = currentChartPoints.reduce((sum, item) => sum + item.value, 0);
    const top = currentChartPoints[0];
    const totalCost = currentChartPoints.reduce(
      (sum, item) => sum + item.cost,
      0,
    );
    summaryValues([
      [t("chart.totalSubjects"), t("chart.subjectCount", { count: integer(groups.length) })],
      [t("chart.totalValue"), tokenValue(total)],
      [
        t("chart.highest"),
        top ? `${clipLabel(top.name, 18)} · ${tokenValue(top.value)}` : "—",
      ],
      [t("chart.estimatedCost"), totalCost ? costDisplay({ cost_total_usd: total, cost_status: "estimated" }) : t("cost.missing")],
    ]);
    if (!currentChartPoints.length) {
      svg.replaceChildren();
      return;
    }
    if (currentChartType === "line") {
      renderLineChart(svg, currentChartPoints);
    } else {
      renderBarChart(svg, currentChartPoints);
    }
  }

  function drawGrid(make, padding, width, plotHeight, maximum) {
    for (let tick = 0; tick <= 4; tick += 1) {
      const ratio = tick / 4;
      const y = padding.top + plotHeight * ratio;
      make("line", {
        x1: padding.left,
        x2: width - padding.right,
        y1: y,
        y2: y,
        class: "chart-grid-line",
      });
      const label = make("text", {
        x: padding.left - 10,
        y: y + 4,
        "text-anchor": "end",
        class: "chart-axis-text",
      });
      label.textContent = compactNumber(maximum * (1 - ratio));
    }
  }

  function renderBarChart(svg, points) {
    const width = Math.max(1000, 104 + points.length * 84);
    const make = makeSvg(svg, width, chartHeight);
    svg.style.width = `${width}px`;
    svg.style.minWidth = `${width}px`;
    const padding = { left: 82, right: 30, top: 26, bottom: 82 };
    const plotWidth = width - padding.left - padding.right;
    const plotHeight = chartHeight - padding.top - padding.bottom;
    const bottom = padding.top + plotHeight;
    const maximum = niceMaximum(Math.max(...points.map((item) => item.value), 1));
    const step = plotWidth / points.length;
    const barWidth = Math.max(28, Math.min(72, step * 0.58));
    drawGrid(make, padding, width, plotHeight, maximum);
    points.forEach((point, index) => {
      const x = padding.left + step * index + step / 2;
      const barHeight = Math.max(2, (point.value / maximum) * plotHeight);
      make("rect", {
        x: x - barWidth / 2,
        y: bottom - barHeight,
        width: barWidth,
        height: barHeight,
        rx: 4,
        class: "chart-bar",
        "data-chart-index": index,
      });
      const valueLabel = make("text", {
        x,
        y: Math.max(padding.top, bottom - barHeight - 7),
        "text-anchor": "middle",
        class: "chart-axis-text value",
      });
      valueLabel.textContent = compactNumber(point.value);
      const nameLabel = make("text", {
        x,
        y: chartHeight - 46,
        "text-anchor": "end",
        class: "chart-axis-text",
        transform: `rotate(-32 ${x} ${chartHeight - 46})`,
      });
      nameLabel.textContent = clipLabel(point.name, points.length > 12 ? 13 : 17);
    });
  }

  function renderLineChart(svg, points) {
    const width = Math.max(1000, 104 + points.length * 84);
    const make = makeSvg(svg, width, chartHeight);
    svg.style.width = `${width}px`;
    svg.style.minWidth = `${width}px`;
    const padding = { left: 82, right: 30, top: 36, bottom: 82 };
    const plotWidth = width - padding.left - padding.right;
    const plotHeight = chartHeight - padding.top - padding.bottom;
    const bottom = padding.top + plotHeight;
    const maximum = niceMaximum(Math.max(...points.map((item) => item.value), 1));
    const step = points.length > 1 ? plotWidth / (points.length - 1) : 0;
    drawGrid(make, padding, width, plotHeight, maximum);
    const linePoints = points.map((point, index) => ({
      x:
        points.length > 1
          ? padding.left + step * index
          : padding.left + plotWidth / 2,
      y: bottom - (point.value / maximum) * plotHeight,
      point,
    }));
    if (linePoints.length > 1) {
      make("path", {
        d: linePoints
          .map(
            (item, index) =>
              `${index ? "L" : "M"} ${item.x.toFixed(2)} ${item.y.toFixed(2)}`,
          )
          .join(" "),
        class: "chart-line",
      });
    }
    linePoints.forEach((item, index) => {
      make("circle", {
        cx: item.x,
        cy: item.y,
        r: 4.2,
        class: "chart-line-point",
        "data-chart-index": index,
      });
      make("rect", {
        x: item.x - Math.max(18, step / 2),
        y: padding.top,
        width: Math.max(36, step),
        height: plotHeight,
        class: "chart-hit-area",
        "data-chart-index": index,
      });
      const nameLabel = make("text", {
        x: item.x,
        y: chartHeight - 46,
        "text-anchor": "end",
        class: "chart-axis-text",
        transform: `rotate(-32 ${item.x} ${chartHeight - 46})`,
      });
      nameLabel.textContent = clipLabel(
        item.point.name,
        points.length > 12 ? 13 : 17,
      );
      const valueLabel = make("text", {
        x: item.x,
        y: Math.max(padding.top - 8, item.y - 10),
        "text-anchor": "middle",
        class: "chart-axis-text value",
      });
      valueLabel.textContent = compactNumber(item.point.value);
    });
  }

  function buildDatePoints() {
    const groups = currentReport?.reports?.date?.groups || [];
    const byDate = new Map();
    const dateMs = [];
    groups.forEach((group) => {
      const parsed = parseDay(group.group);
      if (!parsed) return;
      byDate.set(dayKey(parsed), group);
      dateMs.push(parsed.getTime());
    });
    if (!dateMs.length) return [];
    const first = new Date(Math.min(...dateMs));
    const last = new Date(Math.max(...dateMs));
    const points = [];
    for (
      let cursor = first;
      cursor.getTime() <= last.getTime();
      cursor = addDays(cursor, 1)
    ) {
      const key = dayKey(cursor);
      const group = byDate.get(key);
      points.push({
        date: new Date(cursor.getFullYear(), cursor.getMonth(), cursor.getDate()),
        key,
        value: number(group?.processed_tokens),
        events: number(group?.events),
        input: number(group?.input_tokens_total),
        cached: number(group?.cached_input_tokens),
        output: number(group?.output_tokens),
        cost: number(group?.cost_total_usd),
        costStatus: costStatus(group),
      });
    }
    return points;
  }

  function renderHeatmapChart() {
    const points = buildDatePoints();
    currentHeatmapPoints = new Map();
    const svg = byId("usageChart");
    if (!svg) return;
    const empty = byId("chartEmpty");
    if (empty) empty.hidden = points.length > 0;
    const total = points.reduce((sum, item) => sum + item.value, 0);
    const active = points.filter((item) => item.value > 0);
    const peak = points.reduce(
      (best, item) => (item.value > best.value ? item : best),
      points[0] || { value: 0, date: null },
    );
    summaryValues([
      [
        t("chart.rangeValue"),
        points.length
          ? `${fullDay(points[0].date)} – ${fullDay(points[points.length - 1].date)}`
          : "—",
      ],
      [t("chart.totalValue"), tokenValue(total)],
      [t("chart.activeDays"), t("chart.unitCount", { count: integer(active.length) })],
      [t("chart.peakDay"), peak.date ? `${shortDay(peak.date)} · ${tokenValue(peak.value)}` : "—"],
    ]);
    if (!points.length) {
      svg.replaceChildren();
      return;
    }
    const firstDate = new Date(points[0].date);
    const mondayOffset = (firstDate.getDay() + 6) % 7;
    const gridStart = addDays(firstDate, -mondayOffset);
    const lastDate = new Date(points[points.length - 1].date);
    const totalDays = Math.round((lastDate - gridStart) / 86400000) + 1;
    const weeks = Math.ceil(totalDays / 7);
    const cell = 40;
    const verticalGap = 6;
    const horizontalGap = weeks <= 18 ? 18 : 6;
    const stepX = cell + horizontalGap;
    const stepY = cell + verticalGap;
    const gridWidth = weeks * stepX - horizontalGap;
    const availableWidth = Math.max(
      1000,
      Math.round((byId("chartScroll")?.clientWidth || 1000) - 28),
    );
    const width = Math.max(availableWidth, 48 + gridWidth + 40);
    const make = makeSvg(svg, width, chartHeight);
    svg.style.width = `${width}px`;
    svg.style.minWidth = `${width}px`;
    const startX = Math.max(48, (width - gridWidth) / 2);
    const startY = 16;
    const maximum = Math.max(...points.map((item) => item.value), 1);
    const byKey = new Map(points.map((item) => [item.key, item]));
    const weekdays = [2, 3, 4, 5, 6, 7, 1].map((day) =>
      new Date(2024, 0, day).toLocaleDateString(locale(), { weekday: "narrow" }),
    );
    weekdays.forEach((label, index) => {
      if (index % 2 !== 0) return;
      const textNode = make("text", {
        x: startX - 9,
        y: startY + index * stepY + 22,
        "text-anchor": "end",
        class: "heatmap-weekday",
      });
      textNode.textContent = label;
    });
    let previousMonth = -1;
    for (let dayIndex = 0; dayIndex < totalDays; dayIndex += 1) {
      const date = addDays(gridStart, dayIndex);
      const week = Math.floor(dayIndex / 7);
      const weekday = dayIndex % 7;
      if (date > lastDate || date < firstDate) continue;
      if (date.getDate() <= 7 && date.getMonth() !== previousMonth) {
        previousMonth = date.getMonth();
        const monthLabel = make("text", {
          x: startX + week * stepX,
          y: 10,
          class: "heatmap-month",
        });
        monthLabel.textContent = date.toLocaleDateString(locale(), {
          month: "short",
        });
      }
      const item = byKey.get(dayKey(date)) || {
        value: 0,
        events: 0,
        input: 0,
        cached: 0,
        output: 0,
        cost: 0,
        costStatus: "missing",
      };
      const ratio = item.value / maximum;
      const level = !item.value
        ? 0
        : ratio <= 0.25
          ? 1
          : ratio <= 0.5
            ? 2
            : ratio <= 0.75
              ? 3
              : 4;
      make("rect", {
        x: startX + week * stepX,
        y: startY + weekday * stepY,
        width: cell,
        height: cell,
        rx: 5,
        class: `heatmap-cell level-${level}`,
        "data-chart-index": dayIndex,
      });
      item.date = date;
      currentHeatmapPoints.set(dayIndex, item);
    }
  }

  function renderOverviewTopList() {
    const container = byId("overviewTopList");
    if (!container) return;
    const groups = (currentReport?.reports?.agent?.groups || []).slice(0, 5);
    if (!groups.length) {
      container.innerHTML = `<div class="empty">${escapeHtml(t("overview.noData"))}</div>`;
      return;
    }
    container.innerHTML = groups
      .map(
        (group, index) => `
          <div class="top-list-row">
            <span class="rank">${index + 1}</span>
            <strong title="${escapeHtml(group.group)}">${escapeHtml(group.group || "—")}</strong>
            <span>${escapeHtml(tokenValue(group.processed_tokens))}</span>
            <span class="cost-cell">${escapeHtml(costDisplay(group))}</span>
            <span class="cost-state ${escapeHtml(costStatus(group))}" title="${escapeHtml(costStateDetail(group))}">${escapeHtml(costStateLabel(group))}</span>
          </div>`,
      )
      .join("");
  }

  function renderDimensionTabs() {
    makeSegmented(
      byId("dimensionTabs"),
      dimensionOptions,
      currentDimension,
      (value) => t(`dimension.${value}`),
      (value) => {
        currentDimension = value;
        renderDimensionTabs();
        renderReport();
      },
    );
  }

  function renderReport() {
    const reportData = currentReport?.reports?.[currentDimension];
    const groups = reportData?.groups || [];
    const normalizedSearch = searchText.trim().toLowerCase();
    const filtered = groups.filter(
      (group) =>
        !normalizedSearch ||
        String(group.group || "")
          .toLowerCase()
          .includes(normalizedSearch),
    );
    const total = number(reportData?.overall?.processed_tokens);
    const body = byId("reportBody");
    if (!body) return;
    const empty = byId("reportEmpty");
    if (empty) {
      empty.hidden = filtered.length !== 0;
      text(empty, t("table.empty"));
    }
    body.replaceChildren();
    filtered.slice(0, 500).forEach((group) => {
      const row = document.createElement("tr");
      const share = total > 0 ? (number(group.processed_tokens) / total) * 100 : 0;
      const status = costStatus(group);
      row.innerHTML = `
        <td class="group-name" title="${escapeHtml(group.group)}">${escapeHtml(group.group || "—")}</td>
        <td class="num">${escapeHtml(tokenValue(group.processed_tokens))}</td>
        <td class="num">${escapeHtml(tokenValue(group.input_tokens_total))}</td>
        <td class="num">${escapeHtml(tokenValue(group.output_tokens))}</td>
        <td class="num">${escapeHtml(tokenValue(group.cached_input_tokens))}</td>
        <td class="num cost-cell">${escapeHtml(costDisplay(group, "CNY"))}</td>
        <td class="num cost-cell">${escapeHtml(costDisplay(group, "USD"))}</td>
        <td><span class="cost-state ${escapeHtml(status)}" title="${escapeHtml(costStateDetail(group))}">${escapeHtml(costStateLabel(group))}</span></td>
        <td class="num"><span class="bar"><span style="width:${Math.min(100, share).toFixed(2)}%"></span></span>${fixed(share, 1)}%</td>
        <td class="num">${escapeHtml(integer(group.events))}</td>`;
      body.appendChild(row);
    });
  }

  function renderSourceSummary() {
    const container = byId("sourceSummaryGrid");
    if (!container) return;
    const summary = state?.source_summary || {};
    const values = [
      ["source.supported", number(summary.supported), "supported"],
      ["source.detected", number(summary.detected), "detected"],
      ["source.missing", number(summary.missing), "missing"],
      ["source.unsupported", number(summary.unsupported), "unsupported"],
      ["source.error", number(summary.error), "error"],
    ];
    container.innerHTML = values
      .map(
        ([labelKey, value, className]) =>
          `<div class="detection-item ${className}"><span>${escapeHtml(t(labelKey))}</span><strong>${escapeHtml(integer(value))}</strong></div>`,
      )
      .join("");
  }

  function renderSources() {
    renderSourceSummary();
    const container = byId("sourceList");
    if (!container) return;
    container.replaceChildren();
    const runtimeByAgent = {};
    for (const row of state?.source_runtime || []) {
      const current = runtimeByAgent[row.agent] || { events: 0, processed_tokens: 0 };
      current.events += number(row.events);
      current.processed_tokens += number(row.processed_tokens);
      runtimeByAgent[row.agent] = current;
    }
    const sources = state?.sources || [];
    if (!sources.length) {
      container.innerHTML = `<div class="empty">${escapeHtml(t("overview.noData"))}</div>`;
      return;
    }
    sources.forEach((source) => {
      const row = document.createElement("div");
      row.className = "source-row";
      const runtime = runtimeByAgent[source.agent] || {
        events: 0,
        processed_tokens: 0,
      };
      const status = source.status || "missing";
      const paths = source.existing_paths?.length
        ? source.existing_paths
        : source.paths || [];
      const pathText = paths.length ? paths.join("; ") : t("source.noPaths");
      const precision = precisionLabel(source.metadata?.precision);
      const errorText = source.metadata?.error
        ? `; ${t("source.readError")}: ${source.metadata.error}`
        : "";
      row.innerHTML = `
        <div>
          <div class="source-name">${escapeHtml(source.agent)}</div>
          <div class="source-meta">${escapeHtml(sourceKindLabel(source.kind))} · ${escapeHtml(precision)} · ${escapeHtml(source.note || "")}${escapeHtml(errorText)}</div>
        </div>
        <div class="source-meta" title="${escapeHtml(pathText)}">${escapeHtml(pathText)}</div>
        <div class="source-status ${escapeHtml(status)}">${escapeHtml(sourceStatusLabel(status))} · ${escapeHtml(
          t("source.runtime", {
            events: integer(runtime.events),
            tokens: tokenValue(runtime.processed_tokens),
          }),
        )}</div>`;
      container.appendChild(row);
    });
  }

  function renderValidation() {
    const container = byId("validationGrid");
    const list = byId("issueList");
    if (!container || !list) return;
    const validation = state?.validation || {};
    const values = [
      [
        t("quality.passed"),
        validation.passed ? t("quality.pass") : t("quality.fail"),
        validation.passed ? "validation-pass" : "validation-fail",
      ],
      [t("quality.events"), integer(validation.events), ""],
      [t("quality.errors"), integer(validation.errors), validation.errors ? "validation-fail" : ""],
      [t("quality.warnings"), integer(validation.warnings), validation.warnings ? "validation-warn" : ""],
      [t("quality.semantic"), integer(validation.semantic_unknown), ""],
      [t("quality.providerMismatch"), integer(validation.provider_total_mismatches), ""],
    ];
    container.innerHTML = values
      .map(
        ([label, value, className]) =>
          `<div class="validation-item ${escapeHtml(className)}"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></div>`,
      )
      .join("");
    list.replaceChildren();
    const issues = (state?.issues || []).slice(0, 20);
    if (!issues.length) {
      list.innerHTML = `<div class="empty">${escapeHtml(t("quality.noIssues"))}</div>`;
      return;
    }
    issues.forEach((issue) => {
      const row = document.createElement("div");
      row.className = "issue-row";
      row.innerHTML = `
        <div><span class="issue-severity ${escapeHtml(issue.severity)}">${escapeHtml(severityLabel(issue.severity))}</span> <span class="issue-source">${escapeHtml(issueSourceLabel(issue.source))}</span></div>
        <div class="issue-message">${escapeHtml(issue.message)}</div>
        <div class="source-meta" title="${escapeHtml(issue.code)}">${escapeHtml(issueCodeLabel(issue.code))}</div>`;
      list.appendChild(row);
    });
  }

  function renderNotes() {
    const container = byId("notes");
    if (!container) return;
    const notes = currentReport?.notes || state?.notes || [];
    container.innerHTML = notes.length
      ? notes.map((note) => `<p>${escapeHtml(note)}</p>`).join("")
      : `<p>${escapeHtml(t("quality.waitingNotes"))}</p>`;
  }

  function renderSettings() {
    const prefs = preferences();
    const languageSelect = byId("languageSelect");
    const themeSelect = byId("themeSelect");
    const currencySelect = byId("currencySelect");
    const exchangeRateInput = byId("exchangeRateInput");
    const refreshSelect = byId("refreshSelect");
    if (languageSelect) languageSelect.value = prefs.language;
    if (themeSelect) themeSelect.value = prefs.theme;
    if (currencySelect) currencySelect.value = prefs.currency;
    if (exchangeRateInput && document.activeElement !== exchangeRateInput) {
      exchangeRateInput.value = String(prefs.exchange_rate);
    }
    if (refreshSelect) {
      const refreshValue = String(prefs.refresh_seconds);
      if (![...refreshSelect.options].some((option) => option.value === refreshValue)) {
        const option = document.createElement("option");
        option.value = refreshValue;
        option.textContent = t("settings.refreshHint");
        refreshSelect.appendChild(option);
      }
      refreshSelect.value = refreshValue;
    }
    renderPriceTable();
  }

  function renderStartupControl() {
    const input = byId("startupToggle");
    const stateText = byId("startupStateText");
    if (!input || !stateText) return;
    const supported = Boolean(state?.startup_supported);
    const enabled = supported && Boolean(state?.startup_enabled);
    const error = String(state?.startup_error || "");
    input.checked = enabled;
    input.disabled =
      !supported ||
      startupBusy ||
      state?.status === "stopping";
    input.setAttribute("aria-checked", enabled ? "true" : "false");
    if (!supported) {
      text(stateText, t("settings.startupUnavailable"));
    } else if (startupBusy) {
      text(stateText, t("settings.saving"));
    } else if (error) {
      text(stateText, t("settings.startupSaveFailed"));
    } else {
      text(
        stateText,
        enabled
          ? t("settings.startupEnabled")
          : t("settings.startupDisabled"),
      );
    }
    stateText.title = error;
  }

  function renderPriceTable(force = false) {
    const body = byId("priceTableBody");
    if (!body) return;
    const prices = preferences().model_prices || {};
    const signature = JSON.stringify(prices);
    const activeElement = document.activeElement;
    const isEditingPrice =
      activeElement &&
      body.contains(activeElement) &&
      activeElement.matches?.("input[data-price-model]");
    if (!force) {
      if (isEditingPrice && signature !== lastPriceTableSignature) {
        pendingPriceTableRender = true;
        return;
      }
      if (signature === lastPriceTableSignature && body.children.length) return;
    }
    const names = Object.keys(prices).sort((left, right) => {
      if (left === "*") return -1;
      if (right === "*") return 1;
      return left.localeCompare(right);
    });
    body.innerHTML = names
      .map((name) => {
        const price = prices[name] || {};
        const displayName = name === "*" ? t("settings.priceFallback") : name;
        return `<tr>
          <td class="price-model" title="${escapeHtml(displayName)}">${escapeHtml(displayName)}</td>
          <td><input type="number" min="0" step="0.0001" data-price-model="${escapeHtml(name)}" data-price-field="input" value="${escapeHtml(fixed(price.input, 4))}" aria-label="${escapeHtml(displayName)} ${escapeHtml(t("settings.priceInput"))}"></td>
          <td><input type="number" min="0" step="0.0001" data-price-model="${escapeHtml(name)}" data-price-field="cached_input" value="${escapeHtml(fixed(price.cached_input, 4))}" aria-label="${escapeHtml(displayName)} ${escapeHtml(t("settings.priceCached"))}"></td>
          <td><input type="number" min="0" step="0.0001" data-price-model="${escapeHtml(name)}" data-price-field="output" value="${escapeHtml(fixed(price.output, 4))}" aria-label="${escapeHtml(displayName)} ${escapeHtml(t("settings.priceOutput"))}"></td>
        </tr>`;
      })
      .join("");
    lastPriceTableSignature = signature;
    pendingPriceTableRender = false;
    body.querySelectorAll("input[data-price-model]").forEach((input) => {
      input.addEventListener("input", () => {
        const generation = ++priceSaveGeneration;
        window.clearTimeout(priceSaveTimer);
        priceSaveTimer = window.setTimeout(
          () => savePriceTable(generation),
          650,
        );
      });
    });
    if (body.dataset.priceFocusBound !== "1") {
      body.dataset.priceFocusBound = "1";
      body.addEventListener("focusout", () => {
        window.setTimeout(() => {
          if (
            pendingPriceTableRender &&
            !body.contains(document.activeElement)
          ) {
            renderPriceTable(true);
          }
        }, 0);
      });
    }
  }

  function renderAbout() {
    const version = state?.version || "—";
    text(byId("sidebarVersion"), version);
    text(byId("aboutVersion"), version);
    text(byId("aboutWindowMode"), windowModeLabel(state?.window_mode));
    const aboutStatus = byId("aboutStatus");
    if (aboutStatus) {
      text(aboutStatus, byId("statusPill")?.textContent || t("status.starting"));
      aboutStatus.className = `about-status ${state?.status || "starting"}`;
    }
    text(byId("aboutDataDir"), state?.work_dir || "—");
    const settingsRefreshButton = byId("settingsRefreshButton");
    if (settingsRefreshButton) {
      settingsRefreshButton.disabled =
        state?.status === "scanning" || state?.status === "stopping";
    }
    const settingsStopButton = byId("settingsStopButton");
    if (settingsStopButton) {
      settingsStopButton.disabled = state?.status === "stopping";
    }
  }

  function render() {
    applyTheme();
    applyStaticTranslations();
    renderNavigation();
    renderPage();
    renderStatus();
    renderScanFacts();
    renderTotals();
    renderComparison();
    renderReportRange();
    renderChartPanel();
    renderOverviewTopList();
    renderDimensionTabs();
    renderReport();
    renderSources();
    renderValidation();
    renderNotes();
    renderSettings();
    renderStartupControl();
    renderAbout();
  }

  async function fetchJson(path, options = {}) {
    const response = await fetch(path, {
      cache: "no-store",
      ...options,
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return response.json();
  }

  async function post(path, body = {}) {
    return fetchJson(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  }

  async function loadReport() {
    const requestId = ++reportRequestId;
    const params = new URLSearchParams({ range: currentReportRange });
    if (currentReportRange === "custom") {
      if (!customStartDate || !customEndDate) return;
      params.set("start", customStartDate);
      params.set("end", customEndDate);
    }
    try {
      const next = await fetchJson(`/api/report?${params.toString()}`);
      if (requestId !== reportRequestId) return;
      currentReport = next;
      renderTotals();
      renderComparison();
      renderScanFacts();
      renderChartPanel();
      renderOverviewTopList();
      renderReport();
      renderNotes();
    } catch (error) {
      // Keep the last complete report visible while a scan or request settles.
    }
  }

  function stateSignature(next) {
    return JSON.stringify({
      scan_id: next?.scan_id,
      status: next?.status,
      scanning: next?.scanning,
      paused: next?.paused,
      last_scan_finished_at: next?.last_scan_finished_at,
      last_scan_duration_ms: next?.last_scan_duration_ms,
      preferences: next?.preferences,
      startup_supported: next?.startup_supported,
      startup_enabled: next?.startup_enabled,
      startup_error: next?.startup_error,
      startup_command: next?.startup_command,
    });
  }

  async function loadState(force = false) {
    try {
      const next = await fetchJson("/api/state");
      const signature = stateSignature(next);
      if (!force && signature === lastStateSignature) return false;
      const previousScanId = state?.scan_id;
      state = next;
      lastStateSignature = signature;
      render();
      if (!currentReport || force || next.scan_id !== previousScanId) {
        await loadReport();
      }
      return true;
    } catch (error) {
      return false;
    }
  }

  async function action(path, body = {}) {
    try {
      const next = await post(path, body);
      state = next;
      lastStateSignature = stateSignature(next);
      render();
      if (path === "/api/preferences" || path === "/api/preferences/reset" || path === "/api/preferences/prices/reset") {
        loadReport();
      }
      return next;
    } catch (error) {
      showSaveState(t("settings.saveFailed"), "error");
      return null;
    }
  }

  function showSaveState(message, className = "") {
    const saved = byId("settingsSaved");
    if (!saved) return;
    saved.className = `save-state ${className}`.trim();
    text(saved, message);
  }

  async function togglePaused() {
    const nextPaused = !Boolean(state?.paused);
    if (state) {
      state = {
        ...state,
        paused: nextPaused,
        status: nextPaused ? "paused" : state.scanning ? "scanning" : "ready",
        next_scan_ms: null,
      };
      renderStatus();
      renderScanFacts();
      renderAbout();
    }
    const result = await action("/api/pause", { paused: nextPaused });
    if (!result) await loadState(true);
  }

  async function toggleStartup(event) {
    const input = event?.currentTarget || byId("startupToggle");
    const enabled = Boolean(input?.checked);
    if (!state?.startup_supported) {
      renderStartupControl();
      return;
    }
    startupBusy = true;
    renderStartupControl();
    showSaveState(t("settings.saving"), "saving");
    try {
      const next = await post("/api/startup", { enabled });
      state = next;
      lastStateSignature = stateSignature(next);
      render();
      const result = next.action_result || {};
      if (!result.ok) {
        showSaveState(
          result.message || t("settings.startupSaveFailed"),
          "error",
        );
      } else {
        showSaveState(t("settings.saved"));
      }
    } catch (error) {
      showSaveState(t("settings.saveFailed"), "error");
      await loadState(true);
    } finally {
      startupBusy = false;
      renderStartupControl();
    }
  }

  async function waitForServiceToStop(timeoutMs = 5000) {
    const deadline = Date.now() + timeoutMs;
    while (Date.now() < deadline) {
      try {
        const response = await fetch("/api/health", { cache: "no-store" });
        if (!response.ok) return true;
      } catch (error) {
        return true;
      }
      await new Promise((resolve) => window.setTimeout(resolve, 200));
    }
    return false;
  }

  async function stopService() {
    if (!window.confirm(t("action.stopConfirm"))) return;
    const button = byId("settingsStopButton");
    if (button) button.disabled = true;
    if (state) {
      state = { ...state, status: "stopping" };
      renderStatus();
      renderAbout();
    }
    let stopped = false;
    try {
      await post("/api/stop");
      stopped = true;
    } catch (error) {
      // The service may close the connection immediately after accepting the request.
      stopped = await waitForServiceToStop();
    }
    if (stopped) {
      byId("stoppedOverlay")?.classList.add("visible");
      return;
    }
    if (button) button.disabled = false;
    await loadState(true);
    showSaveState(t("settings.saveFailed"), "error");
  }

  function collectSettings() {
    return {
      language: byId("languageSelect")?.value || defaultPreferences.language,
      theme: byId("themeSelect")?.value || defaultPreferences.theme,
      currency: byId("currencySelect")?.value || defaultPreferences.currency,
      exchange_rate: Number(byId("exchangeRateInput")?.value || defaultPreferences.exchange_rate),
      refresh_seconds: Number(byId("refreshSelect")?.value || defaultPreferences.refresh_seconds),
    };
  }

  async function saveSettings() {
    showSaveState(t("settings.saving"), "saving");
    const result = await action("/api/preferences", collectSettings());
    if (result) showSaveState(t("settings.saved"));
  }

  async function savePriceTable(generation = priceSaveGeneration) {
    if (generation !== priceSaveGeneration) return;
    const body = byId("priceTableBody");
    if (!body) return;
    const modelPrices = {};
    body.querySelectorAll("input[data-price-model]").forEach((input) => {
      const model = input.dataset.priceModel;
      const field = input.dataset.priceField;
      if (!model || !field) return;
      modelPrices[model] = modelPrices[model] || {
        input: 0,
        cached_input: 0,
        output: 0,
      };
      modelPrices[model][field] = Math.max(0, number(input.value));
    });
    showSaveState(t("settings.saving"), "saving");
    const saveRequest = action("/api/preferences", {
      model_prices: modelPrices,
    });
    priceSavePromise = saveRequest.then(
      () => undefined,
      () => undefined,
    );
    const result = await saveRequest;
    if (generation !== priceSaveGeneration) return;
    if (result) showSaveState(t("settings.priceSaved"));
  }

  async function resetSettings() {
    const result = await action("/api/preferences/reset");
    if (result) showSaveState(t("settings.saved"));
  }

  async function resetPrices() {
    priceSaveGeneration += 1;
    window.clearTimeout(priceSaveTimer);
    priceSaveTimer = null;
    await priceSavePromise;
    const result = await action("/api/preferences/prices/reset");
    if (result) {
      renderPriceTable(true);
      showSaveState(t("settings.priceSaved"));
    }
  }

  async function refreshNow() {
    const result = await action("/api/refresh");
    if (result) {
      window.setTimeout(loadState, 450);
      window.setTimeout(loadReport, 1000);
    }
  }

  async function exportReport(format) {
    const params = new URLSearchParams({
      format,
      dimension: currentDimension,
      range: currentReportRange,
    });
    if (currentReportRange === "custom") {
      params.set("start", customStartDate);
      params.set("end", customEndDate);
    }
    try {
      const response = await fetch(`/api/export?${params.toString()}`, { cache: "no-store" });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `agent-token-ledger-${currentDimension}-${currentReportRange}.${format}`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
    } catch (error) {
      showSaveState(t("settings.saveFailed"), "error");
    }
  }

  function copyText(value) {
    if (navigator.clipboard?.writeText) {
      return navigator.clipboard
        .writeText(value)
        .catch(() => legacyCopyText(value));
    }
    return legacyCopyText(value);
  }

  function legacyCopyText(value) {
    const area = document.createElement("textarea");
    area.value = value;
    area.setAttribute("readonly", "");
    area.style.position = "fixed";
    area.style.top = "0";
    area.style.left = "0";
    area.style.opacity = "0";
    document.body.appendChild(area);
    const selection = document.getSelection();
    const previousRange =
      selection && selection.rangeCount > 0 ? selection.getRangeAt(0) : null;
    area.focus();
    area.select();
    area.setSelectionRange(0, area.value.length);
    let copied = false;
    try {
      copied = document.execCommand("copy");
    } finally {
      area.remove();
      if (previousRange && selection) {
        selection.removeAllRanges();
        selection.addRange(previousRange);
      }
    }
    if (!copied) {
      throw new Error("copy failed");
    }
  }

  async function copyDiagnostics() {
    try {
      const data = await fetchJson("/api/diagnostics");
      const value = JSON.stringify(data, null, 2);
      await copyText(value);
      showSaveState(t("action.copied"));
    } catch (error) {
      showSaveState(t("action.copyFailed"), "error");
    }
  }

  function bindChartTooltip() {
    const svg = byId("usageChart");
    const tooltip = byId("chartTooltip");
    if (!svg || !tooltip) return;
    svg.addEventListener("mousemove", (event) => {
      const target = event.target.closest?.("[data-chart-index]");
      if (!target) {
        tooltip.style.display = "none";
        return;
      }
      const index = Number(target.dataset.chartIndex);
      let point = null;
      if (currentChartType === "heatmap") {
        point = currentHeatmapPoints.get(index);
      } else {
        point = currentChartPoints[index];
      }
      if (!point) return;
      const title = currentChartType === "heatmap" ? fullDay(point.date) : point.name;
      const lines = [
        `<strong>${escapeHtml(title)}</strong>`,
        `${escapeHtml(t("chart.totalValue"))}: ${escapeHtml(tokenValue(point.value))}`,
        `${escapeHtml(t("table.input"))}: ${escapeHtml(tokenValue(point.input))}`,
        `${escapeHtml(t("table.output"))}: ${escapeHtml(tokenValue(point.output))}`,
        `${escapeHtml(t("table.cached"))}: ${escapeHtml(tokenValue(point.cached))}`,
        `${escapeHtml(t("chart.estimatedCost"))}: ${escapeHtml(
          point.cost > 0
            ? costDisplay({
                cost_total_usd: point.cost,
                cost_status: point.costStatus || "estimated",
              })
            : t("cost.missing"),
        )}`,
        `${escapeHtml(t("table.events"))}: ${escapeHtml(integer(point.events))}`,
      ];
      tooltip.innerHTML = lines.join("<br>");
      tooltip.style.display = "block";
      const width = tooltip.offsetWidth || 220;
      const height = tooltip.offsetHeight || 120;
      const left = Math.min(event.clientX + 14, window.innerWidth - width - 12);
      const top = Math.min(event.clientY + 14, window.innerHeight - height - 12);
      tooltip.style.left = `${Math.max(12, left)}px`;
      tooltip.style.top = `${Math.max(12, top)}px`;
    });
    svg.addEventListener("mouseleave", () => {
      tooltip.style.display = "none";
    });
  }

  function on(id, eventName, handler) {
    const element = byId(id);
    if (element) element.addEventListener(eventName, handler);
  }

  function bindEvents() {
    document.querySelectorAll(".nav-item").forEach((button) => {
      button.addEventListener("click", () => {
        currentPage = button.dataset.page || "overview";
        renderNavigation();
        renderPage();
      });
    });
    on("openUsageButton", "click", () => {
      currentPage = "usage";
      renderNavigation();
      renderPage();
    });
    on("refreshButton", "click", refreshNow);
    on("pauseButton", "click", togglePaused);
    on("sourceRefreshButton", "click", refreshNow);
    on("settingsRefreshButton", "click", refreshNow);
    on("settingsPauseButton", "click", togglePaused);
    on("settingsStopButton", "click", stopService);
    on("startupToggle", "change", toggleStartup);
    on("searchInput", "input", (event) => {
      searchText = event.target.value;
      renderReport();
    });
    on("settingsForm", "submit", (event) => {
      event.preventDefault();
      saveSettings();
    });
    on("resetSettingsButton", "click", resetSettings);
    on("resetPricesButton", "click", resetPrices);
    on("exportCsvButton", "click", () => exportReport("csv"));
    on("exportJsonButton", "click", () => exportReport("json"));
    on("openDataButton", "click", () => action("/api/data/open"));
    on("clearCacheButton", "click", () => {
      if (window.confirm(`${t("settings.clearCache")}？`)) action("/api/cache/clear");
    });
    on("copyDiagnosticsButton", "click", copyDiagnostics);
    on("customStartInput", "change", (event) => {
      customStartDate = event.target.value;
      if (customStartDate && customEndDate) {
        renderReportRange();
        loadReport();
      }
    });
    on("customEndInput", "change", (event) => {
      customEndDate = event.target.value;
      if (customStartDate && customEndDate) {
        renderReportRange();
        loadReport();
      }
    });
    [
      "languageSelect",
      "themeSelect",
      "currencySelect",
      "refreshSelect",
    ].forEach((id) => {
      on(id, "change", () => {
        window.clearTimeout(settingsSaveTimer);
        settingsSaveTimer = window.setTimeout(saveSettings, 120);
      });
    });
    on("exchangeRateInput", "input", () => {
      window.clearTimeout(settingsSaveTimer);
      settingsSaveTimer = window.setTimeout(saveSettings, 650);
    });
  }

  function initialize() {
    systemThemeQuery = window.matchMedia?.("(prefers-color-scheme: dark)");
    systemThemeQuery?.addEventListener?.("change", () => {
      if (preferences().theme === "system") render();
    });
    verifyLanguageOptions();
    bindEvents();
    bindChartTooltip();
    render();
    loadState(true);
    window.setInterval(() => loadState(false), 2000);
  }

  // 启动自检：语言下拉框的选项必须与翻译目录覆盖的语言完全一致。
  // 上次“下拉框为空”就是 HTML 选项与目录脱节导致的，这里做一次前端兜底。
  function verifyLanguageOptions() {
    const select = byId("languageSelect");
    if (!select) return;
    const expected = Object.keys(translations).sort();
    const actual = [...select.options].map((option) => option.value).sort();
    const missing = expected.filter((value) => !actual.includes(value));
    const extra = actual.filter((value) => !expected.includes(value));
    if (missing.length || extra.length) {
      console.warn(
        "语言下拉框与翻译目录不一致：",
        missing.length ? `缺少 ${missing.join(",")}` : "",
        extra.length ? `多余 ${extra.join(",")}` : ""
      );
    }
  }

  initialize();
})();
