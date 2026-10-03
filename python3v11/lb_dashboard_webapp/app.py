import math
import time
import json
from zoneinfo import ZoneInfo
from flask import Flask, render_template, jsonify, Response
from influxdb import InfluxDBClient
import pandas as pd
import plotly.graph_objs as go
from plotly.subplots import make_subplots
from werkzeug.middleware.proxy_fix import ProxyFix

_API_CACHE = {}
_CACHE_TTL_SEC = 15.0
STOCKHOLM_TZ = ZoneInfo("Europe/Stockholm")


# -------------------------
# Timestamp / cache / serialize helpers
# -------------------------
def _to_utc_timestamp(ts):
    """Parse Influx time to UTC pandas Timestamp, or None if invalid/epoch."""
    if ts is None or (isinstance(ts, float) and math.isnan(ts)):
        return None
    try:
        dt = pd.to_datetime(ts, utc=True)
        if pd.isna(dt):
            return None
        # Influx multi-field last() often returns epoch 0 — treat as missing
        if dt.timestamp() <= 0 or dt.year <= 1970:
            return None
        return dt
    except Exception:
        return None


def format_data_timestamp(ts):
    """Format Influx UTC timestamp as Stockholm local YYYY/MM/DD HH:MM:SS."""
    dt = _to_utc_timestamp(ts)
    if dt is None:
        return None
    return dt.tz_convert(STOCKHOLM_TZ).strftime("%Y/%m/%d %H:%M:%S")


def max_timestamp(values):
    """Latest formatted Stockholm timestamp from DataFrames and/or raw times."""
    latest = None
    for item in values:
        candidates = []
        if item is None:
            continue
        if hasattr(item, "empty"):
            if item.empty or "time" not in item.columns:
                continue
            candidates = item["time"].dropna().unique()
        else:
            candidates = [item]
        for t in candidates:
            dt = _to_utc_timestamp(t)
            if dt is None:
                continue
            if latest is None or dt > _to_utc_timestamp(latest):
                latest = t
    return format_data_timestamp(latest)


def slide_timestamp_info(*sources, labels=None):
    """
    Pick display timestamp and warn if sources disagree.

    sources: DataFrames (with time col) and/or raw Influx time values
    labels: optional names (e.g. HG / LG) aligned with sources
    Returns (stockholm_display_ts, warning_or_None)
    """
    collected = []  # (label, raw_ts, utc_dt)

    for i, src in enumerate(sources):
        lab = labels[i] if labels and i < len(labels) else f"src{i}"
        if src is None:
            continue
        if hasattr(src, "empty"):
            if getattr(src, "empty", True) or "time" not in getattr(src, "columns", []):
                continue
            for t in src["time"].dropna().unique():
                dt = _to_utc_timestamp(t)
                if dt is not None:
                    collected.append((lab, t, dt))
        else:
            dt = _to_utc_timestamp(src)
            if dt is not None:
                collected.append((lab, src, dt))

    if not collected:
        return None, None

    by_key = {}
    for lab, raw, dt in collected:
        key = dt.isoformat()
        slot = by_key.setdefault(key, {"labels": set(), "raw": raw, "dt": dt})
        slot["labels"].add(lab)

    latest_raw = max(collected, key=lambda x: x[2])[1]
    display = format_data_timestamp(latest_raw)

    if len(by_key) <= 1:
        return display, None

    parts = []
    for key in sorted(by_key.keys()):
        info = by_key[key]
        labs = ",".join(sorted(info["labels"]))
        parts.append(f"{labs}={format_data_timestamp(info['raw'])}")

    warning = "Timestamp mismatch: " + "; ".join(parts)
    return display, warning


def cache_get(key):
    hit = _API_CACHE.get(key)
    if not hit:
        return None
    expires, body = hit
    if time.monotonic() > expires:
        _API_CACHE.pop(key, None)
        return None
    return body


def cache_set(key, body, ttl=_CACHE_TTL_SEC):
    _API_CACHE[key] = (time.monotonic() + ttl, body)


