from flask import Flask, render_template, jsonify
from influxdb import InfluxDBClient
import pandas as pd
import plotly.graph_objs as go
from plotly.subplots import make_subplots
import json

app = Flask(__name__)
app.debug = True  # enable debug

# --- Load secrets ---
with open("secrets.json") as f:
    secrets = json.load(f)

# InfluxDB client
influx_conf = secrets["influx"]
client = InfluxDBClient(
    host=influx_conf["host"],
    port=influx_conf["port"],
    username=influx_conf["username"],
    password=influx_conf["password"],
    database=influx_conf["database"]
)

# --- Query last event only ---
def query_latest_data(gain):
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

# --- Create MD subplot ---
def make_md_subplot(df_hg, df_lg, md_label):
    channels = [f"{md_label}_CH{i}" for i in range(12)]
    fig = make_subplots(
        rows=2, cols=6,
        subplot_titles=["" for _ in channels]
    )

    for i, full_ch in enumerate(channels):
        row = i // 6 + 1
        col = i % 6 + 1

        # HG bright red, smaller points
        ch_hg = df_hg[df_hg["channel"] == full_ch]
        fig.add_trace(go.Scatter(
            x=ch_hg["sample"],
            y=ch_hg["value"],
            mode="markers",
            marker=dict(color='#FF0000', size=5),
            name=f"{full_ch} HG",
            hovertemplate="Sample: %{x}<br>Value: %{y}<extra>HG</extra>"
        ), row=row, col=col)

        # LG cyan
        ch_lg = df_lg[df_lg["channel"] == full_ch]
        fig.add_trace(go.Scatter(
            x=ch_lg["sample"],
            y=ch_lg["value"],
            mode="markers",
            marker=dict(color='#00FFFF', size=5),
            name=f"{full_ch} LG",
            hovertemplate="Sample: %{x}<br>Value: %{y}<extra>LG</extra>"
        ), row=row, col=col)

    # Layout
    fig.update_layout(
        height=400,
        width=None,
        autosize=True,
        showlegend=False,
        title_text=md_label,
        title_x=0.5,
        margin=dict(l=5,r=5,t=25,b=5),
        plot_bgcolor="#111111",
        paper_bgcolor="#111111",
        font=dict(color="white")
    )

    # Hide axis labels, ticks
    for axis in fig.layout:
        if isinstance(fig.layout[axis], go.layout.XAxis):
            fig.layout[axis].update(showticklabels=False, title_text="", showgrid=True, gridcolor="#333")
        if isinstance(fig.layout[axis], go.layout.YAxis):
            fig.layout[axis].update(range=[0,4096], title_text="", showticklabels=False, showgrid=True, gridcolor="#333")

    return fig

# --- Routes ---
@app.route("/")
def dashboard():
    df_hg = query_latest_data("HG")
    md_labels = sorted(set(
        ch.split("_MD")[0] + "_MD" + ch.split("_MD")[1][0]
        for ch in df_hg["channel"].unique()
    ))
    return render_template("dashboard.html", md_labels=md_labels)

@app.route("/api/combined")
def api_combined():
    df_hg = query_latest_data("HG")
    df_lg = query_latest_data("LG")
    md_labels = sorted(set(
        ch.split("_MD")[0] + "_MD" + ch.split("_MD")[1][0]
        for ch in df_hg["channel"].unique()
    ))
    figs_json = [json.loads(make_md_subplot(df_hg, df_lg, md).to_json()) for md in md_labels]
    return jsonify(figs_json)

# --- Run ---
if __name__ == "__main__":
    flask_conf = secrets["flask"]
    app.run(host=flask_conf["host"], port=flask_conf["port"], debug=True)