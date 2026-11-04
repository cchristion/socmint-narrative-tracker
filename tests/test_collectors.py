import json

import pandas as pd
import pytest

from socmint_narrative_tracker.collectors import (
    _md5,
    _parse_count,
    collect_posts,
)


def test_md5():
    result = _md5("OpenAI")

    assert isinstance(result, str)
    assert len(result) == 12
    assert result == _md5("OpenAI")


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("14.2K", 14200),
        ("1.5M", 1500000),
        ("1,204 views", 1204),
        ("500", 500),
        ("", None),
        ("Unknown", None),
        (None, None),
    ],
)
def test_parse_count(raw, expected):
    assert _parse_count(raw) == expected


@pytest.fixture
def sample_posts(tmp_path, monkeypatch):
    posts = [
        {
            "post_id": "yt_001",
            "platform": "YouTube",
            "author_handle": "@channel1",
            "author_created_at": None,
            "avatar_hash": "abc123",
            "timestamp": "2026-01-10T10:00:00",
            "text": "AI developments",
            "media_urls": [],
            "media_type": "video",
            "engagement": 1500,
            "amplified_handle": "",
            "link": "https://youtube.com/watch?v=001",
        },
        {
            "post_id": "tg_001",
            "platform": "Telegram",
            "author_handle": "@channel2",
            "author_created_at": None,
            "avatar_hash": "def456",
            "timestamp": "2026-01-11T10:00:00",
            "text": "AI discussion",
            "media_urls": [],
            "media_type": "text",
            "engagement": 500,
            "amplified_handle": "",
            "link": "https://t.me/channel2/1",
        },
        {
            "post_id": "x_001",
            "platform": "X",
            "author_handle": "@user1",
            "author_created_at": None,
            "avatar_hash": "ghi789",
            "timestamp": "2026-01-12T10:00:00",
            "text": "AI trends",
            "media_urls": [],
            "media_type": "text",
            "engagement": None,
            "amplified_handle": "",
            "link": "https://x.com/user1/status/1",
        },
    ]

    data_file = tmp_path / "synthetic_posts.json"
    data_file.write_text(json.dumps(posts), encoding="utf-8")

    monkeypatch.setattr(
        "socmint_narrative_tracker.collectors.SAMPLE_PATH",
        str(data_file),
    )

    return posts


def test_collect_sample_posts(sample_posts):
    df = collect_posts(
        topic="AI",
        start_date="2026-01-01",
        end_date="2026-01-31",
        platforms=["YouTube", "Telegram", "X"],
        mode="sample",
    )

    assert isinstance(df, pd.DataFrame)
    assert len(df) == 3
    assert set(df["platform"]) == {"YouTube", "Telegram", "X"}


def test_platform_filtering(sample_posts):
    df = collect_posts(
        topic="AI",
        start_date="2026-01-01",
        end_date="2026-01-31",
        platforms=["YouTube"],
        mode="sample",
    )

    assert len(df) == 1
    assert df.iloc[0]["platform"] == "YouTube"


def test_date_filtering(sample_posts):
    df = collect_posts(
        topic="AI",
        start_date="2026-01-11",
        end_date="2026-01-11",
        platforms=["YouTube", "Telegram", "X"],
        mode="sample",
    )

    assert len(df) == 1
    assert df.iloc[0]["platform"] == "Telegram"


def test_sorted_timestamps(sample_posts):
    df = collect_posts(
        topic="AI",
        start_date="2026-01-01",
        end_date="2026-01-31",
        platforms=["YouTube", "Telegram", "X"],
        mode="sample",
    )

    assert df["timestamp_dt"].is_monotonic_increasing


def test_empty_sample_file(tmp_path, monkeypatch):
    data_file = tmp_path / "empty.json"
    data_file.write_text("[]", encoding="utf-8")

    monkeypatch.setattr(
        "socmint_narrative_tracker.collectors.SAMPLE_PATH",
        str(data_file),
    )

    df = collect_posts(
        topic="AI",
        start_date="2026-01-01",
        end_date="2026-01-31",
        platforms=["YouTube"],
        mode="sample",
    )

    assert isinstance(df, pd.DataFrame)
    assert df.empty


def test_no_matching_platform(sample_posts):
    df = collect_posts(
        topic="AI",
        start_date="2026-01-01",
        end_date="2026-01-31",
        platforms=["Instagram"],
        mode="sample",
    )

    assert df.empty


def test_no_matching_date_returns_empty(sample_posts):
    df = collect_posts(
        topic="AI",
        start_date="2027-01-01",
        end_date="2027-01-31",
        platforms=["YouTube", "Telegram", "X"],
        mode="sample",
    )

    assert df.empty


def test_live_scraping_failure(monkeypatch):
    def mock_scrape(*args, **kwargs):
        raise RuntimeError("Network unavailable")

    monkeypatch.setattr(
        "socmint_narrative_tracker.collectors.scrape_youtube_live",
        mock_scrape,
    )

    with pytest.raises(RuntimeError, match="Network unavailable"):
        collect_posts(
            topic="AI",
            start_date="2026-01-01",
            end_date="2026-12-31",
            platforms=["YouTube"],
            mode="live",
        )