def fig_to_jsonable(fig):
    """Serialize Plotly figure using plain JSON lists (no binary bdata)."""
    for tr in fig.data:
        for attr in ("x", "y"):
            val = getattr(tr, attr, None)
            if val is None:
                continue
            if hasattr(val, "tolist"):
                setattr(tr, attr, val.tolist())
            elif not isinstance(val, list):
                setattr(tr, attr, list(val))
    # engine=json avoids orjson binary packing (plain arrays, smaller CPU)
    return json.loads(fig.to_json(engine="json"))


def latest_batch_time(measurement, where_sql=""):
    """Timestamp of the newest point (single-field last — avoids epoch-0 bug)."""
    where = f"WHERE {where_sql}" if where_sql else ""
    query = f'SELECT last("value") FROM "{measurement}" {where}'
    try:
        result = client.query(query)
        for p in result.get_points():
            t = p.get("time")
            if format_data_timestamp(t) is not None:
                return t
    except Exception as e:
        print(f"BATCH TIME ERROR ({measurement}):", e)
    return None


def map_query(fn, items):
    """Apply fn over items (sequential — shared Influx client is not thread-safe)."""
    return [fn(x) for x in items]


def apply_md_layout(fig, md_label, n_channels=12, x_range=None, y_range=None,
                    show_hg_lg_legend=True):
    """Shared layout: tight fit, channel titles, outer ticks, dark theme."""
    title_text = md_label
    if show_hg_lg_legend:
        title_text = (
            f"{md_label}"
            f"<span style='font-size:10px; color:#aaa'>"
            f"&nbsp;&nbsp;<span style='color:#FF4444'>● HG</span>"
            f"&nbsp;<span style='color:#00E5FF'>● LG</span></span>"
        )

    fig.update_layout(
        autosize=True,
        height=None,
        width=None,
        showlegend=False,
        title=dict(
            text=title_text,
            x=0.5,
            xanchor="center",
            font=dict(size=13, color="white"),
            pad=dict(t=0, b=0),
        ),
        margin=dict(l=28, r=6, t=32, b=20),
        plot_bgcolor="#111111",
        paper_bgcolor="#111111",
        font=dict(color="white", size=9),
        hovermode="closest",
    )

    # Keep subplot titles readable; do not restyle paper/title annotations
    for ann in fig.layout.annotations:
        if getattr(ann, "text", None) and str(ann.text).startswith("CH"):
            ann.font = dict(size=10, color="#cccccc")

    # Outer-edge ticks only (scale without clutter)
    for i in range(n_channels):
        row = i // 6 + 1
        col = i % 6 + 1
        x_kwargs = dict(
            showticklabels=(row == 2),
            ticks="outside" if row == 2 else "",
            tickfont=dict(size=8, color="#aaaaaa"),
            showgrid=True,
            gridcolor="#333333",
            zeroline=False,
            row=row,
            col=col,
        )
        if x_range is not None:
            x_kwargs["range"] = x_range
        fig.update_xaxes(**x_kwargs)

        y_kwargs = dict(
            showticklabels=(col == 1),
            ticks="outside" if col == 1 else "",
            tickfont=dict(size=8, color="#aaaaaa"),
            showgrid=True,
            gridcolor="#333333",
            zeroline=False,
            row=row,
            col=col,
        )
        if y_range is not None:
            y_kwargs["range"] = y_range
        fig.update_yaxes(**y_kwargs)

    return fig


def add_subplot_metric(fig, row, col, text):
    """Compact metric label inside a subplot (top-left)."""
    fig.add_annotation(
        text=text,
        x=0.03,
        y=0.97,
        xref="x domain",
        yref="y domain",
        xanchor="left",
        yanchor="top",
        showarrow=False,
        font=dict(size=8, color="#dddddd"),
        bgcolor="rgba(0,0,0,0.45)",
        borderpad=2,
        row=row,
        col=col,
    )

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
    """Latest ADC linearity batch for one gain (exact-time read, not full-history last())."""
    ts = latest_batch_time("ADC_Linearity_Samples", f"\"gain\"='{gain}'")
    if ts is None:
        return pd.DataFrame(), None

    query = f"""
    SELECT "value","std","adc_input"
    FROM "ADC_Linearity_Samples"
    WHERE "gain"='{gain}' AND time = '{ts}'
    GROUP BY "channel","gain","step"
    """
    result = client.query(query)
    rows = []

    for (_, tags), points in result.items():
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
                "std": p.get("std", 0) or 0,
                "time": ts,
            })

    return pd.DataFrame(rows), ts


