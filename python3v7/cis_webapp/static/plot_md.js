const REFRESH_INTERVAL = 10000;

async function fetchAndPlot() {
    const API_URL = "/api/combined";

    try {
        const response = await fetch(API_URL);
        if (!response.ok) return;

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
    } catch (err) {
        console.error("Error fetching data:", err);
    }
}

fetchAndPlot();
setInterval(fetchAndPlot, REFRESH_INTERVAL);