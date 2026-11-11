
from __future__ import annotations

import sys
import textwrap
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st


# ============================================================
# 1. PROJECT CONFIGURATION
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[3]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.acale.dashboard.dashboard_utils import (
    extract_batch_count,
    extract_packet_count,
    find_dicts_with_key,
    load_csv_rows,
    load_json,
    safe_number,
)


st.set_page_config(
    page_title="SFEA| Smart Agriculture Security",
    page_icon="🌱",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ============================================================
# 2. PROFESSIONAL DASHBOARD THEME
# ============================================================

st.markdown(
    """
    <style>

    /* Main background */

    .stApp {
        background-color: #f4f8f5;
        color: #20352b;
    }

    .block-container {
        max-width: 1450px;
        padding-top: 1.8rem;
        padding-bottom: 2rem;
    }

    /* Main title */

    h1 {
        color: #14532d !important;
        font-weight: 800 !important;
        font-size: 2.3rem !important;
        letter-spacing: -1px;
    }

    h2, h3 {
        color: #166534 !important;
        font-weight: 700 !important;
    }

    /* Sidebar */

    section[data-testid="stSidebar"] {
        background: linear-gradient(
            180deg,
            #123b2a 0%,
            #1b5138 100%
        );
    }

    section[data-testid="stSidebar"] * {
        color: #ffffff !important;
    }

    section[data-testid="stSidebar"] button {
        background-color: #e2f5e9 !important;
        color: #14532d !important;
        border-radius: 10px !important;
        font-weight: 700 !important;
        border: none !important;
    }

    /* Metric cards */

    div[data-testid="stMetric"] {
        background: #ffffff;
        border: 1px solid #dcebe0;
        border-left: 5px solid #22a05a;
        padding: 18px;
        border-radius: 14px;
        box-shadow: 0 4px 14px rgba(20, 83, 45, 0.07);
        min-height: 120px;
    }

    div[data-testid="stMetricLabel"] {
        color: #52705d !important;
        font-weight: 600 !important;
    }

    div[data-testid="stMetricValue"] {
        color: #14532d !important;
        font-weight: 800 !important;
    }

    /* Chart cards */

    div[data-testid="stPlotlyChart"] {
        background: #ffffff;
        padding: 12px;
        border-radius: 14px;
        border: 1px solid #e0ebe3;
        box-shadow: 0 3px 12px rgba(20, 83, 45, 0.05);
    }

    /* Expanders */

    div[data-testid="stExpander"] {
        background: #ffffff;
        border: 1px solid #dcebe0;
        border-radius: 12px;
        margin-bottom: 12px;
    }

    /* Buttons */

    .stButton > button {
        border-radius: 10px;
        font-weight: 600;
        border: 1px solid #198754;
        transition: 0.2s;
    }

    .stButton > button:hover {
        background-color: #198754;
        color: white;
    }

    /* Information boxes */

    div[data-testid="stAlert"] {
        border-radius: 12px;
    }

    /* Dividers */

    hr {
        border-color: #d7e7dc;
    }

    /* Captions */

    .stCaption {
        color: #718477 !important;
    }

    /* Tables */

    div[data-testid="stDataFrame"] {
        border: 1px solid #dcebe0;
        border-radius: 12px;
    }

    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# 3. DATA FILE LOCATIONS
# ============================================================

DATA_DIR = PROJECT_ROOT / "data"

SIMULATION_DIR = DATA_DIR / "simulation_results"

PERFORMANCE_DIR = PROJECT_ROOT / "results" / "performance"

SENSOR_CSV = DATA_DIR / "sensor_data" / "sensor_readings.csv"

CLASSIFICATION_JSON = (
    SIMULATION_DIR / "context_classification.json"
)

ENCRYPTED_JSON = (
    SIMULATION_DIR / "encrypted_sensor_packets.json"
)

BATCHES_JSON = (
    SIMULATION_DIR / "transmission_batches.json"
)

FOG_JSON = (
    SIMULATION_DIR / "fog_verification_results.json"
)

REPORT_JSON = (
    PERFORMANCE_DIR / "phase7_performance_report.json"
)

METRICS_CSV = (
    PERFORMANCE_DIR / "phase7_metrics.csv"
)


# ============================================================
# 4. LOAD PHASE 2–7 DATA
# ============================================================

sensor_rows = load_csv_rows(SENSOR_CSV)

classification = load_json(CLASSIFICATION_JSON)

encrypted = load_json(ENCRYPTED_JSON)

batches = load_json(BATCHES_JSON)

fog = load_json(FOG_JSON)

report = load_json(REPORT_JSON)

metric_rows = load_csv_rows(METRICS_CSV)


# ============================================================
# 5. HELPER FUNCTIONS
# ============================================================

def find_metric(data, possible_names):
    """
    Search recursively for a metric in nested JSON structures.
    Returns None when the metric is unavailable.
    """

    if isinstance(data, dict):

        for name in possible_names:
            if name in data:
                return data[name]

        for value in data.values():

            result = find_metric(value, possible_names)

            if result is not None:
                return result

    elif isinstance(data, list):

        for item in data:

            result = find_metric(item, possible_names)

            if result is not None:
                return result

    return None


def show_metric(label, value, suffix=""):
    """Display a metric card safely."""

    if value is None:
        st.metric(label, "—")
        return

    if isinstance(value, (int, float)):
        formatted = f"{value:,.3f}" if isinstance(value, float) else f"{value:,}"
        st.metric(label, formatted + suffix)
    else:
        st.metric(label, str(value) + suffix)


def get_context_counts(data):
    """Count NORMAL, CRITICAL and RECOVERY states."""

    records = find_dicts_with_key(data, "context_state")

    counts = {
        "NORMAL": 0,
        "CRITICAL": 0,
        "RECOVERY": 0,
        "OTHER": 0,
    }

    for record in records:

        state = str(
            record.get("context_state", "OTHER")
        ).upper()

        if state in counts:
            counts[state] += 1
        else:
            counts["OTHER"] += 1

    return counts


def create_chart_layout(fig):
    """Apply a consistent chart appearance."""

    fig.update_layout(
        paper_bgcolor="#ffffff",
        plot_bgcolor="#ffffff",
        font=dict(
            family="Arial",
            color="#334b3b",
            size=12,
        ),
        margin=dict(
            l=20,
            r=20,
            t=55,
            b=35,
        ),
        title_font=dict(
            size=17,
            color="#14532d",
        ),
        showlegend=False,
    )

    fig.update_xaxes(
        showgrid=False,
        zeroline=False,
    )

    fig.update_yaxes(
        gridcolor="#e7eee9",
        zeroline=False,
    )

    return fig


# ============================================================
# 6. SIDEBAR
# ============================================================

with st.sidebar:

    st.markdown(
        """
        <div style="text-align:center; padding:20px 5px;">
            <div style="font-size:48px;">🌱</div>
            <h2 style="color:white !important; margin-bottom:0;">
                ACALE
            </h2>
            <p style="color:#d1ead9 !important;">
                Agricultural IoT Security
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.divider()

    st.subheader("Dashboard Controls")

    st.write("📊 Simulation Data: Phases 2–7")

    if st.button(
        "↻ Refresh Dashboard",
        use_container_width=True,
    ):
        st.rerun()

    st.divider()

    st.markdown("### System Information")

    st.write("🔐 Encryption: ChaCha20-Poly1305")

    st.write("🔑 Key Derivation: HKDF-SHA256")

    st.write("📡 Communication: Adaptive Batching")

    st.write("🛡️ Security: Fog Verification")

    st.divider()

    st.caption(
        "ACALE is a software simulation project. "
        "This dashboard reads existing project outputs."
    )




# ============================================================
# 7. DASHBOARD HEADER
# ============================================================

header_html = """
<div style="background:linear-gradient(120deg,#123b2a,#23834e);padding:30px;border-radius:18px;margin-bottom:20px;">
<h1 style="color:#white;font-size:34px;margin:0;">🌱 SFEA Dashboard</h1>
<p style="color:white;font-size:16px;margin-top:12px;">
Security-Floor Energy-Safe Adaption for Authentication Encryption in Edge-Fog Agriculture IOT
</p>
<p style="color:#c8e8d3;font-size:13px;margin-top:12px;">
Secure Sensor Monitoring | Context Awareness | Adaptive Transmission | Fog Verification
</p>
</div>
"""

st.markdown(header_html, unsafe_allow_html=True)

st.info(
    "This dashboard displays software simulation results. "
    "Energy-saving values are illustrative estimates, "
    "not measurements from physical IoT hardware."
)



# ============================================================
# 8. EXTRACT METRICS
# ============================================================

sensor_count = len(sensor_rows)

encrypted_count = extract_packet_count(encrypted)

if encrypted_count == 0:
    encrypted_count = find_metric(
        report,
        ["encrypted_packets", "packet_count"],
    ) or 0

batch_count = extract_batch_count(batches)

trans_before = find_metric(
    report,
    [
        "transmissions_before",
        "transmission_events_before",
    ],
)

trans_after = find_metric(
    report,
    [
        "transmissions_after",
        "transmission_events_after",
    ],
)

# Use existing simulation counts if report values are absent.

if trans_before is None:
    trans_before = sensor_count

if trans_after is None:
    trans_after = batch_count

# Calculate transmission reduction automatically.

reduction = find_metric(
    report,
    [
        "transmission_reduction_percent",
        "transmission_reduction",
        "reduction_percent",
    ],
)

if reduction is None and safe_number(trans_before) > 0:

    reduction = (
        (
            safe_number(trans_before)
            - safe_number(trans_after)
        )
        / safe_number(trans_before)
    ) * 100

energy_saving = find_metric(
    report,
    [
        "estimated_energy_saving_percent",
        "energy_saving_percent",
        "energy_saving",
    ],
)

enc_latency = find_metric(
    report,
    [
        "mean_encryption_ms",
        "mean_encryption_latency_ms",
        "encryption_mean_ms",
    ],
)

dec_latency = find_metric(
    report,
    [
        "mean_decryption_ms",
        "mean_decryption_latency_ms",
        "decryption_mean_ms",
    ],
)

fog_accept = find_metric(
    report,
    [
        "fog_accepted",
        "accepted_packets",
        "accepted",
    ],
)

fog_reject = find_metric(
    report,
    [
        "fog_rejected",
        "rejected_packets",
        "rejected",
    ],
)

fog_replay = find_metric(
    report,
    [
        "fog_replayed",
        "replayed_packets",
        "replay_detected",
        "replayed",
    ],
)

# Read fog verification output if a metric is missing in Phase 7.

if fog_accept is None:
    fog_accept = find_metric(
        fog,
        ["accepted", "accepted_count", "accepted_packets"],
    )

if fog_reject is None:
    fog_reject = find_metric(
        fog,
        ["rejected", "rejected_count", "rejected_packets"],
    )

if fog_replay is None:
    fog_replay = find_metric(
        fog,
        ["replayed", "replayed_count", "replay_detected"],
    )


# ============================================================
# 9. SYSTEM OVERVIEW
# ============================================================

st.markdown("## 📊 System Overview")

st.caption(
    "Live visualization of the generated ACALE simulation outputs."
)

c1, c2, c3, c4 = st.columns(4)

with c1:
    show_metric(
        "Sensor Readings",
        sensor_count,
    )

with c2:
    show_metric(
        "Encrypted Packets",
        encrypted_count,
    )

with c3:
    show_metric(
        "Transmission Events",
        trans_after,
    )

with c4:
    show_metric(
        "Transmission Reduction",
        reduction,
        "%",
    )


st.divider()


# ============================================================
# 10. CONTEXT-AWARE CLASSIFICATION
# ============================================================

st.markdown("## 🌿 Context-Aware Classification")

left, right = st.columns([1, 1])

context_counts = get_context_counts(classification)

with left:

    st.markdown("### Sensor Context Distribution")

    if sum(context_counts.values()) > 0:

        context_df = pd.DataFrame({
            "Context State": list(context_counts.keys()),
            "Readings": list(context_counts.values()),
        })

        context_df = context_df[
            context_df["Readings"] > 0
        ]

        fig = px.pie(
            context_df,
            names="Context State",
            values="Readings",
            hole=0.58,
            title="Context Classification",
        )

        fig.update_traces(
            textposition="inside",
            textinfo="percent+label",
        )

        fig.update_layout(
            paper_bgcolor="#ffffff",
            font_color="#334b3b",
            margin=dict(t=55, b=20, l=15, r=15),
        )

        st.plotly_chart(
            fig,
            use_container_width=True,
        )

    else:

        st.warning(
            "Classification data is unavailable. "
            "Check the Phase 3 output file."
        )


with right:

    st.markdown("### Classification Summary")

    st.metric(
        "NORMAL Readings",
        context_counts["NORMAL"],
    )

    st.metric(
        "CRITICAL Readings",
        context_counts["CRITICAL"],
    )

    st.metric(
        "RECOVERY Readings",
        context_counts["RECOVERY"],
    )

    st.caption(
        "These states are prototype context classifications, "
        "not agricultural disease or crop-health diagnoses."
    )


st.divider()


# ============================================================
# 11. ADAPTIVE TRANSMISSION OPTIMIZATION
# ============================================================

st.markdown("## 📡 Adaptive Transmission Optimization")

left, right = st.columns(2)

with left:

    st.markdown("### Transmission Comparison")

    if trans_before is not None and trans_after is not None:

        tx_df = pd.DataFrame({
            "Stage": [
                "Before Optimization",
                "After Optimization",
            ],
            "Transmission Events": [
                safe_number(trans_before),
                safe_number(trans_after),
            ],
        })

        fig = px.bar(
            tx_df,
            x="Stage",
            y="Transmission Events",
            text="Transmission Events",
            title="Transmission Events Before and After Batching",
        )

        fig.update_traces(
            marker_color=["#9ac9a9", "#198754"],
            textposition="outside",
        )

        fig = create_chart_layout(fig)

        st.plotly_chart(
            fig,
            use_container_width=True,
        )

    else:

        st.warning(
            "Transmission comparison is unavailable."
        )


with right:

    st.markdown("### Energy Optimization")

    show_metric(
        "Estimated Energy Saving",
        energy_saving,
        "%",
    )

    show_metric(
        "Transmission Events Saved",
        max(
            0,
            int(safe_number(trans_before) - safe_number(trans_after)),
        ),
    )

    st.success(
        "Adaptive batching reduces the number of transmission "
        "events while preserving the original encrypted packets."
    )

    st.caption(
        "Energy saving is calculated using the project's "
        "illustrative simulation model."
    )


st.divider()


# ============================================================
# 12. SECURITY AND FOG VERIFICATION
# ============================================================

st.markdown("## 🔐 Security and Fog-Node Verification")

s1, s2, s3, s4 = st.columns(4)

with s1:
    show_metric(
        "Accepted Packets",
        fog_accept,
    )

with s2:
    show_metric(
        "Rejected Packets",
        fog_reject,
    )

with s3:
    show_metric(
        "Replay Detected",
        fog_replay,
    )

with s4:
    show_metric(
        "Transmission Batches",
        batch_count,
    )

st.caption(
    "Fog verification checks packet authentication and replay "
    "protection. Successful authentication does not establish "
    "that a sensor reading is truthful."
)

if fog_accept is not None and fog_reject is not None:

    fog_df = pd.DataFrame({
        "Verification Result": [
            "Accepted",
            "Rejected",
        ],
        "Packets": [
            safe_number(fog_accept),
            safe_number(fog_reject),
        ],
    })

    fig = px.bar(
        fog_df,
        x="Verification Result",
        y="Packets",
        text="Packets",
        title="Fog Node Verification Results",
    )

    fig.update_traces(
        marker_color=["#198754", "#dc6b6b"],
        textposition="outside",
    )

    fig = create_chart_layout(fig)

    st.plotly_chart(
        fig,
        use_container_width=True,
    )


st.divider()


# ============================================================
# 13. CRYPTOGRAPHIC PERFORMANCE
# ============================================================

st.markdown("## ⚡ Cryptographic Performance")

t1, t2 = st.columns(2)

with t1:

    st.metric(
        "Mean Encryption API Latency",
        (
            f"{safe_number(enc_latency):.3f} ms"
            if enc_latency is not None
            else "—"
        ),
    )

with t2:

    st.metric(
        "Mean Decryption API Latency",
        (
            f"{safe_number(dec_latency):.3f} ms"
            if dec_latency is not None
            else "—"
        ),
    )

st.caption(
    "These are local software API timings. They depend on the "
    "computer and evaluator implementation; they are not "
    "wireless network latency measurements."
)


st.divider()


# ============================================================
# 14. PHASE 7 PERFORMANCE CHARTS
# ============================================================

st.markdown("## 📈 Performance Analysis")

chart_files = [
    (
        "Transmission Comparison",
        PERFORMANCE_DIR / "transmission_comparison.png",
    ),
    (
        "Cryptographic API Latency",
        PERFORMANCE_DIR / "crypto_latency.png",
    ),
    (
        "Fog Verification",
        PERFORMANCE_DIR / "fog_verification.png",
    ),
]

chart_columns = st.columns(3)

for column, (title, chart_path) in zip(
    chart_columns,
    chart_files,
):

    with column:

        st.markdown(f"### {title}")

        if chart_path.exists():

            st.image(
                str(chart_path),
                use_container_width=True,
            )

        else:

            st.warning(
                "Run Phase 7 to generate this chart."
            )


st.divider()


# ============================================================
# 15. SENSOR DATA EXPLORER
# ============================================================

st.markdown("## 📋 Sensor Data Explorer")

with st.expander(
    "View Sensor Readings",
    expanded=False,
):

    if sensor_rows:

        sensor_df = pd.DataFrame(sensor_rows)

        st.write(
            f"Total sensor records: {len(sensor_df)}"
        )

        st.dataframe(
            sensor_df,
            use_container_width=True,
            hide_index=True,
        )

    else:

        st.warning(
            "Sensor data CSV is unavailable."
        )


# ============================================================
# 16. PERFORMANCE METRICS EXPLORER
# ============================================================

with st.expander(
    "View Phase 7 Performance Metrics",
    expanded=False,
):

    if metric_rows:

        metrics_df = pd.DataFrame(metric_rows)

        st.dataframe(
            metrics_df,
            use_container_width=True,
            hide_index=True,
        )

    else:

        st.info(
            "Phase 7 metrics CSV is unavailable."
        )


# ============================================================
# 17. FILE STATUS
# ============================================================

with st.expander(
    "Project Output File Status",
    expanded=False,
):

    expected_files = [
        SENSOR_CSV,
        CLASSIFICATION_JSON,
        ENCRYPTED_JSON,
        BATCHES_JSON,
        FOG_JSON,
        REPORT_JSON,
        METRICS_CSV,
    ]

    for file_path in expected_files:

        exists = file_path.exists()

        if exists:

            st.success(
                f"Available: {file_path.relative_to(PROJECT_ROOT)}"
            )

        else:

            st.warning(
                f"Missing: {file_path.relative_to(PROJECT_ROOT)}"
            )




# ============================================================
# 18. FOOTER
# ============================================================

st.divider()

footer_html = """
<div style="background:#e4f2e8;padding:25px;border-radius:14px;text-align:center;">
<h3 style="color:#14532d;">🌱 SFEA</h3>
<p style="color:#456653;">Security-Floor Energy-Safe Adaption for Authentication Encryption in Edge-Fog Agriculture IOT</p>
<p style="color:#718477;font-size:12px;">Phase 8 | Interactive Simulation Dashboard</p>
<p style="color:#718477;font-size:11px;">Academic Software Prototype | Not a Physical IoT Deployment</p>
</div>
"""

st.markdown(footer_html, unsafe_allow_html=True)
