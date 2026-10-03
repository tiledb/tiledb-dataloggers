const FADE_MS = 160;
const PREFETCH_TTL_MS = 12000;
const DWELL_STORAGE_KEY = "lb_dashboard_slide_dwell_ms";
const DEFAULT_DWELL_MS = 8000;

let slideDwellMs = DEFAULT_DWELL_MS;

const API_ENDPOINTS = [
    "api/adc_linearity_all",
    "api/cis_all",
    "api/cis_phase_recon_all",
    "api/cis_linearity_all",
    "api/integrator_linearity_all"
];

const API_LABELS = {
    "api/adc_linearity_all": "ADC Linearity",
    "api/cis_all": "CIS",
    "api/cis_phase_recon_all": "CIS Pulse Reconstruction",
    "api/cis_linearity_all": "CIS Linearity",
    "api/integrator_linearity_all": "Integrator Linearity (FENICs Gain 1)"
};

const PLOTLY_CONFIG = {
    responsive: true,
    displayModeBar: false,
    staticPlot: false
};

let currentApiIndex = 0;
let isPlaying = true;
let dwellTimer = null;
let hideProgressTimer = null;
let activeController = null;
let loadToken = 0;

/** @type {Map<string, {at:number, payload:any, promise?:Promise<any>}>} */
const payloadCache = new Map();


function sleep(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
}


function setMainTitle(apiUrl, timestamp) {
    const label = API_LABELS[apiUrl] || "Dashboard";
    const tsPart = timestamp ? ` | ${timestamp}` : "";
    document.querySelector("h1").textContent =
        `${label} Dashboard (HG + LG)${tsPart}`;
}


function setTimestampWarning(message) {
    const el = document.getElementById("tsWarning");
    if (!el) return;
    if (!message) {
        el.hidden = true;
        el.textContent = "";
        return;
    }
    el.hidden = false;
    el.textContent = message;
}


function extractPayload(payload) {
    if (Array.isArray(payload)) {
        return { timestamp: null, timestamp_warning: null, figures: payload };
    }
    if (payload && typeof payload === "object") {
        return {
            timestamp: payload.timestamp || null,
            timestamp_warning: payload.timestamp_warning || null,
            figures: payload.figures || []
        };
    }
    return { timestamp: null, timestamp_warning: null, figures: [] };
}


function showLoadProgress(label) {
    const box = document.getElementById("loadProgress");
    if (!box) return;
    if (hideProgressTimer) {
        clearTimeout(hideProgressTimer);
        hideProgressTimer = null;
    }
    box.hidden = false;
    box.classList.remove("is-hiding");
    document.getElementById("loadProgressLabel").textContent = label;
    setLoadProgress(0);
}


function setLoadProgress(pct, label) {
    const bar = document.getElementById("loadProgressBar");
    const pctEl = document.getElementById("loadProgressPct");
    const labelEl = document.getElementById("loadProgressLabel");
    if (!bar || !pctEl) return;
    const clamped = Math.max(0, Math.min(100, Math.round(pct)));
    bar.style.width = `${clamped}%`;
    pctEl.textContent = `${clamped}%`;
    if (label && labelEl) labelEl.textContent = label;
}


function hideLoadProgress(delayMs = 120) {
    const box = document.getElementById("loadProgress");
    if (!box) return;
    setLoadProgress(100);
    if (hideProgressTimer) clearTimeout(hideProgressTimer);
    hideProgressTimer = setTimeout(() => {
        box.classList.add("is-hiding");
        setTimeout(() => {
            box.hidden = true;
            box.classList.remove("is-hiding");
            setLoadProgress(0);
        }, 180);
        hideProgressTimer = null;
    }, delayMs);
}


function getCachedPayload(apiUrl) {
    const hit = payloadCache.get(apiUrl);
    if (!hit) return null;
    if (Date.now() - hit.at > PREFETCH_TTL_MS) {
        payloadCache.delete(apiUrl);
        return null;
    }
    return hit.payload || null;
}


function setCachedPayload(apiUrl, payload) {
    payloadCache.set(apiUrl, { at: Date.now(), payload });
}


