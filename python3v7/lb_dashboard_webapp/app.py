import math
from flask import Flask, render_template, jsonify
from influxdb import InfluxDBClient
import pandas as pd
import plotly.graph_objs as go
from plotly.subplots import make_subplots
import json
from werkzeug.middleware.proxy_fix import ProxyFix

# -------------------------
# Linear fit function
# -------------------------
def linear_fit(x, y):
    n = len(x)
    mean_x = sum(x) / n
    mean_y = sum(y) / n

    num = sum((x[i] - mean_x) * (y[i] - mean_y) for i in range(n))
    den = sum((x[i] - mean_x) ** 2 for i in range(n))
    slope = num / den if den != 0 else 0

    intercept = mean_y - slope * mean_x

    y_fit = [slope * xi + intercept for xi in x]

    ss_tot = sum((yi - mean_y) ** 2 for yi in y)
    ss_res = sum((y[i] - y_fit[i]) ** 2 for i in range(n))
    r2 = 1 - ss_res / ss_tot if ss_tot != 0 else 0

    max_dev = max(abs(y[i] - y_fit[i]) for i in range(n))

    return slope, intercept, r2, max_dev

# -------------------------
# Pulse analysis function
# -------------------------
def analyze_pulse(samples,
                  pedestal_samples=4,
                  noise_sigma_threshold=5,
                  threshold_fraction=0.5):
    """
    Robust pulse analysis.

    Returns:
        pedestal
        peak_value
        peak_index
        center_of_mass
        fwhm
    If no pulse is detected → returns pedestal and 0s.
    """

    if not samples or len(samples) < pedestal_samples + 2:
        return 0, 0, 0, 0, 0

    # Pedestal estimation (mean of first N samples)
    pedestal_region = samples[:pedestal_samples]
    pedestal = sum(pedestal_region) / pedestal_samples

    # Estimate noise sigma
    variance = sum((x - pedestal) ** 2 for x in pedestal_region) / pedestal_samples
    noise_sigma = math.sqrt(variance)

    # Subtract pedestal
    signal = [x - pedestal for x in samples]

    peak_value = max(signal)
    peak_index = signal.index(peak_value)

    # Pulse existence check
    if noise_sigma == 0 or peak_value < noise_sigma_threshold * noise_sigma:
        return pedestal, 0, 0, 0, 0

    # Center of mass
    total = sum(signal)
    center_of_mass = sum(i * v for i, v in enumerate(signal)) / total if total > 0 else 0

    # FWHM
    half_max = peak_value * threshold_fraction
    above_half = [i for i, v in enumerate(signal) if v >= half_max]
    fwhm = above_half[-1] - above_half[0] if len(above_half) >= 2 else 0

    return pedestal, peak_value, peak_index, center_of_mass, fwhm

# -------------------------
# Flask setup
# -------------------------
app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_prefix=1)
app.debug = True

# -------------------------
# Load secrets
# -------------------------
with open("secrets.json") as f:
    secrets = json.load(f)

influx_conf = secrets["influx"]

client = InfluxDBClient(
    host=influx_conf["host"],
    port=influx_conf["port"],
    username=influx_conf["username"],
    password=influx_conf["password"],
    database=influx_conf["database"]
)

# -------------------------
# Query ADC linearity samples
# -------------------------

def query_adc_lin_samples(gain):
    query = f"""
    SELECT last("value") AS value, last("std") AS std, last("adc_input") AS adc_input
    FROM "ADC_Linearity_Samples"
    WHERE "gain"='{gain}'
    GROUP BY "channel","gain","step"
    """
    result = client.query(query)
    rows = []

    for (measurement, tags), points in result.items():
        if tags is None:
            continue

        channel = tags.get("channel")
        step = int(tags.get("step"))

        for p in points:
            rows.append({
                "channel": channel,
                "gain": gain,
                "step": step,
                "adc_input": p["adc_input"],
                "value": p["value"],
                "std": p["std"]
            })

    return pd.DataFrame(rows)


