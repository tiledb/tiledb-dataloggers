from flask import Flask, render_template, jsonify
from influxdb import InfluxDBClient
import pandas as pd
import plotly.graph_objs as go
from plotly.subplots import make_subplots
import json
from werkzeug.middleware.proxy_fix import ProxyFix

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
# Query CIS samples
# -------------------------
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




# -------------------------
# Query CIS metadata
# -------------------------
def query_cis_metadata():

    query = """
    SELECT last("hg_center") AS hg_center,
           last("lg_center") AS lg_center,
           last("delta_crc") AS delta_crc
    FROM "CIS"
    GROUP BY *
    """

    result = client.query(query)

    meta = {}

    for (measurement, tags), points in result.items():

        if tags is None:
            continue

        # Find the tag that contains "PprGTH"
        md_tag = None
        for k in tags.keys():
            if "PprGTH" in k:
                md_tag = k
                break

        if md_tag is None:
            continue

        md_label = md_tag.replace(" ", "_")      # PprGTH_MD1
        ch = tags[md_tag]                        # CH0

        full_channel = f"{md_label}_{ch}"        # PprGTH_MD1_CH0

        for p in points:

            meta[full_channel] = {
                "hg_center": p.get("hg_center"),
                "lg_center": p.get("lg_center"),
                "delta_crc": p.get("delta_crc", 0) or 0
            }

    return meta


# -------------------------
# Plot builder
# -------------------------
def make_md_subplot(df_hg, df_lg, md_label, meta):

    channels = [f"{md_label}_CH{i}" for i in range(12)]

    fig = make_subplots(
        rows=2,
        cols=6,
        subplot_titles=["" for _ in channels]
    )

    for i, full_ch in enumerate(channels):

        row = i // 6 + 1
        col = i % 6 + 1

        ch_hg = df_hg[df_hg["channel"] == full_ch]
        ch_lg = df_lg[df_lg["channel"] == full_ch]

        # HG points
        fig.add_trace(
            go.Scatter(
                x=ch_hg["sample"],
                y=ch_hg["value"],
                mode="markers",
                marker=dict(color='#FF0000', size=5),
                hovertemplate="Sample: %{x}<br>Value: %{y}<extra>HG</extra>"
            ),
            row=row,
            col=col
        )

        # LG points
        fig.add_trace(
            go.Scatter(
                x=ch_lg["sample"],
                y=ch_lg["value"],
                mode="markers",
                marker=dict(color='#00FFFF', size=5),
                hovertemplate="Sample: %{x}<br>Value: %{y}<extra>LG</extra>"
            ),
            row=row,
            col=col
        )

        # -------------------------
        # Metadata
        # -------------------------
        meta_ch = meta.get(full_ch, {})

        hg_center = meta_ch.get("hg_center")
        lg_center = meta_ch.get("lg_center")
        delta_crc = meta_ch.get("delta_crc", 0)

        # HG center line
        if isinstance(hg_center, (int, float)):
            fig.add_vline(
                x=float(hg_center),
                line=dict(color='#FF0000', width=1),
                row=row,
                col=col
            )

        # LG center line
        if isinstance(lg_center, (int, float)):
            fig.add_vline(
                x=float(lg_center),
                line=dict(color='#00FFFF', width=1),
                row=row,
                col=col
            )

        # CRC error highlight
        if delta_crc and delta_crc > 0:

            # gray overlay
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

            # red border
            fig.update_xaxes(
                showline=True,
                linewidth=2,
                linecolor="red",
                row=row,
                col=col
            )

            fig.update_yaxes(
                showline=True,
                linewidth=2,
                linecolor="red",
                row=row,
                col=col
            )

    # -------------------------
    # Layout
    # -------------------------
    fig.update_layout(

        height=400,
        width=None,
        autosize=True,

        showlegend=False,

        title_text=md_label,
        title_x=0.5,

        margin=dict(l=5, r=5, t=25, b=5),

        plot_bgcolor="#111111",
        paper_bgcolor="#111111",

        font=dict(color="white")
    )

    # Hide ticks
    for axis in fig.layout:

        if isinstance(fig.layout[axis], go.layout.XAxis):

            fig.layout[axis].update(
                showticklabels=False,
                title_text="",
                showgrid=True,
                gridcolor="#333"
            )

        if isinstance(fig.layout[axis], go.layout.YAxis):

            fig.layout[axis].update(
                range=[0, 4096],
                showticklabels=False,
                title_text="",
                showgrid=True,
                gridcolor="#333"
            )

    return fig


# -------------------------
# Routes
# -------------------------
@app.route("/")
def dashboard():

    df_hg = query_latest_data("HG")

    md_labels = sorted(set(
        ch.split("_MD")[0] + "_MD" + ch.split("_MD")[1][0]
        for ch in df_hg["channel"].unique()
    ))

    return render_template(
        "dashboard.html",
        md_labels=md_labels
    )


@app.route("/api/combined")
def api_combined():

    try:

        df_hg = query_latest_data("HG")
        df_lg = query_latest_data("LG")

        meta = query_cis_metadata()

        md_labels = sorted(set(
            ch.split("_MD")[0] + "_MD" + ch.split("_MD")[1][0]
            for ch in df_hg["channel"].unique()
        ))

        figs_json = []

        for md in md_labels:

            fig = make_md_subplot(df_hg, df_lg, md, meta)

            figs_json.append(json.loads(fig.to_json()))

        return jsonify(figs_json)

    except Exception as e:

        print("API ERROR:", e)

        return jsonify({"error": str(e)}), 500


# -------------------------
# Run server
# -------------------------
if __name__ == "__main__":

    flask_conf = secrets["flask"]

    app.run(
        host=flask_conf["host"],
        port=flask_conf["port"],
        debug=True
    )