async function fetchPayload(apiUrl, signal, onProgress) {
    const cached = getCachedPayload(apiUrl);
    if (cached) {
        onProgress(0.7, "Cached");
        return cached;
    }

    // Reuse in-flight prefetch for the same URL
    const existing = payloadCache.get(apiUrl);
    if (existing && existing.promise) {
        onProgress(0.2, "Waiting…");
        const payload = await existing.promise;
        onProgress(0.75, "Ready");
        return payload;
    }

    onProgress(0.08, "Fetching…");
    let creep = 0.08;
    const creepTimer = setInterval(() => {
        creep = Math.min(0.65, creep + 0.04);
        onProgress(creep, "Fetching…");
    }, 200);

    const pending = (async () => {
        const response = await fetch(apiUrl, { signal });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        onProgress(0.72, "Parsing…");
        return extractPayload(await response.json());
    })();

    payloadCache.set(apiUrl, { at: Date.now(), promise: pending });

    try {
        const payload = await pending;
        setCachedPayload(apiUrl, payload);
        return payload;
    } catch (err) {
        payloadCache.delete(apiUrl);
        throw err;
    } finally {
        clearInterval(creepTimer);
    }
}


function prefetchSlide(index) {
    const apiUrl = API_ENDPOINTS[index];
    if (!apiUrl) return;
    if (getCachedPayload(apiUrl)) return;
    const existing = payloadCache.get(apiUrl);
    if (existing && existing.promise) return;

    const controller = new AbortController();
    const pending = fetch(apiUrl, { signal: controller.signal })
        .then((r) => {
            if (!r.ok) throw new Error(`HTTP ${r.status}`);
            return r.json();
        })
        .then((raw) => {
            const payload = extractPayload(raw);
            setCachedPayload(apiUrl, payload);
            return payload;
        })
        .catch(() => {
            payloadCache.delete(apiUrl);
        });

    payloadCache.set(apiUrl, { at: Date.now(), promise: pending });
}


async function fadePlots(opacity) {
    const title = document.querySelector("h1");
    const plots = document.querySelectorAll(".fade-plot");
    title.style.opacity = String(opacity);
    plots.forEach((div) => {
        div.style.opacity = String(opacity);
    });
    await sleep(FADE_MS);
}


async function renderFigures(figures, onProgress) {
    const jobs = figures.map(async (fig_json, index) => {
        const divId = `plotly-div-${index + 1}`;
        const div = document.getElementById(divId);
        if (!div || !fig_json) return;
        await Plotly.react(divId, fig_json.data, fig_json.layout, PLOTLY_CONFIG);
    });

    // Progress while parallel renders run
    let done = 0;
    const tracked = jobs.map((p) =>
        p.then(() => {
            done += 1;
            if (onProgress) {
                onProgress(
                    0.76 + 0.2 * (done / Math.max(figures.length, 1)),
                    `Rendering ${done}/${figures.length}…`
                );
            }
        }).catch((err) => console.error("Plotly render error:", err))
    );

    await Promise.all(tracked);
}


function clearDwell() {
    if (dwellTimer) {
        clearTimeout(dwellTimer);
        dwellTimer = null;
    }
}


function getDwellMs() {
    return slideDwellMs;
}


function initDwellSelect() {
    const select = document.getElementById("dwellSelect");
    if (!select) return;

    const stored = Number(localStorage.getItem(DWELL_STORAGE_KEY));
    const allowed = Array.from(select.options).map((o) => Number(o.value));
    if (allowed.includes(stored)) {
        slideDwellMs = stored;
        select.value = String(stored);
    } else {
        slideDwellMs = DEFAULT_DWELL_MS;
        select.value = String(DEFAULT_DWELL_MS);
    }

    select.addEventListener("change", () => {
        const ms = Number(select.value);
        if (!Number.isFinite(ms) || ms <= 0) return;
        slideDwellMs = ms;
        localStorage.setItem(DWELL_STORAGE_KEY, String(ms));
        // Restart dwell countdown with the new interval if playing
        if (isPlaying) {
            scheduleNextSlide();
        }
    });
}


