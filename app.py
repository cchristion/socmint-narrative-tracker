from datetime import date
import pandas as pd
import plotly.express as px
import streamlit as st

from socmint_narrative_tracker.collectors import collect_posts
from socmint_narrative_tracker.coordination import detect_coordinated_groups
from socmint_narrative_tracker.exporter import export_all_artifacts
from socmint_narrative_tracker.narratives import cluster_narratives
from socmint_narrative_tracker.origin import trace_narrative_origins

st.set_page_config(page_title="SOCMINT & Disinformation Tracker", layout="wide")

st.title("🛡️ SOCMINT Coordinated Activity & Narrative Tracker")
st.caption(
    "Automated Multi-Platform Narrative Clustering, Patient-Zero Attribution & Botnet Graph Detection"
)

with st.sidebar:
    st.header("🔍 Investigation Inputs")
    topic = st.text_input("Topic / Keyword / Hashtag", value="Acme Bank")
    col1, col2 = st.columns(2)
    start_date = col1.date_input("Start Date", value=date(2026, 10, 25))
    end_date = col2.date_input("End Date", value=date.today())

    platforms = st.multiselect(
        "Target Platforms (Pick 2-3)",
        options=["Telegram", "X", "YouTube"],
        default=["Telegram", "X", "YouTube"],
    )
    mode = st.selectbox(
        "Data Source",
        options=["sample", "live"],
        format_func=lambda x: {
            "sample": "Synthetic Benchmark (data/synthetic_posts.json)",
            "live": "Live OSINT Scrapers + Cache (Telegram, X, YouTube)",
        }[x],
    )
    sim_threshold = st.slider(
        "Coordination Text Similarity Threshold", 0.70, 0.98, 0.85, 0.02
    )
    dist_threshold = st.slider("Narrative Clustering Distance", 0.15, 0.60, 0.25, 0.05)

    force_refresh = st.checkbox("🔄 Force Live Refresh (Ignore Cache)", value=False)

    run_btn = st.button(
        "🚀 Run Intelligence Pipeline", type="primary", use_container_width=True
    )

if run_btn or "df" not in st.session_state:
    with st.spinner(
        f"Collecting & analyzing multi-platform telemetry for '{topic}'..."
    ):
        df = collect_posts(
            topic,
            str(start_date),
            str(end_date),
            platforms,
            mode=mode,
            force_refresh=force_refresh,
        )
        if not df.empty:
            df, embeddings, narratives = cluster_narratives(
                df, distance_threshold=dist_threshold, topic=topic
            )
            coord_groups = detect_coordinated_groups(
                df, embeddings, sim_threshold=sim_threshold
            )
            origins = trace_narrative_origins(df)
            paths = export_all_artifacts(topic, df, narratives, coord_groups, origins)
            st.session_state.update(
                {
                    "df": df,
                    "narratives": narratives,
                    "coord_groups": coord_groups,
                    "origins": origins,
                    "paths": paths,
                }
            )
        else:
            st.session_state.pop("df", None)
            st.warning("No posts found for the given criteria.")

if "df" in st.session_state and not st.session_state["df"].empty:
    df = st.session_state["df"]
    narratives = st.session_state["narratives"]
    coord_groups = st.session_state["coord_groups"]
    origins = st.session_state["origins"]
    paths = st.session_state["paths"]

    # Top KPI Metrics
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Posts Collected", len(df))
    m2.metric("Active Narratives Clustered", len(narratives))
    m3.metric("Coordinated Account Rings", len(coord_groups))
    m4.metric("Unique Authors Tracked", df["author_handle"].nunique())

    # 1. Main Narratives & Volume Over Time / Platform
    st.subheader("1. Main Narratives: Volume Over Time & Per Platform")
    c1, c2 = st.columns([3, 2])
    with c1:
        df_plot = df.copy()
        df_plot["Time_Bucket"] = df_plot["timestamp_dt"].dt.floor("h")
        vol_time = (
            df_plot.groupby(["Time_Bucket", "narrative_label"])
            .size()
            .reset_index(name="Posts")
        )
        fig_time = px.bar(
            vol_time,
            x="Time_Bucket",
            y="Posts",
            color="narrative_label",
            title="Narrative Volume Over Time",
        )
        st.plotly_chart(fig_time, use_container_width=True)
    with c2:
        vol_plat = (
            df.groupby(["platform", "narrative_label"]).size().reset_index(name="Posts")
        )
        fig_plat = px.bar(
            vol_plat,
            x="platform",
            y="Posts",
            color="narrative_label",
            barmode="group",
            title="Volume Per Platform",
        )
        st.plotly_chart(fig_plat, use_container_width=True)

    st.dataframe(pd.DataFrame(narratives), use_container_width=True)

    # 2. Coordinated Activity Groups & Evidence
    st.subheader("2. Coordinated Account Rings & Detection Evidence")
    if coord_groups:
        for g in coord_groups:
            with st.expander(
                f"🚨 {g['group_id']} | Confidence: {g['confidence_score']} | {g['account_count']} Accounts across {', '.join(g['platforms'])}",
                expanded=True,
            ):
                st.markdown(f"**Accounts:** `{', '.join(g['accounts'])}`")
                st.markdown(f"**Total Ring Posts:** `{g['post_count']}`")
                st.markdown("**Triggered Coordination Heuristics:**")
                for r in g["reasons"]:
                    st.markdown(f"- `{r}`")
    else:
        st.info("No coordinated groups triggered at the current threshold.")

    # 3. Patient Zero & Cross-Platform Spread
    st.subheader("3. Narrative Origin ('Patient Zero') & Cross-Platform Spread")
    st.dataframe(pd.DataFrame(origins), use_container_width=True)

    # 4. Raw Posts & Export Downloads
    st.subheader("4. Collected Posts & Export Artifacts (JSON / CSV / HTML)")
    dl1, dl2, dl3 = st.columns(3)
    with open(paths["csv"], "rb") as f:
        dl1.download_button(
            "⬇️ Download Posts (CSV)",
            f,
            file_name="posts.csv",
            mime="text/csv",
            use_container_width=True,
        )
    with open(paths["json"], "rb") as f:
        dl2.download_button(
            "⬇️ Download Full Report (JSON)",
            f,
            file_name="intelligence_report.json",
            mime="application/json",
            use_container_width=True,
        )
    with open(paths["html"], "rb") as f:
        dl3.download_button(
            "⬇️ Download Standalone HTML Report",
            f,
            file_name="report.html",
            mime="text/html",
            use_container_width=True,
        )

    st.dataframe(
        df[
            [
                "timestamp",
                "platform",
                "author_handle",
                "narrative_label",
                "text",
                "media_type",
                "engagement",
                "link",
            ]
        ],
        use_container_width=True,
    )