# -------------------------
# Query CIS samples
# -------------------------
def query_cis_samples(gain):
    """Latest CIS sample batch for one gain."""
    ts = latest_batch_time("CIS_Samples", f"\"gain\"='{gain}'")
    if ts is None:
        return pd.DataFrame(), None

    # Logger uses event=0 for the live CIS pulse; skip event cardinality in GROUP BY
    query = f"""
    SELECT "value"
    FROM "CIS_Samples"
    WHERE "gain"='{gain}' AND time = '{ts}' AND "event"='0'
    GROUP BY "channel","sample"
    """
    result = client.query(query)
    all_points = []

    for (_, tags), points in result.items():
        if tags is None:
            continue
        channel = tags.get("channel")
        sample = int(tags.get("sample", 0))
        if sample < 0 or sample > 15:
            continue
        for p in points:
            all_points.append({
                "channel": channel,
                "sample": sample,
                "value": p["value"],
                "time": ts,
            })

    return pd.DataFrame(all_points), ts

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
    ts = latest_batch_time("CIS_Linearity_Samples", f"\"gain\"='{gain}'")
    if ts is None:
        return pd.DataFrame(), None

    query = f"""
    SELECT "value","dac_charge"
    FROM "CIS_Linearity_Samples"
    WHERE "gain"='{gain}' AND time = '{ts}'
    GROUP BY "channel","gain","step"
    """
    result = client.query(query)
    rows = []

    for (_, tags), points in result.items():
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
                "value": p["value"],
                "time": ts,
            })

    return pd.DataFrame(rows), ts




def query_integrator_lin_samples():
    ts = latest_batch_time("Integrator_Linearity_Samples")
    if ts is None:
        return pd.DataFrame(), None

    query = f"""
    SELECT "value","dac_charge"
    FROM "Integrator_Linearity_Samples"
    WHERE time = '{ts}'
    GROUP BY "channel","step"
    """
    result = client.query(query)
    rows = []

    for (_, tags), points in result.items():
        if tags is None:
            continue
        channel = tags.get("channel")
        step = int(tags.get("step"))
        for p in points:
            rows.append({
                "channel": channel,
                "step": step,
                "dac_charge": p["dac_charge"],
                "value": p["value"],
                "time": ts,
            })

    return pd.DataFrame(rows), ts


# -------------------------
# Query CIS phase-scan samples (pulse reconstruction)
# -------------------------
PHASE_SCAN_NS_PER_SAMPLE = 25.0
PHASE_SCAN_NS_PER_PHASE = 25.0 / 32.0


def phase_sample_to_t_ns(sample, phase):
    """Reconstructed time axis: sample×25 + (31−phase)×(25/32) ns."""
    return float(sample) * PHASE_SCAN_NS_PER_SAMPLE + (
        31.0 - float(phase)
    ) * PHASE_SCAN_NS_PER_PHASE


def _query_cis_phase_scan_gain(gain):
    ts = latest_batch_time("CIS_Phase_Scan_Samples", f"\"gain\"='{gain}'")
    if ts is None:
        return [], None

    # event is always 0 in the logger; omit from GROUP BY for fewer series keys
    query = f"""
    SELECT "value"
    FROM "CIS_Phase_Scan_Samples"
    WHERE "gain"='{gain}' AND time = '{ts}' AND "event"='0'
    GROUP BY "channel","phase-31","sample"
    """
    try:
        result = client.query(query)
    except Exception as e:
        print(f"CIS PHASE SCAN QUERY ERROR ({gain}):", e)
        return [], None

    rows = []
    for (_, tags), points in result.items():
        if tags is None:
            continue
        channel = tags.get("channel")
        phase = int(tags.get("phase-31", 0))
        sample = int(tags.get("sample", 0))
        for p in points:
            rows.append({
                "channel": channel,
                "gain": gain,
                "phase": phase,
                "sample": sample,
                "value": p["value"],
                "time": ts,
                "t_ns": phase_sample_to_t_ns(sample, phase),
            })
    return rows, ts