function scheduleNextSlide() {
    clearDwell();
    if (!isPlaying) return;

    const nextIndex = (currentApiIndex + 1) % API_ENDPOINTS.length;
    prefetchSlide(nextIndex);

    dwellTimer = setTimeout(() => {
        currentApiIndex = nextIndex;
        loadSlide(currentApiIndex);
    }, getDwellMs());
}


async function loadSlide(index, { fromUser = false } = {}) {
    const token = ++loadToken;
    currentApiIndex = index;
    updateDots();

    if (activeController) {
        activeController.abort();
    }
    activeController = new AbortController();
    const { signal } = activeController;

    clearDwell();

    const API_URL = API_ENDPOINTS[currentApiIndex];
    const slideLabel = API_LABELS[API_URL] || "Dashboard";

    let lastPct = 0;
    const onProgress = (pct, label) => {
        lastPct = Math.max(lastPct, pct * 100);
        setLoadProgress(lastPct, `${slideLabel}: ${label}`);
    };

    showLoadProgress(`${slideLabel}: Starting…`);

    try {
        const payload = await fetchPayload(API_URL, signal, onProgress);
        if (token !== loadToken) return;

        const hasExisting = Array.from(document.querySelectorAll(".fade-plot"))
            .some((div) => div.data && div.data.length);

        if (hasExisting) {
            setLoadProgress(Math.max(lastPct, 74), `${slideLabel}: Transition…`);
            await fadePlots(0);
            if (token !== loadToken) return;
        }

        setMainTitle(API_URL, payload.timestamp);
        setTimestampWarning(payload.timestamp_warning);
        await renderFigures(payload.figures, onProgress);
        if (token !== loadToken) return;

        setLoadProgress(98, `${slideLabel}: Done`);
        await fadePlots(1);
        hideLoadProgress(100);

        // Warm the following slide in the background
        prefetchSlide((currentApiIndex + 1) % API_ENDPOINTS.length);
        scheduleNextSlide();

    } catch (err) {
        if (err && err.name === "AbortError") return;
        console.error("Error loading slide:", err);
        setLoadProgress(100, `${slideLabel}: Failed`);
        await fadePlots(1);
        hideLoadProgress(600);
        if (isPlaying && token === loadToken) {
            scheduleNextSlide();
        }
    }
}


function createDots() {
    const container = document.getElementById("carouselDots");
    container.innerHTML = "";

    API_ENDPOINTS.forEach((api, index) => {
        const dotContainer = document.createElement("div");
        dotContainer.style.display = "flex";
        dotContainer.style.flexDirection = "column";
        dotContainer.style.alignItems = "center";
        dotContainer.style.cursor = "pointer";

        const dot = document.createElement("div");
        dot.classList.add("dot");

        dot.addEventListener("click", () => {
            if (isPlaying) togglePlayPause();
            loadSlide(index, { fromUser: true });
        });

        const label = document.createElement("div");
        label.style.fontSize = "10px";
        label.style.color = "#ccc";
        label.style.marginTop = "3px";
        label.textContent = API_LABELS[api];

        dotContainer.appendChild(dot);
        dotContainer.appendChild(label);
        container.appendChild(dotContainer);
    });

    updateDots();
}


function updateDots() {
    document.querySelectorAll(".dot").forEach((dot, index) => {
        dot.classList.toggle("active", index === currentApiIndex);
    });
}


function togglePlayPause() {
    isPlaying = !isPlaying;
    const btn = document.getElementById("playPauseBtn");

    if (isPlaying) {
        btn.textContent = "⏸ Pause";
        scheduleNextSlide();
    } else {
        btn.textContent = "▶ Play";
        clearDwell();
    }
}


document.getElementById("playPauseBtn")
    .addEventListener("click", togglePlayPause);

let resizeTimer = null;
window.addEventListener("resize", () => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(() => {
        document.querySelectorAll(".fade-plot").forEach((div) => {
            if (div && div.data) Plotly.Plots.resize(div);
        });
    }, 120);
});

initDwellSelect();
createDots();
loadSlide(0);