# -------------------------
# Query CIS samples
# -------------------------
def query_cis_samples(gain):
    query = f"""
    SELECT last("value") AS value
    FROM "CIS_Samples"
    WHERE "gain"='{gain}'
    GROUP BY "channel","sample","event"
    """

    result = client.query(query)
    all_points = []

    for (measurement, tags), points in result.items():
        if tags is None:
            continue

        channel = tags.get("channel")
        sample = int(tags.get("sample", 0))
        event = int(tags.get("event", 0))

        for p in points:
            all_points.append({
                "channel": channel,
                "sample": sample,
                "value": p["value"],
                "event": event
            })

    df = pd.DataFrame(all_points)
    if df.empty:
        return df

    last_event = df["event"].max()
    df_last = df[df["event"] == last_event]
    df_last = df_last[df_last["sample"].between(0, 15)]
    return df_last

# -------------------------
# Query CIS metadata (only delta_crc)
# -------------------------
def query_cis_metadata():
    query = """
    SELECT last("delta_crc") AS delta_crc
    FROM "CIS"
    GROUP BY *
    """

    result = client.query(query)
    meta = {}

    for (measurement, tags), points in result.items():
        if tags is None:
            continue

        md_tag = None
        for k in tags.keys():
            if "PprGTH" in k:
                md_tag = k
                break
        if md_tag is None:
            continue

        md_label = md_tag.replace(" ", "_")
        ch = tags[md_tag]
        full_channel = f"{md_label}_{ch}"

        for p in points:
            meta[full_channel] = {
                "delta_crc": p.get("delta_crc", 0) or 0
            }

    return meta

# -------------------------
# Query CIS linearity samples
# -------------------------

def query_cis_lin_samples(gain):
    query = f"""
    SELECT last("value") AS value, last("dac_charge") AS dac_charge
    FROM "CIS_Linearity_Samples"
    WHERE "gain"='{gain}'
    GROUP BY "channel","gain","step"
    """
    result = client.query(query)
    rows = []

    for (measurement, tags), points in result.items():
        if tags is None:
            continue

        channel = tags.get("channel")
        step = int(tags.get("step"))

        for p in points:
            rows.append({
                "channel": channel,
                "gain": gain,
                "step": step,
                "dac_charge": p["dac_charge"],
                "value": p["value"]
            })

    return pd.DataFrame(rows)




def query_integrator_lin_samples():
    query = """
    SELECT last("value") AS value, last("dac_charge") AS dac_charge
    FROM "Integrator_Linearity_Samples"
    GROUP BY "channel","step"
    """

    result = client.query(query)
    rows = []

    for (measurement, tags), points in result.items():
        if tags is None:
            continue

        channel = tags.get("channel")
        step = int(tags.get("step"))

        for p in points:
            rows.append({
                "channel": channel,
                "step": step,
                "dac_charge": p["dac_charge"],
                "value": p["value"]
            })

    return pd.DataFrame(rows)


# -------------------------
# Plot builders
# -------------------------