def query_cis_phase_scan_samples():
    """Latest CIS_Phase_Scan_Samples batches for HG and LG (parallel)."""
    results = map_query(_query_cis_phase_scan_gain, ["HG", "LG"])
    rows = []
    times = []
    for gain_rows, ts in results:
        rows.extend(gain_rows)
        if ts is not None:
            times.append(ts)

    df = pd.DataFrame(rows)
    return df, max_timestamp(times)


# -------------------------
# Plot builders
# -------------------------

CHANNEL_OVERLAY_COLORS = [
    "#e6194b", "#3cb44b", "#ffe119", "#4363d8", "#f58231", "#911eb4",
    "#42d4f4", "#f032e6", "#bfef45", "#fabed4", "#469990", "#dcbeff",
]


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
        subplot_titles=[f"CH{i}" for i in range(12)],
        horizontal_spacing=0.03,
        vertical_spacing=0.10,
    )

    for i, full_ch in enumerate(channels):
        row = i // 6 + 1
        col = i % 6 + 1

        ch_hg = df_hg[df_hg["channel"] == full_ch].sort_values("adc_input")
        ch_lg = df_lg[df_lg["channel"] == full_ch].sort_values("adc_input")

        x_hg = ch_hg["adc_input"].tolist()
        x_lg = ch_lg["adc_input"].tolist()
        hg_samples = ch_hg["value"].tolist()
        lg_samples = ch_lg["value"].tolist()

        hg_std = ch_hg["std"].tolist() if "std" in ch_hg.columns else [0] * len(hg_samples)
        lg_std = ch_lg["std"].tolist() if "std" in ch_lg.columns else [0] * len(lg_samples)

        # Linear fit
        if hg_samples:
            slope_hg, intercept_hg, r2_hg, maxdev_hg = linear_fit(x_hg, hg_samples)
            fit_hg = [slope_hg * x + intercept_hg for x in x_hg]
        else:
            slope_hg, r2_hg, fit_hg, maxdev_hg = 0, 0, [], 0

        if lg_samples:
            slope_lg, intercept_lg, r2_lg, maxdev_lg = linear_fit(x_lg, lg_samples)
            fit_lg = [slope_lg * x + intercept_lg for x in x_lg]
        else:
            slope_lg, r2_lg, fit_lg, maxdev_lg = 0, 0, [], 0

        # HG trace
        fig.add_trace(go.Scatter(
            x=x_hg,
            y=hg_samples,
            error_y=dict(type='data', array=hg_std, visible=True),
            mode='markers',
            marker=dict(size=4, color='#FF4444'),
            hovertemplate=(
                "Input: %{x}<br>Value: %{y}<br>"
                f"Slope: {slope_hg:.3f}<br>"
                f"R²: {r2_hg:.3f}<br>"
                f"Max dev: {maxdev_hg:.1f}<extra>HG</extra>"
            ),
            showlegend=False
        ), row=row, col=col)

        # HG fit line
        fig.add_trace(go.Scatter(
            x=x_hg,
            y=fit_hg,
            mode='lines',
            line=dict(color='#66FF66', width=1),
            showlegend=False
        ), row=row, col=col)

        # LG trace
        fig.add_trace(go.Scatter(
            x=x_lg,
            y=lg_samples,
            error_y=dict(type='data', array=lg_std, visible=True),
            mode='markers',
            marker=dict(size=4, color='#00E5FF'),
            hovertemplate=(
                "Input: %{x}<br>Value: %{y}<br>"
                f"Slope: {slope_lg:.3f}<br>"
                f"R²: {r2_lg:.3f}<br>"
                f"Max dev: {maxdev_lg:.1f}<extra>LG</extra>"
            ),
            showlegend=False
        ), row=row, col=col)

        # LG fit line
        fig.add_trace(go.Scatter(
            x=x_lg,
            y=fit_lg,
            mode='lines',
            line=dict(color='#66FF66', width=1),
            showlegend=False
        ), row=row, col=col)

        if hg_samples or lg_samples:
            add_subplot_metric(
                fig, row, col,
                f"Δ {maxdev_hg:.0f}/{maxdev_lg:.0f}"
            )

    apply_md_layout(fig, md_label, x_range=[0, 4096], y_range=[0, 4096])
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
        subplot_titles=[f"CH{i}" for i in range(12)],
        horizontal_spacing=0.03,
        vertical_spacing=0.10,
    )

    for i, full_ch in enumerate(channels):
        row = i // 6 + 1
        col = i % 6 + 1

        ch_hg = df_hg[df_hg["channel"] == full_ch].sort_values("dac_charge")
        ch_lg = df_lg[df_lg["channel"] == full_ch].sort_values("dac_charge")

        x_hg = ch_hg["dac_charge"].tolist()
        x_lg = ch_lg["dac_charge"].tolist()
        hg_samples = ch_hg["value"].tolist()
        lg_samples = ch_lg["value"].tolist()

        if hg_samples:
            slope_hg, intercept_hg, r2_hg, maxdev_hg = linear_fit(x_hg, hg_samples)
            fit_hg = [slope_hg * x + intercept_hg for x in x_hg]
        else:
            slope_hg, r2_hg, fit_hg, maxdev_hg = 0, 0, [], 0

        if lg_samples:
            slope_lg, intercept_lg, r2_lg, maxdev_lg = linear_fit(x_lg, lg_samples)
            fit_lg = [slope_lg * x + intercept_lg for x in x_lg]
        else:
            slope_lg, r2_lg, fit_lg, maxdev_lg = 0, 0, [], 0

        # HG trace
        fig.add_trace(go.Scatter(
            x=x_hg,
            y=hg_samples,
            mode="markers",
            marker=dict(color='#FF4444', size=4),
            hovertemplate=(
                "DAC: %{x}<br>Value: %{y}<br>"
                f"Slope: {slope_hg:.3f}<br>"
                f"R²: {r2_hg:.3f}<br>"
                f"Max dev: {maxdev_hg:.1f}<extra>HG</extra>"
            ),
            showlegend=False
        ), row=row, col=col)

        fig.add_trace(go.Scatter(
            x=x_hg,
            y=fit_hg,
            mode="lines",
            line=dict(color='#66FF66', width=1),
            showlegend=False
        ), row=row, col=col)

        # LG trace
        fig.add_trace(go.Scatter(
            x=x_lg,
            y=lg_samples,
            mode="markers",
            marker=dict(color='#00E5FF', size=4),
            hovertemplate=(
                "DAC: %{x}<br>Value: %{y}<br>"
                f"Slope: {slope_lg:.3f}<br>"
                f"R²: {r2_lg:.3f}<br>"
                f"Max dev: {maxdev_lg:.1f}<extra>LG</extra>"
            ),
            showlegend=False
        ), row=row, col=col)

        fig.add_trace(go.Scatter(
            x=x_lg,
            y=fit_lg,
            mode="lines",
            line=dict(color='#66FF66', width=1),
            showlegend=False
        ), row=row, col=col)

        if hg_samples or lg_samples:
            add_subplot_metric(
                fig, row, col,
                f"Δ {maxdev_hg:.0f}/{maxdev_lg:.0f}"
            )

    apply_md_layout(fig, md_label, x_range=[0, 4096], y_range=[0, 4096])
    return fig

