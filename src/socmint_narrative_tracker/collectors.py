import hashlib
import json
import re
from datetime import datetime, timedelta

import pandas as pd
import requests
import scrapetube
from bs4 import BeautifulSoup
from ddgs import DDGS

SAMPLE_PATH = "data/sample_acme_bank.json"


def _md5(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()[:12]


def _parse_count(raw_text: str) -> int | None:
    """Convert strings like '14.2K', '1.5M', or '1,204 views' into an integer."""
    if not raw_text:
        return None
    clean = raw_text.strip().upper().replace(",", "")
    m = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*([KM]?)", clean)
    if not m:
        return None
    val = float(m.group(1))
    suffix = m.group(2)
    if suffix == "K":
        val *= 1_000
    elif suffix == "M":
        val *= 1_000_000
    return int(val)


def scrape_youtube_live(topic: str, limit: int = 15) -> list[dict]:
    results = []
    try:
        videos = scrapetube.get_search(topic, limit=limit)
        now = datetime.utcnow()
        for idx, v in enumerate(videos):
            vid_id = v.get("videoId", f"yt_{idx}")
            title = v.get("title", {}).get("runs", [{}])[0].get("text", "")
            channel = (
                v.get("ownerText", {})
                .get("runs", [{}])[0]
                .get("text", f"yt_channel_{idx}")
            )
            view_text = v.get("viewCountText", {}).get("simpleText", "")
            thumbs = v.get("thumbnail", {}).get("thumbnails", [{}])
            thumb_url = thumbs[-1].get("url", "") if thumbs else ""

            results.append(
                {
                    "post_id": f"yt_{vid_id}",
                    "platform": "YouTube",
                    "author_handle": f"@{re.sub(r'[^a-zA-Z0-9_]', '', channel) or 'yt_user'}",
                    "author_created_at": None,
                    "avatar_hash": _md5(channel),
                    "timestamp": (now - timedelta(hours=idx * 2 + 1)).isoformat(),
                    "text": title or f"Video coverage regarding {topic}",
                    "media_urls": [
                        u
                        for u in (
                            thumb_url,
                            f"https://www.youtube.com/watch?v={vid_id}",
                        )
                        if u
                    ],
                    "media_type": "video",
                    "engagement": _parse_count(view_text),
                    "amplified_handle": "",
                    "link": f"https://www.youtube.com/watch?v={vid_id}",
                }
            )
    except Exception as e:
        print(f"[WARN] YouTube scrape error: {e}")
    return results


def scrape_telegram_and_x_live(topic: str, limit: int = 15) -> list[dict]:
    results = []
    now = datetime.utcnow()
    headers = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64)"}

    try:
        with DDGS() as ddgs:
            # 1. Telegram public posts
            for idx, hit in enumerate(
                ddgs.text(f'site:t.me "{topic}"', max_results=limit)
            ):
                href = hit.get("href", "")
                body = hit.get("body", "") or hit.get("title", "")
                m = re.search(r"t\.me/(?:s/)?([a-zA-Z0-9_]+)", href)
                handle = f"@{m.group(1)}" if m else f"@tg_channel_{idx}"
                ts_iso = (now - timedelta(hours=idx * 2 + 1)).isoformat()
                engagement = None

                if "t.me/s/" in href:
                    try:
                        resp = requests.get(href, headers=headers, timeout=5)
                        if resp.status_code == 200:
                            soup = BeautifulSoup(resp.text, "html.parser")
                            t_tag = soup.select_one(".tgme_widget_message_date time")
                            if t_tag and t_tag.get("datetime"):
                                ts_iso = t_tag["datetime"][:19]
                            v_tag = soup.select_one(".tgme_widget_message_views")
                            if v_tag:
                                engagement = _parse_count(v_tag.get_text(strip=True))
                    except Exception:
                        pass

                results.append(
                    {
                        "post_id": f"tg_live_{idx}",
                        "platform": "Telegram",
                        "author_handle": handle,
                        "author_created_at": None,
                        "avatar_hash": _md5(handle),
                        "timestamp": ts_iso,
                        "text": body[:400],
                        "media_urls": [],
                        "media_type": "text",
                        "engagement": engagement,
                        "amplified_handle": "",
                        "link": href,
                    }
                )

            # 2. X public posts
            for idx, hit in enumerate(
                ddgs.text(
                    f'(site:x.com OR site:twitter.com) "{topic}"', max_results=limit
                )
            ):
                href = hit.get("href", "")
                body = hit.get("body", "") or hit.get("title", "")
                m = re.search(r"(?:x\.com|twitter\.com)/([a-zA-Z0-9_]+)", href)
                handle = f"@{m.group(1)}" if m else f"@x_user_{idx}"

                results.append(
                    {
                        "post_id": f"x_live_{idx}",
                        "platform": "X",
                        "author_handle": handle,
                        "author_created_at": None,
                        "avatar_hash": _md5(handle),
                        "timestamp": (now - timedelta(hours=idx * 2 + 1)).isoformat(),
                        "text": body[:400],
                        "media_urls": [],
                        "media_type": "text",
                        "engagement": None,
                        "amplified_handle": "",
                        "link": href,
                    }
                )
    except Exception as e:
        print(f"[WARN] Live OSINT error: {e}")
    return results


def collect_posts(
    topic: str,
    start_date: str,
    end_date: str,
    platforms: list[str],
    mode: str = "sample",
) -> pd.DataFrame:
    if mode == "sample":
        with open(SAMPLE_PATH, "r", encoding="utf-8") as f:
            posts = json.load(f)
    else:
        posts = []
        if "YouTube" in platforms:
            posts.extend(scrape_youtube_live(topic))
        if "Telegram" in platforms or "X" in platforms:
            posts.extend(scrape_telegram_and_x_live(topic))

    df = pd.DataFrame(posts)
    if df.empty:
        return df

    # Normalize legacy sample files if they still have engagement_total
    if "engagement" not in df.columns:
        df["engagement"] = df.get("engagement_total", None)
    df = df.drop(
        columns=["likes", "shares", "views", "engagement_total"], errors="ignore"
    )

    df = df[df["platform"].isin(platforms)].copy()
    df["timestamp_dt"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    df["author_created_dt"] = pd.to_datetime(
        df["author_created_at"], utc=True, errors="coerce"
    )

    start_dt = pd.to_datetime(start_date, utc=True)
    end_dt = pd.to_datetime(end_date, utc=True) + pd.Timedelta(days=1)
    mask = (df["timestamp_dt"] >= start_dt) & (df["timestamp_dt"] <= end_dt)
    if mask.sum() > 0:
        df = df[mask].copy()

    return df.sort_values("timestamp_dt").reset_index(drop=True)