def make_adc_lin_combined(df_hg, df_lg, md_label):
    """
    Combined ADC linearity plot for HG + LG in one figure.
    Fully responsive, fills MD box, dark style, 2x6 grid,
    axis range 0-4096.
    """
    channels = [f"{md_label}_CH{i}" for i in range(12)]

    fig = make_subplots(
        rows=2,
        cols=6,
        subplot_titles=["" for _ in channels]
    )

    for i, full_ch in enumerate(channels):
        row = i // 6 + 1
        col = i % 6 + 1

        ch_hg = df_hg[df_hg["channel"] == full_ch].sort_values("adc_input")
        ch_lg = df_lg[df_lg["channel"] == full_ch].sort_values("adc_input")

        hg_samples = ch_hg["value"].tolist()
        lg_samples = ch_lg["value"].tolist()

        hg_std = ch_hg.get("std", [0]*len(hg_samples)).tolist()
        lg_std = ch_lg.get("std", [0]*len(lg_samples)).tolist()

        # Linear fit
        if hg_samples:
            slope_hg, intercept_hg, r2_hg, maxdev_hg = linear_fit(ch_hg["adc_input"].tolist(), hg_samples)
            fit_hg = [slope_hg * x + intercept_hg for x in ch_hg["adc_input"].tolist()]
        else:
            fit_hg, maxdev_hg = [], 0

        if lg_samples:
            slope_lg, intercept_lg, r2_lg, maxdev_lg = linear_fit(ch_lg["adc_input"].tolist(), lg_samples)
            fit_lg = [slope_lg * x + intercept_lg for x in ch_lg["adc_input"].tolist()]
        else:
            fit_lg, maxdev_lg = [], 0

        # HG trace
        fig.add_trace(go.Scatter(
            x=ch_hg["adc_input"],
            y=hg_samples,
            error_y=dict(type='data', array=hg_std, visible=True),
            mode='markers',
            marker=dict(size=5, color='#FF0000'),
            hovertemplate=(
                "Input: %{x}<br>Value: %{y}<br>"
                f"Slope: {slope_hg:.3f}<br>"
                f"Max dev: {maxdev_hg:.1f}<extra>HG</extra>"
            ),
            showlegend=False
        ), row=row, col=col)

        # HG fit line
        fig.add_trace(go.Scatter(
            x=ch_hg["adc_input"],
            y=fit_hg,
            mode='lines',
            line=dict(color='#00FF00'),
            showlegend=False
        ), row=row, col=col)

        # LG trace
        fig.add_trace(go.Scatter(
            x=ch_lg["adc_input"],
            y=lg_samples,
            error_y=dict(type='data', array=lg_std, visible=True),
            mode='markers',
            marker=dict(size=5, color='#00FFFF'),
            hovertemplate=(
                "Input: %{x}<br>Value: %{y}<br>"
                f"Slope: {slope_lg:.3f}<br>"
                f"Max dev: {maxdev_lg:.1f}<extra>LG</extra>"
            ),
            showlegend=False
        ), row=row, col=col)

        # LG fit line
        fig.add_trace(go.Scatter(
            x=ch_lg["adc_input"],
            y=fit_lg,
            mode='lines',
            line=dict(color='#00FF00'),
            showlegend=False
        ), row=row, col=col)

    # Layout
    fig.update_layout(
        autosize=True,
        height=None,
        width=None,
        showlegend=False,
        title_text=md_label,
        title_x=0.5,
        margin=dict(l=5, r=5, t=25, b=5),
        plot_bgcolor="#111111",
        paper_bgcolor="#111111",
        font=dict(color="white")
    )

    # Set all axes 0-4096 and hide ticks
    for axis in fig.layout:
        if isinstance(fig.layout[axis], go.layout.XAxis) or isinstance(fig.layout[axis], go.layout.YAxis):
            fig.layout[axis].update(showticklabels=False, showgrid=True, gridcolor="#333", range=[0, 4096])

    return fig