def make_cis_combined(df_hg, df_lg, md_label, meta_crc):
    """
    Combined CIS pulse plot (HG + LG) for one MD label.
    Fully responsive to MD box size.
    X-axis range: 0-15, Y-axis auto.
    """
    channels = [f"{md_label}_CH{i}" for i in range(12)]
    crc_axes = []

    fig = make_subplots(
        rows=2,
        cols=6,
        subplot_titles=[f"CH{i}" for i in range(12)],
        horizontal_spacing=0.03,
        vertical_spacing=0.10,
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

        x_hg = ch_hg["sample"].tolist()
        x_lg = ch_lg["sample"].tolist()

        # HG trace
        fig.add_trace(go.Scatter(
            x=x_hg,
            y=hg_samples,
            mode="markers+lines",
            marker=dict(color='#FF4444', size=4),
            line=dict(color='#FF4444', width=1),
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
            x=x_lg,
            y=lg_samples,
            mode="markers+lines",
            marker=dict(color='#00E5FF', size=4),
            line=dict(color='#00E5FF', width=1),
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
            fig.add_vline(x=peak_idx_hg, line=dict(color='#FF4444', width=1, dash="dot"), row=row, col=col)

        # LG peak line
        if peak_idx_lg > 0:
            fig.add_vline(x=peak_idx_lg, line=dict(color='#00E5FF', width=1, dash="dot"), row=row, col=col)

        # HG FWHM
        if fwhm_hg > 0:
            fig.add_shape(
                type="rect",
                x0=peak_idx_hg - fwhm_hg / 2,
                x1=peak_idx_hg + fwhm_hg / 2,
                y0=0,
                y1=max(hg_samples) if hg_samples else 4096,
                fillcolor="#FF4444",
                opacity=0.15,
                line_width=0,
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
                fillcolor="#00E5FF",
                opacity=0.15,
                line_width=0,
                row=row,
                col=col
            )

        delta_crc = meta_crc.get(full_ch, {}).get("delta_crc", 0)
        if hg_samples or lg_samples:
            crc_flag = " CRC!" if delta_crc > 0 else ""
            add_subplot_metric(
                fig, row, col,
                f"Pk {peak_hg:.0f}/{peak_lg:.0f}{crc_flag}"
            )

        # CRC error highlight (borders applied after shared layout)
        if delta_crc > 0:
            y_top = max(
                max(hg_samples) if hg_samples else 0,
                max(lg_samples) if lg_samples else 0,
                1,
            )
            fig.add_shape(
                type="rect",
                x0=0,
                x1=15,
                y0=0,
                y1=y_top,
                fillcolor="rgba(255,80,80,0.15)",
                opacity=1.0,
                layer="below",
                line_width=0,
                row=row,
                col=col
            )
            crc_axes.append((row, col))

    apply_md_layout(fig, md_label, x_range=[0, 15], y_range=None)

    for row, col in crc_axes:
        fig.update_xaxes(showline=True, linewidth=2, linecolor="#FF5555", mirror=True, row=row, col=col)
        fig.update_yaxes(showline=True, linewidth=2, linecolor="#FF5555", mirror=True, row=row, col=col)

    return fig



def make_integrator_lin_combined(df, md_label):
    """
    Integrator linearity plot (single curve per channel)
    """
    channels = [f"{md_label}_CH{i}" for i in range(12)]

    fig = make_subplots(
        rows=2,
        cols=6,
        subplot_titles=[f"CH{i}" for i in range(12)],
        horizontal_spacing=0.03,
        vertical_spacing=0.10,
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
            marker=dict(size=4, color='#FFA500'),
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
            line=dict(color='#66FF66', width=1),
            showlegend=False
        ), row=row, col=col)

        if y:
            add_subplot_metric(
                fig, row, col,
                f"Δ {maxdev:.0f}  R² {r2:.3f}"
            )

    apply_md_layout(
        fig, md_label,
        x_range=[0, 4096],
        y_range=[0, 65535],
        show_hg_lg_legend=False,
    )
    return fig


def make_cis_phase_recon_plot(df, md_label):
    """
    Per MD: two stacked plots (LG on top, HG below), channels overlapped.
    Time axis from phase scan: t_ns = sample×25 + (31−phase)×(25/32).
    Legend sits below both plots.
    """
    channels = [f"{md_label}_CH{i}" for i in range(12)]
    md_df = df[df["channel"].isin(channels)]

    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.08,
        subplot_titles=("LG", "HG"),
        row_heights=[0.5, 0.5],
    )

    if md_df.empty:
        fig.update_layout(
            title_text=md_label,
            paper_bgcolor="#111111",
            plot_bgcolor="#111111",
            font=dict(color="white"),
        )
        return fig

    md_df = md_df.sort_values(["channel", "gain", "t_ns"])
    grouped = md_df.groupby(["channel", "gain"], sort=False)

    # Row 1 = LG, row 2 = HG
    for gain, row in (("LG", 1), ("HG", 2)):
        for i, full_ch in enumerate(channels):
            key = (full_ch, gain)
            if key not in grouped.groups:
                continue
            gdf = grouped.get_group(key)
            if len(gdf) > 320:
                gdf = gdf.iloc[::2]

            color = CHANNEL_OVERLAY_COLORS[i % len(CHANNEL_OVERLAY_COLORS)]
            fig.add_trace(
                go.Scattergl(
                    x=gdf["t_ns"].tolist(),
                    y=gdf["value"].tolist(),
                    mode="lines",
                    name=f"CH{i}",
                    legendgroup=f"CH{i}",
                    showlegend=(gain == "LG"),  # one legend entry per channel
                    line=dict(color=color, width=1.4),
                    opacity=0.85,
                    hovertemplate=(
                        f"{full_ch} {gain}<br>"
                        "t: %{x:.2f} ns<br>"
                        "ADC: %{y:.1f}<extra></extra>"
                    ),
                ),
                row=row,
                col=1,
            )

    fig.update_layout(
        autosize=True,
        height=None,
        width=None,
        title=dict(
            text=f"{md_label}<span style='font-size:10px; color:#aaa'>"
                 "&nbsp;&nbsp;phase-scan recon</span>",
            x=0.5,
            xanchor="center",
            font=dict(size=13, color="white"),
            pad=dict(t=0, b=0),
        ),
        margin=dict(l=42, r=10, t=36, b=52),
        plot_bgcolor="#111111",
        paper_bgcolor="#111111",
        font=dict(color="white", size=9),
        hovermode="closest",
        legend=dict(
            orientation="h",
            yanchor="top",
            y=-0.12,
            xanchor="center",
            x=0.5,
            font=dict(size=9),
            bgcolor="rgba(0,0,0,0)",
            tracegroupgap=2,
        ),
    )

    fig.update_annotations(font=dict(size=11, color="#cccccc"))

    for row in (1, 2):
        fig.update_xaxes(
            showgrid=True,
            gridcolor="#333333",
            zeroline=False,
            tickfont=dict(size=9, color="#aaaaaa"),
            range=[0, 400],
            row=row,
            col=1,
        )
        fig.update_yaxes(
            title=dict(text="ADC", font=dict(size=10, color="#cccccc")),
            showgrid=True,
            gridcolor="#333333",
            zeroline=False,
            tickfont=dict(size=9, color="#aaaaaa"),
            row=row,
            col=1,
        )

    # X label only on bottom (HG) panel
    fig.update_xaxes(
        title=dict(text="t [ns]", font=dict(size=10, color="#cccccc")),
        row=2,
        col=1,
    )
    return fig


# -------------------------
# Routes
# -------------------------
@app.route("/")
def dashboard():
    # Avoid a heavy Influx round-trip just to build the empty MD grid
    md_labels = [f"PprGTH_MD{i}" for i in range(1, 5)]
    test_name = ""
    return render_template("dashboard.html", md_labels=md_labels, test_name=test_name)


def _md_labels_from_df(df):
    if df is None or df.empty or "channel" not in df.columns:
        return []
    return sorted(set(
        ch.split("_MD")[0] + "_MD" + ch.split("_MD")[1][0]
        for ch in df["channel"].unique()
    ))


def _build_figures(md_labels, builder):
    return [fig_to_jsonable(builder(md)) for md in md_labels]


def _cached_payload(cache_key, producer):
    cached = cache_get(cache_key)
    if cached is not None:
        return Response(cached, mimetype="application/json")
    payload = producer()
    body = json.dumps(payload, separators=(",", ":"))
    cache_set(cache_key, body)
    return Response(body, mimetype="application/json")


@app.route("/api/cis_all")
def api_cis_all():
    def produce():
        (df_hg, ts_hg), (df_lg, ts_lg) = map_query(
            query_cis_samples, ["HG", "LG"]
        )
        meta_crc = query_cis_metadata()
        md_labels = _md_labels_from_df(df_hg)
        data_ts, ts_warn = slide_timestamp_info(
            df_hg, df_lg, labels=["HG", "LG"]
        )
        return {
            "timestamp": data_ts,
            "timestamp_warning": ts_warn,
            "figures": _build_figures(
                md_labels,
                lambda md: make_cis_combined(df_hg, df_lg, md, meta_crc),
            ),
        }

    try:
        return _cached_payload("cis_all_v2", produce)
    except Exception as e:
        print("CIS ALL ERROR:", e)
        return jsonify({"error": str(e)}), 500


@app.route("/api/adc_linearity_all")
def api_adc_lin_all():
    def produce():
        (df_hg, ts_hg), (df_lg, ts_lg) = map_query(
            query_adc_lin_samples, ["HG", "LG"]
        )
        md_labels = _md_labels_from_df(df_hg)
        data_ts, ts_warn = slide_timestamp_info(
            df_hg, df_lg, labels=["HG", "LG"]
        )
        return {
            "timestamp": data_ts,
            "timestamp_warning": ts_warn,
            "figures": _build_figures(
                md_labels,
                lambda md: make_adc_lin_combined(df_hg, df_lg, md),
            ),
        }

    try:
        return _cached_payload("adc_linearity_all_v2", produce)
    except Exception as e:
        print("ADC LIN ALL ERROR:", e)
        return jsonify({"error": str(e)}), 500


@app.route("/api/cis_linearity_all")
def api_cis_lin_all():
    def produce():
        (df_hg, ts_hg), (df_lg, ts_lg) = map_query(
            query_cis_lin_samples, ["HG", "LG"]
        )
        md_labels = _md_labels_from_df(df_hg)
        data_ts, ts_warn = slide_timestamp_info(
            df_hg, df_lg, labels=["HG", "LG"]
        )
        return {
            "timestamp": data_ts,
            "timestamp_warning": ts_warn,
            "figures": _build_figures(
                md_labels,
                lambda md: make_cis_lin_combined(df_hg, df_lg, md),
            ),
        }

    try:
        return _cached_payload("cis_linearity_all_v2", produce)
    except Exception as e:
        print("CIS LIN ALL ERROR:", e)
        return jsonify({"error": str(e)}), 500


@app.route("/api/integrator_linearity_all")
def api_integrator_lin_all():
    def produce():
        df, ts = query_integrator_lin_samples()
        if df.empty:
            return {"timestamp": None, "timestamp_warning": None, "figures": []}
        md_labels = _md_labels_from_df(df)
        data_ts, ts_warn = slide_timestamp_info(df, labels=["data"])
        return {
            "timestamp": data_ts,
            "timestamp_warning": ts_warn,
            "figures": _build_figures(
                md_labels,
                lambda md: make_integrator_lin_combined(df, md),
            ),
        }

    try:
        return _cached_payload("integrator_linearity_all_v2", produce)
    except Exception as e:
        print("INTEGRATOR LIN ALL ERROR:", e)
        return jsonify({"error": str(e)}), 500


@app.route("/api/cis_phase_recon_all")
def api_cis_phase_recon_all():
    def produce():
        df, _data_ts = query_cis_phase_scan_samples()
        if df.empty:
            return {"timestamp": None, "timestamp_warning": None, "figures": []}
        md_labels = _md_labels_from_df(df)
        df_hg = df[df["gain"] == "HG"] if "gain" in df.columns else df
        df_lg = df[df["gain"] == "LG"] if "gain" in df.columns else df.iloc[0:0]
        data_ts, ts_warn = slide_timestamp_info(
            df_hg, df_lg, labels=["HG", "LG"]
        )
        return {
            "timestamp": data_ts,
            "timestamp_warning": ts_warn,
            "figures": _build_figures(
                md_labels,
                lambda md: make_cis_phase_recon_plot(df, md),
            ),
        }

    try:
        return _cached_payload("cis_phase_recon_all_v2", produce)
    except Exception as e:
        print("CIS PHASE RECON ALL ERROR:", e)
        return jsonify({"error": str(e)}), 500


# -------------------------
# Run server
# -------------------------
if __name__ == "__main__":
    flask_conf = secrets["flask"]
    app.run(host=flask_conf["host"], port=flask_conf["port"], debug=True)