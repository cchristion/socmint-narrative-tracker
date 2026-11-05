import hashlib
import json
import os
import re
from datetime import datetime, timedelta

import pandas as pd
import requests
import scrapetube
from bs4 import BeautifulSoup
from ddgs import DDGS

CACHE_DIR = "data/cache"
SAMPLE_PATH = "data/synthetic_posts.json"


def _md5(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()[:12]


def _get_cache_path(topic: str) -> str:
    os.makedirs(CACHE_DIR, exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "_", topic.lower()).strip("_") or "query"
    return os.path.join(CACHE_DIR, f"{slug}.json")


def _parse_count(raw_text: str) -> int | None:
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


def scrape_telegram_and_x_live(
    topic: str, limit: int = 15, platforms: list[str] | None = None
) -> list[dict]:
    results = []
    now = datetime.utcnow()
    headers = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64)"}
    target_platforms = platforms or ["Telegram", "X"]

    try:
        with DDGS() as ddgs:
            if "Telegram" in target_platforms:
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
                                t_tags = soup.select(".tgme_widget_message_date time")
                                if t_tags and t_tags[-1].get("datetime"):
                                    ts_iso = t_tags[-1]["datetime"][:19]
                                v_tags = soup.select(".tgme_widget_message_views")
                                if v_tags:
                                    engagement = _parse_count(
                                        v_tags[-1].get_text(strip=True)
                                    )
                        except Exception:
                            pass

                    results.append(
                        {
                            "post_id": f"tg_{_md5(href or body)}",
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

            if "X" in target_platforms:
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
                            "post_id": f"x_{_md5(href or body)}",
                            "platform": "X",
                            "author_handle": handle,
                            "author_created_at": None,
                            "avatar_hash": _md5(handle),
                            "timestamp": (
                                now - timedelta(hours=idx * 2 + 1)
                            ).isoformat(),
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


def _deduplicate_posts(posts: list[dict]) -> list[dict]:
    deduped = {}
    for p in posts:
        key = (
            p.get("link")
            or p.get("post_id")
            or f"{p.get('platform')}_{p.get('author_handle')}_{_md5(p.get('text', ''))}"
        )
        deduped[key] = p
    return list(deduped.values())


def collect_posts(
    topic: str,
    start_date: str,
    end_date: str,
    platforms: list[str],
    mode: str = "sample",
    force_refresh: bool = False,
) -> pd.DataFrame:
    if mode == "sample":
        with open(SAMPLE_PATH, "r", encoding="utf-8") as f:
            posts = json.load(f)
    else:
        cache_path = _get_cache_path(topic)
        cached_posts = []

        # 1. Load existing cached posts
        if os.path.exists(cache_path) and not force_refresh:
            try:
                with open(cache_path, "r", encoding="utf-8") as f:
                    cached_posts = json.load(f)
            except Exception as e:
                print(f"[WARN] Cache read error ({cache_path}): {e}")

        # 2. Scrape current live posts
        live_posts = []
        if "YouTube" in platforms:
            live_posts.extend(scrape_youtube_live(topic))
        tg_or_x = [p for p in platforms if p in ("Telegram", "X")]
        if tg_or_x:
            live_posts.extend(scrape_telegram_and_x_live(topic, platforms=tg_or_x))

        # 3. Merge cache + freshly scraped posts and deduplicate
        posts = _deduplicate_posts(cached_posts + live_posts)

        if posts:
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(posts, f, indent=2)

    df = pd.DataFrame(posts)
    if df.empty:
        return df

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