def make_cis_lin_combined(df_hg, df_lg, md_label):
    """
    Combined CIS linearity plot for HG + LG in one figure.
    Fully responsive, fills MD box, dark style, 2x6 grid,
    axis range 0-4096.
    """
    channels = [f"{md_label}_CH{i}" for i in range(12)]

    fig = make_subplots(
        rows=2,
        cols=6,
        subplot_titles=["" for _ in channels]
    )

    for i, full_ch in enumerate(channels):
        row = i // 6 + 1
        col = i % 6 + 1

        ch_hg = df_hg[df_hg["channel"] == full_ch].sort_values("dac_charge")
        ch_lg = df_lg[df_lg["channel"] == full_ch].sort_values("dac_charge")

        hg_samples = ch_hg["value"].tolist()
        lg_samples = ch_lg["value"].tolist()

        pedestal_hg, peak_hg, peak_idx_hg, center_hg, fwhm_hg = analyze_pulse(hg_samples)
        pedestal_lg, peak_lg, peak_idx_lg, center_lg, fwhm_lg = analyze_pulse(lg_samples)

        # HG trace
        fig.add_trace(go.Scatter(
            x=ch_hg["dac_charge"],
            y=hg_samples,
            mode="markers",
            marker=dict(color='#FF0000', size=5),
            hovertemplate=(
                "DAC: %{x}<br>Value: %{y}<br>"
                f"Pedestal: {pedestal_hg:.1f}<br>"
                f"Peak: {peak_hg:.1f}<br>"
                f"Center: {center_hg:.1f}<br>"
                f"FWHM: {fwhm_hg:.1f}<extra>HG</extra>"
            ),
            showlegend=False
        ), row=row, col=col)

        # LG trace
        fig.add_trace(go.Scatter(
            x=ch_lg["dac_charge"],
            y=lg_samples,
            mode="markers",
            marker=dict(color='#00FFFF', size=5),
            hovertemplate=(
                "DAC: %{x}<br>Value: %{y}<br>"
                f"Pedestal: {pedestal_lg:.1f}<br>"
                f"Peak: {peak_lg:.1f}<br>"
                f"Center: {center_lg:.1f}<br>"
                f"FWHM: {fwhm_lg:.1f}<extra>LG</extra>"
            ),
            showlegend=False
        ), row=row, col=col)

    # Layout
    fig.update_layout(
        autosize=True,
        height=None,
        width=None,
        showlegend=False,
        title_text=md_label,
        title_x=0.5,
        margin=dict(l=5, r=5, t=25, b=5),
        plot_bgcolor="#111111",
        paper_bgcolor="#111111",
        font=dict(color="white")
    )

    # Set all axes to 0-4096 and hide ticks
    for axis in fig.layout:
        if isinstance(fig.layout[axis], go.layout.XAxis) or isinstance(fig.layout[axis], go.layout.YAxis):
            fig.layout[axis].update(showticklabels=False, showgrid=True, gridcolor="#333", range=[0, 4096])

    return fig

