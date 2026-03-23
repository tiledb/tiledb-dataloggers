const REFRESH_INTERVAL = 10000;

// Array of APIs to cycle through
const API_ENDPOINTS = [
    "api/adc_linearity_all",
    "api/cis_all",
    "api/cis_linearity_all",
    "api/integrator_linearity_all"   // <-- NEW
];

const API_LABELS = {
    "api/adc_linearity_all": "ADC Linearity",
    "api/cis_all": "CIS",
    "api/cis_linearity_all": "CIS Linearity",
    "api/integrator_linearity_all": "Integrator Linearity (FENICs Gain 1)"   // <-- NEW
};


let currentApiIndex = 0;

let isPlaying = true;
let intervalHandle = null;


async function fetchAndPlot() {
    const API_URL = API_ENDPOINTS[currentApiIndex];

    try {
        const response = await fetch(API_URL);
        if (!response.ok) return;

        document.querySelector("h1").textContent =
            API_LABELS[API_URL] + " Dashboard (HG + LG)";

        const figs = await response.json();

        figs.forEach((fig_json, index) => {
            const divId = `plotly-div-${index + 1}`;
            const div = document.getElementById(divId);

            if (div) {
                div.style.transition = "transform 0.6s ease, opacity 0.6s ease";
                div.style.transform = "scale(0.9)";
                div.style.opacity = 0;

                setTimeout(() => {
                    Plotly.react(divId, fig_json.data, fig_json.layout);

                    // Force Plotly to resize to container, preventing layout jumps
                    Plotly.Plots.resize(div);

                    div.style.transform = "scale(1)";
                    div.style.opacity = 1;
                }, 400);
            }
        });

        updateDots();

        // Only rotate if playing
        if (isPlaying) {
            currentApiIndex = (currentApiIndex + 1) % API_ENDPOINTS.length;
        }

    } catch (err) {
        console.error("Error fetching data:", err);
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

        // Dot
        const dot = document.createElement("div");
        dot.classList.add("dot");

        dot.addEventListener("click", () => {
            currentApiIndex = index;
            updateDots();
            fetchAndPlot();

            // Optional: pause auto-rotation when dot clicked
            if (isPlaying) togglePlayPause();
        });

        // Label
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
    const dots = document.querySelectorAll(".dot");

    dots.forEach((dot, index) => {
        dot.classList.toggle("active", index === currentApiIndex);
    });
}

function togglePlayPause() {
    isPlaying = !isPlaying;

    const btn = document.getElementById("playPauseBtn");

    if (isPlaying) {
        btn.textContent = "⏸ Pause";
        startAutoRefresh();
    } else {
        btn.textContent = "▶ Play";
        stopAutoRefresh();
    }
}
function startAutoRefresh() {
    if (!intervalHandle) {
        intervalHandle = setInterval(fetchAndPlot, REFRESH_INTERVAL);
    }
}

function stopAutoRefresh() {
    if (intervalHandle) {
        clearInterval(intervalHandle);
        intervalHandle = null;
    }
}

document.getElementById("playPauseBtn")
    .addEventListener("click", togglePlayPause);

createDots();

// Initial load
fetchAndPlot();
startAutoRefresh();