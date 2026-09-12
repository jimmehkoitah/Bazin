"""URL normalisation and platform detection for candidates found via web search or bios."""

from __future__ import annotations

import re
from urllib.parse import parse_qs, urlparse, urlunparse

SOCIAL_HOSTS = {
    "instagram.com": "instagram",
    "tiktok.com": "tiktok",
    "facebook.com": "facebook",
    "fb.com": "facebook",
    "youtube.com": "youtube",
    "youtu.be": "youtube",
    "pinterest.com": "pinterest",
    "pinterest.fr": "pinterest",
    "etsy.com": "etsy",
    "anka.africa": "afrikrea",
    "afrikrea.com": "afrikrea",
    "amazon.com": "amazon",
    "amazon.fr": "amazon",
    "jumia.sn": "jumia",
    "jumia.com.ng": "jumia",
    "jumia.ci": "jumia",
    "coinafrique.com": "coinafrique",
    "expat-dakar.com": "expat_dakar",
    "jiji.ng": "jiji",
    "jiji.sn": "jiji",
    "snapchat.com": "snapchat",
    "wa.me": "whatsapp",
    "whatsapp.com": "whatsapp",
    "google.com": "google_maps",
    "goo.gl": "google_maps",
    "yelp.com": "yelp",
}

TRACKING_PARAMS = {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "igsh", "igshid", "fbclid", "ref", "hl", "lang"}


def _host(url: str) -> str:
    return (urlparse(url).hostname or "").lower().removeprefix("www.").removeprefix("m.").removeprefix("fr-fr.")


def clean_url(url: str) -> str:
    """Drop tracking parameters and fragments; keep scheme and host lowercase."""
    if not url.startswith("http"):
        url = "https://" + url
    p = urlparse(url)
    q = parse_qs(p.query, keep_blank_values=False)
    q = {k: v for k, v in q.items() if k not in TRACKING_PARAMS}
    query = "&".join(f"{k}={v[0]}" for k, v in sorted(q.items()))
    host = (p.hostname or "").lower()
    path = re.sub(r"/+$", "", p.path) or "/"
    return urlunparse((p.scheme.lower() or "https", host, path, "", query, ""))


def resolve_platform(url: str) -> tuple[str, str, str | None]:
    """Return (platform, canonical_url, handle). Unknown hosts are 'website'."""
    url = clean_url(url)
    host = _host(url)
    platform = "website"
    for h, plat in SOCIAL_HOSTS.items():
        if host == h or host.endswith("." + h):
            platform = plat
            break
    path = urlparse(url).path
    handle: str | None = None
    if platform == "instagram":
        m = re.match(r"^/([A-Za-z0-9_.]+)/?(?:$|\?)", path)
        if m and m.group(1) not in ("p", "reel", "reels", "explore", "stories", "tv", "accounts"):
            handle = m.group(1).lower()
            url = f"https://www.instagram.com/{handle}/"
    elif platform == "tiktok":
        m = re.match(r"^/@([A-Za-z0-9_.]+)", path)
        if m:
            handle = m.group(1).lower()
            if "/video/" not in path:
                url = f"https://www.tiktok.com/@{handle}"
    elif platform == "facebook":
        m = re.match(r"^/([A-Za-z0-9.\-]+)/?$", path)
        if m and m.group(1) not in ("groups", "pages", "profile.php", "people", "watch", "marketplace", "events", "photo", "photo.php", "share", "reel"):
            handle = m.group(1).lower()
            url = f"https://www.facebook.com/{handle}/"
    elif platform == "youtube":
        m = re.match(r"^/@([A-Za-z0-9_.\-]+)", path)
        if m:
            handle = m.group(1).lower()
    elif platform == "etsy":
        m = re.match(r"^/shop/([A-Za-z0-9]+)", path)
        if m:
            handle = m.group(1).lower()
            url = f"https://www.etsy.com/shop/{m.group(1)}"
    return platform, url, handle


def is_profile_url(platform: str, url: str) -> bool:
    """True for a profile/shop/page URL rather than a single post."""
    path = urlparse(url).path
    if platform == "instagram":
        return not any(seg in path for seg in ("/p/", "/reel/", "/reels/", "/tv/"))
    if platform == "tiktok":
        return "/video/" not in path
    if platform == "facebook":
        return not any(seg in path for seg in ("/posts/", "/photos/", "/videos/", "/reel/", "permalink"))
    if platform == "youtube":
        return "/watch" not in path and "/shorts/" not in path
    if platform == "etsy":
        return "/shop/" in path
    return True