def make_cis_combined(df_hg, df_lg, md_label, meta_crc):
    """
    Combined CIS pulse plot (HG + LG) for one MD label.
    Fully responsive to MD box size.
    X-axis range: 0-15, Y-axis auto.
    """
    channels = [f"{md_label}_CH{i}" for i in range(12)]

    fig = make_subplots(
        rows=2,
        cols=6,
        subplot_titles=["" for _ in channels]
    )

    for i, full_ch in enumerate(channels):
        row = i // 6 + 1
        col = i % 6 + 1

        ch_hg = df_hg[df_hg["channel"] == full_ch].sort_values("sample")
        ch_lg = df_lg[df_lg["channel"] == full_ch].sort_values("sample")

        hg_samples = ch_hg["value"].tolist()
        lg_samples = ch_lg["value"].tolist()

        pedestal_hg, peak_hg, peak_idx_hg, center_hg, fwhm_hg = analyze_pulse(hg_samples)
        pedestal_lg, peak_lg, peak_idx_lg, center_lg, fwhm_lg = analyze_pulse(lg_samples)

        # HG trace
        fig.add_trace(go.Scatter(
            x=ch_hg["sample"],
            y=hg_samples,
            mode="markers",
            marker=dict(color='#FF0000', size=5),
            hovertemplate=(
                "Sample: %{x}<br>"
                "Value: %{y}<br>"
                f"Pedestal: {pedestal_hg:.1f}<br>"
                f"Peak: {peak_hg:.1f}<br>"
                f"Center: {center_hg:.1f}<br>"
                f"FWHM: {fwhm_hg:.1f}<extra>HG</extra>"
            ),
            showlegend=False
        ), row=row, col=col)

        # LG trace
        fig.add_trace(go.Scatter(
            x=ch_lg["sample"],
            y=lg_samples,
            mode="markers",
            marker=dict(color='#00FFFF', size=5),
            hovertemplate=(
                "Sample: %{x}<br>"
                "Value: %{y}<br>"
                f"Pedestal: {pedestal_lg:.1f}<br>"
                f"Peak: {peak_lg:.1f}<br>"
                f"Center: {center_lg:.1f}<br>"
                f"FWHM: {fwhm_lg:.1f}<extra>LG</extra>"
            ),
            showlegend=False
        ), row=row, col=col)

        # HG peak line
        if peak_idx_hg > 0:
            fig.add_vline(x=peak_idx_hg, line=dict(color='#FF0000', width=1), row=row, col=col)

        # LG peak line
        if peak_idx_lg > 0:
            fig.add_vline(x=peak_idx_lg, line=dict(color='#00FFFF', width=1), row=row, col=col)

        # HG FWHM
        if fwhm_hg > 0:
            fig.add_shape(
                type="rect",
                x0=peak_idx_hg - fwhm_hg / 2,
                x1=peak_idx_hg + fwhm_hg / 2,
                y0=0,
                y1=max(hg_samples) if hg_samples else 4096,
                fillcolor="#FF0000",
                opacity=0.2,
                row=row,
                col=col
            )

        # LG FWHM
        if fwhm_lg > 0:
            fig.add_shape(
                type="rect",
                x0=peak_idx_lg - fwhm_lg / 2,
                x1=peak_idx_lg + fwhm_lg / 2,
                y0=0,
                y1=max(lg_samples) if lg_samples else 4096,
                fillcolor="#00FFFF",
                opacity=0.2,
                row=row,
                col=col
            )

        # CRC error highlight
        delta_crc = meta_crc.get(full_ch, {}).get("delta_crc", 0)
        if delta_crc > 0:
            fig.add_shape(
                type="rect",
                x0=0,
                x1=15,
                y0=0,
                y1=4096,
                fillcolor="gray",
                opacity=0.4,
                layer="above",
                line_width=0,
                row=row,
                col=col
            )
            fig.update_xaxes(showline=True, linewidth=2, linecolor="red", row=row, col=col)
            fig.update_yaxes(showline=True, linewidth=2, linecolor="red", row=row, col=col)

    # Layout
    fig.update_layout(
        autosize=True,
        height=None,
        width=None,
        showlegend=False,
        title_text=md_label,
        title_x=0.5,
        margin=dict(l=5, r=5, t=25, b=5),
        plot_bgcolor="#111111",
        paper_bgcolor="#111111",
        font=dict(color="white")
    )

    # Axes: x fixed 0–15, y auto, hide ticks
    for axis in fig.layout:
        if isinstance(fig.layout[axis], go.layout.XAxis):
            fig.layout[axis].update(showticklabels=False, showgrid=True, gridcolor="#333", range=[0, 15])
        if isinstance(fig.layout[axis], go.layout.YAxis):
            fig.layout[axis].update(showticklabels=False, showgrid=True, gridcolor="#333")

    return fig



def make_integrator_lin_combined(df, md_label):
    """
    Integrator linearity plot (single curve per channel)
    """
    channels = [f"{md_label}_CH{i}" for i in range(12)]

    fig = make_subplots(
        rows=2,
        cols=6,
        subplot_titles=["" for _ in channels]
    )

    for i, full_ch in enumerate(channels):
        row = i // 6 + 1
        col = i % 6 + 1

        ch_df = df[df["channel"] == full_ch].sort_values("dac_charge")

        x = ch_df["dac_charge"].tolist()
        y = ch_df["value"].tolist()

        if y:
            slope, intercept, r2, maxdev = linear_fit(x, y)
            fit = [slope * xi + intercept for xi in x]
        else:
            slope, intercept, r2, maxdev = 0, 0, 0, 0
            fit = []

        # Data points
        fig.add_trace(go.Scatter(
            x=x,
            y=y,
            mode='markers',
            marker=dict(size=5, color='#FFA500'),
            hovertemplate=(
                "DAC: %{x}<br>Value: %{y}<br>"
                f"Slope: {slope:.3f}<br>"
                f"R²: {r2:.3f}<br>"
                f"Max dev: {maxdev:.1f}<extra></extra>"
            ),
            showlegend=False
        ), row=row, col=col)

        # Fit line
        fig.add_trace(go.Scatter(
            x=x,
            y=fit,
            mode='lines',
            line=dict(color='#00FF00'),
            showlegend=False
        ), row=row, col=col)

    fig.update_layout(
        autosize=True,
        height=None,
        width=None,
        showlegend=False,
        title_text=md_label,
        title_x=0.5,
        margin=dict(l=5, r=5, t=25, b=5),
        plot_bgcolor="#111111",
        paper_bgcolor="#111111",
        font=dict(color="white")
    )

    # Same style as others
    for axis in fig.layout:
        if isinstance(fig.layout[axis], go.layout.XAxis):
            fig.layout[axis].update(
                showticklabels=False,
                showgrid=True,
                gridcolor="#333",
                range=[0, 4096]
            )

        if isinstance(fig.layout[axis], go.layout.YAxis):
            fig.layout[axis].update(
                showticklabels=False,
                showgrid=True,
                gridcolor="#333",
                range=[0, 65535]
            )



    return fig


