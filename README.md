# SOCMINT Narrative & Coordinated Activity Tracker

An automated multi-platform SOCMINT and disinformation detection module that collects posts across Telegram, X, and YouTube, groups claims into semantic narratives using transformer embeddings (all-MiniLM-L6-v2), traces Patient Zero cross-platform propagation, and attributes coordinated inauthentic behavior (CIB) using graph connected components (networkx).

## Setup

### Prerequisites

- Python 3.12+ and [`uv`](https://docs.astral.sh/uv/) package manager.

### 1. Install Dependencies

```shell
git clone https://github.com/cchristion/socmint-narrative-tracker.git
cd socmint-narrative-tracker
uv sync
```

### 2. Run the Interactive Live Dashboard

```shell
uv run streamlit run app.py
```

- Open `http://localhost:8501` in your browser.
- Enter any **Topic / Keyword / Hashtag**, **Date Range**, and **Target Platforms**.
- Results are automatically exported to:
  - `output/posts.csv` (Structured post telemetry & narrative labels)
  - `output/intelligence_report.json` (Full JSON payload with narratives, coordinated rings, and origins)
  - `output/report.html` (Standalone executive dark-mode HTML report)

## Architecture & Implementation Choices (Deliverables)

### Methodology & Design Decisions

### Tools, Libraries & APIs Used

### How AI Was Used & How Output Was Verified

### Handling Rate Limits, Blocking & Platform Restrictions

### Accuracy: False Positives & False Negatives Found

### Limitations & Assumptions
