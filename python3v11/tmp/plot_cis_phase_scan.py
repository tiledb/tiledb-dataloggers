#!/root/apps/tiledb-dataloggers/python3v11/.pyenv/bin/python
"""Plot the latest InfluxDB CIS_Phase_Scan_Samples run (one Plotly figure per MD)."""

from __future__ import annotations

import argparse
import re
import webbrowser
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
from influxdb import InfluxDBClient

_BC_NS = 25.0
_PHASE_STEPS = 32
_PHASE_STEP_NS = _BC_NS / _PHASE_STEPS
_CHANNEL_RE = re.compile(r"^(?P<label>.+)_MD(?P<md>\d+)_CH(?P<ch>\d+)$")

_ADC_COLORS = [
    "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728",
    "#9467bd", "#8c564b", "#e377c2", "#7f7f7f",
    "#bcbd22", "#17becf", "#aec7e8", "#ffbb78",
]


def t_ns(sample: int, phase: int) -> float:
    """Phase-reversed time axis used by the CIS pulse-scan plugin."""
    return sample * _BC_NS + (_PHASE_STEPS - 1 - (phase & 0x1F)) * _PHASE_STEP_NS


def connect(args) -> InfluxDBClient:
    return InfluxDBClient(
        host=args.host,
        port=args.port,
        username=args.username,
        password=args.password,
        database=args.database,
    )


def _last_time(client: InfluxDBClient, gain: str | None = None) -> datetime | None:
    where = f'WHERE "gain"=\'{gain}\'' if gain else ""
    q = f'SELECT last("value") FROM "CIS_Phase_Scan_Samples" {where}'
    result = client.query(q)
    points = list(result.get_points())
    if not points:
        return None
    return pd.to_datetime(points[0]["time"], utc=True).to_pydatetime()


def _iso_z(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _fetch_at_time(client: InfluxDBClient, when: datetime) -> list[dict]:
    iso = _iso_z(when)
    q = f'''
    SELECT "value"
    FROM "CIS_Phase_Scan_Samples"
    WHERE time = '{iso}'
    GROUP BY *
    '''
    result = client.query(q)
    rows = []
    for (_measurement, tags), points in result.items():
        if not tags:
            continue
        for p in points:
            rows.append({
                "time": pd.to_datetime(p["time"], utc=True),
                "channel": tags.get("channel"),
                "gain": tags.get("gain"),
                "event": str(tags.get("event", "0")),
                "sample": int(tags.get("sample", 0)),
                "phase": int(tags.get("phase-31", 0)),
                "value": float(p["value"]),
            })
    return rows


def fetch_latest_scan(client: InfluxDBClient) -> pd.DataFrame:
    """Load the latest LG+HG write pair (each gain uses one shared timestamp)."""
    t_hg = _last_time(client, "HG")
    t_lg = _last_time(client, "LG")
    candidates = [t for t in (t_lg, t_hg) if t is not None]
    if not candidates:
        raise SystemExit("No CIS_Phase_Scan_Samples data in InfluxDB.")

    # One logger cycle writes LG then HG with two close timestamps
    newest = max(candidates)
    times = sorted({
        t for t in candidates
        if abs((newest - t).total_seconds()) <= 30 * 60
    })

    print("Fetching timestamps:", ", ".join(_iso_z(t) for t in times))
    rows = []
    for t in times:
        chunk = _fetch_at_time(client, t)
        print(f"  {_iso_z(t)} -> {len(chunk)} points")
        rows.extend(chunk)

    if not rows:
        raise SystemExit("Latest timestamps returned no points.")

    df = pd.DataFrame(rows)
    parsed = df["channel"].str.extract(_CHANNEL_RE)
    if parsed.isna().any().any():
        bad = df.loc[parsed.isna().any(axis=1), "channel"].unique()
        raise SystemExit(f"Unrecognised channel tag(s): {list(bad)}")

    df["md"] = parsed["md"].astype(int)
    df["ch"] = parsed["ch"].astype(int)
    df["label"] = parsed["label"]
    df["t_ns"] = [
        t_ns(s, ph) for s, ph in zip(df["sample"].tolist(), df["phase"].tolist())
    ]
    return df.sort_values(["md", "ch", "gain", "t_ns", "phase", "sample"])


def figure_for_md(df_md: pd.DataFrame, md: int, label: str) -> go.Figure:
    fig = go.Figure()
    for ch in sorted(df_md["ch"].unique()):
        color = _ADC_COLORS[int(ch) % len(_ADC_COLORS)]
        for gain, dash, symbol, opacity in (
            ("HG", "solid", "circle", 1.0),
            ("LG", "dot", "diamond", 0.85),
        ):
            sub = df_md[(df_md["ch"] == ch) & (df_md["gain"] == gain)]
            if sub.empty:
                continue
            sub = sub.sort_values(["t_ns", "phase", "sample"])
            fig.add_trace(go.Scatter(
                x=sub["t_ns"],
                y=sub["value"],
                mode="lines+markers",
                name=f"CH{ch} {gain}",
                line=dict(color=color, width=1.5, dash=dash),
                marker=dict(color=color, size=4, symbol=symbol, opacity=opacity),
                opacity=opacity,
                customdata=sub[["sample", "phase"]].to_numpy(),
                hovertemplate=(
                    f"MD{md} CH{ch} {gain}<br>"
                    "t %{x:.3f} ns<br>ADC %{y}"
                    "<br>sample %{customdata[0]} · phase %{customdata[1]}"
                    "<extra></extra>"
                ),
            ))

    times = ", ".join(sorted({t.isoformat() for t in df_md["time"].unique()}))
    fig.update_layout(
        title=f"CIS Phase Scan · {label} MD{md}<br><sup>{times}</sup>",
        xaxis_title="t [ns]  ·  sample×25 + (31−phase)×(25/32)",
        yaxis_title="ADC counts",
        template="plotly_white",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
        hovermode="closest",
        height=700,
    )
    return fig


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="192.168.0.200")
    parser.add_argument("--port", type=int, default=8086)
    parser.add_argument("--username", default="tiledb")
    parser.add_argument("--password", default="T1le-db-word!")
    parser.add_argument("--database", default="tiledb")
    parser.add_argument(
        "--outdir",
        default=str(Path(__file__).resolve().parent / "cis_phase_scan_plots"),
        help="Directory for HTML plots",
    )
    parser.add_argument("--no-open", action="store_true",
                        help="Do not open plots in the browser")
    args = parser.parse_args()

    client = connect(args)
    print("Querying latest CIS_Phase_Scan_Samples...")
    df = fetch_latest_scan(client)
    label = df["label"].iloc[0]
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    print(f"Loaded {len(df)} points ({label})")
    print(f"  times : {sorted(df['time'].unique())}")
    print(f"  MDs   : {sorted(df['md'].unique())}")
    print(f"  gains : {sorted(df['gain'].unique())}")

    paths = []
    for md in sorted(df["md"].unique()):
        fig = figure_for_md(df[df["md"] == md], int(md), label)
        path = outdir / f"cis_phase_scan_{label}_MD{md}.html"
        fig.write_html(str(path), include_plotlyjs="cdn")
        paths.append(path)
        print(f"Wrote {path}")

    if not args.no_open:
        for path in paths:
            webbrowser.open(path.as_uri())


if __name__ == "__main__":
    main()
