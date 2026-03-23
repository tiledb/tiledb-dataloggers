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




async function fetchAndPlot() {
    const API_URL = API_ENDPOINTS[currentApiIndex];
    
    try {
        const response = await fetch(API_URL);
        if (!response.ok) return;
        document.querySelector("h1").textContent = API_LABELS[API_ENDPOINTS[currentApiIndex]] + " Dashboard (HG + LG)";
        const figs = await response.json();

        figs.forEach((fig_json, index) => {
            const divId = `plotly-div-${index + 1}`;
            const div = document.getElementById(divId);
            if (div) {
                // Zoom out + fade out
                div.style.transition = "transform 0.6s ease, opacity 0.6s ease";
                div.style.transform = "scale(0.9)";
                div.style.opacity = 0;

                setTimeout(() => {
                    Plotly.react(divId, fig_json.data, fig_json.layout);

                    // Zoom in + fade in
                    div.style.transform = "scale(1)";
                    div.style.opacity = 1;
                }, 400);
            }
        });

        // Move to the next API in the cycle
        currentApiIndex = (currentApiIndex + 1) % API_ENDPOINTS.length;

    } catch (err) {
        console.error("Error fetching data:", err);
    }
}

// Initial fetch
fetchAndPlot();

// Repeat every REFRESH_INTERVAL
setInterval(fetchAndPlot, REFRESH_INTERVAL);