# -------------------------
# Routes
# -------------------------
@app.route("/")
def dashboard():
    df_hg = query_cis_samples("HG")
    md_labels = sorted(set(
        ch.split("_MD")[0] + "_MD" + ch.split("_MD")[1][0]
        for ch in df_hg["channel"].unique()
    ))

    test_name = "" 
    return render_template("dashboard.html", md_labels=md_labels, test_name=test_name)


@app.route("/api/cis_all")
def api_cis_all():
    try:
        df_hg = query_cis_samples("HG")
        df_lg = query_cis_samples("LG")
        meta_crc = query_cis_metadata()

        md_labels = sorted(set(
            ch.split("_MD")[0] + "_MD" + ch.split("_MD")[1][0]
            for ch in df_hg["channel"].unique()
        ))

        figs_json = []
        for md in md_labels:
            fig = make_cis_combined(df_hg, df_lg, md, meta_crc)
            figs_json.append(json.loads(fig.to_json()))

        return jsonify(figs_json)

    except Exception as e:
        print("CIS ALL ERROR:", e)
        return jsonify({"error": str(e)}), 500


@app.route("/api/adc_linearity_all")
def api_adc_lin_all():
    try:
        df_hg = query_adc_lin_samples("HG")
        df_lg = query_adc_lin_samples("LG")

        md_labels = sorted(set(
            ch.split("_MD")[0] + "_MD" + ch.split("_MD")[1][0]
            for ch in df_hg["channel"].unique()
        ))

        figs_json = []
        for md in md_labels:
            fig = make_adc_lin_combined(df_hg, df_lg, md)
            figs_json.append(json.loads(fig.to_json()))
        return jsonify(figs_json)

    except Exception as e:
        print("ADC LIN ALL ERROR:", e)
        return jsonify({"error": str(e)}), 500


@app.route("/api/cis_linearity_all")
def api_cis_lin_all():
    try:
        df_hg = query_cis_lin_samples("HG")
        df_lg = query_cis_lin_samples("LG")

        md_labels = sorted(set(
            ch.split("_MD")[0] + "_MD" + ch.split("_MD")[1][0]
            for ch in df_hg["channel"].unique()
        ))

        figs_json = []
        for md in md_labels:
            fig = make_cis_lin_combined(df_hg, df_lg, md)  # single figure for HG + LG
            figs_json.append(json.loads(fig.to_json()))

        return jsonify(figs_json)

    except Exception as e:
        print("CIS LIN ALL ERROR:", e)
        return jsonify({"error": str(e)}), 500


@app.route("/api/integrator_linearity_all")
def api_integrator_lin_all():
    try:
        df = query_integrator_lin_samples()

        if df.empty:
            return jsonify([])

        md_labels = sorted(set(
            ch.split("_MD")[0] + "_MD" + ch.split("_MD")[1][0]
            for ch in df["channel"].unique()
        ))

        figs_json = []
        for md in md_labels:
            fig = make_integrator_lin_combined(df, md)
            figs_json.append(json.loads(fig.to_json()))

        return jsonify(figs_json)

    except Exception as e:
        print("INTEGRATOR LIN ALL ERROR:", e)
        return jsonify({"error": str(e)}), 500
    
# -------------------------
# Run server
# -------------------------
if __name__ == "__main__":
    flask_conf = secrets["flask"]
    app.run(host=flask_conf["host"], port=flask_conf["port"], debug=True)