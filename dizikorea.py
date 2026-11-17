#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import os
import time
import html
import json
import logging
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from yt_dlp import YoutubeDL


# ==========================================================
# MIRTI68 - DIZIKOREA M3U OTOMATIK CEKICI
# ==========================================================

BASE_URL = "https://dizikorea3.com"

OUTPUT_FILE = "dizikorea.m3u"
BACKUP_FILE = "dizikorea.m3u.bak"

MAX_PAGES_PER_CATEGORY = 30
REQUEST_TIMEOUT = 25
SLEEP_SECONDS = 0.8

# Her dizi için alınacak en fazla bölüm.
# 0 = bulunan bütün bölümleri al.
MAX_EPISODES_PER_SERIES = 0

# yt-dlp kaynak çözümleme ayarları
YTDLP_OPTIONS = {
    "quiet": True,
    "no_warnings": True,
    "noplaylist": True,
    "skip_download": True,
    "extract_flat": False,
    "socket_timeout": REQUEST_TIMEOUT,
    "retries": 1,
    "extractor_retries": 1,
}

CATEGORIES = [
    {
        "url": f"{BASE_URL}/kore-dizileri-izle-dq1",
        "name": "🇰🇷 KORE DİZİLERİ",
        "kind": "series",
    },
    {
        "url": f"{BASE_URL}/kore-filmleri-izle-dq",
        "name": "🇰🇷 KORE FİLMLERİ",
        "kind": "movie",
    },
    {
        "url": f"{BASE_URL}/cin-dizileri",
        "name": "🇨🇳 ÇİN DİZİLERİ",
        "kind": "series",
    },
    {
        "url": f"{BASE_URL}/japon-dizileri",
        "name": "🇯🇵 JAPON DİZİLERİ",
        "kind": "series",
    },
    {
        "url": f"{BASE_URL}/tayland-dizileri",
        "name": "🇹🇭 TAYLAND DİZİLERİ",
        "kind": "series",
    },
    {
        "url": f"{BASE_URL}/tayvan-dizileri",
        "name": "🇹🇼 TAYVAN DİZİLERİ",
        "kind": "series",
    },
    {
        "url": f"{BASE_URL}/filmler",
        "name": "🎬 FİLMLER",
        "kind": "movie",
    },
]


# ==========================================================
# LOG
# ==========================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)

log = logging.getLogger("DIZIKOREA")


# ==========================================================
# HTTP OTURUMU
# ==========================================================

session = requests.Session()

session.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/130.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,"
        "application/xml;q=0.9,*/*;q=0.8"
    ),
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": BASE_URL + "/",
})


def get_page(url):
    """Sayfayı indirir ve BeautifulSoup döndürür."""

    for attempt in range(1, 3):
        try:
            response = session.get(
                url,
                timeout=REQUEST_TIMEOUT,
            )

            response.raise_for_status()

            if not response.encoding or response.encoding == "ISO-8859-1":
                response.encoding = response.apparent_encoding

            return BeautifulSoup(response.text, "html.parser")

        except Exception as exc:
            log.warning(
                "Sayfa alınamadı (%s/2): %s | %s",
                attempt,
                url,
                exc,
            )
            time.sleep(1)

    return None


# ==========================================================
# METİN VE URL YARDIMCILARI
# ==========================================================

def clean_text(value):
    if not value:
        return ""

    value = html.unescape(str(value))
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def fix_url(url):
    if not url:
        return None

    url = html.unescape(str(url)).strip()

    if not url or url.startswith(("javascript:", "data:", "#")):
        return None

    if url.startswith("//"):
        url = "https:" + url

    return urljoin(BASE_URL + "/", url)


def safe_name(value):
    value = clean_text(value)
    value = value.replace(",", " ")
    value = value.replace('"', "'")
    value = re.sub(r"[\r\n]+", " ", value)
    return value.strip()


def is_valid_media_url(url):
    if not url:
        return False

    parsed = urlparse(url)

    if parsed.scheme not in ("http", "https"):
        return False

    if not parsed.netloc:
        return False

    return True


# ==========================================================
# M3U8 ADRESİ BULMA
# ==========================================================

M3U8_REGEX = re.compile(
    r"""https?://[^\s"'<>\\]+?\.m3u8(?:\?[^\s"'<>\\]*)?""",
    re.IGNORECASE,
)


def find_m3u8(text):
    if not text:
        return []

    found = []

    for match in M3U8_REGEX.findall(text):
        url = match.rstrip("),];}")

        if is_valid_media_url(url) and url not in found:
            found.append(url)

    return found


# ==========================================================
# OYNATICI KAYNAKLARINI BULMA
# ==========================================================

def get_player_sources(document):
    """
    Kotlin eklentisindeki:
    div.player-source iframe
    seçicisini kullanır.

    Ek olarak yaygın iframe alanlarını da kontrol eder.
    """

    if not document:
        return []

    sources = []

    selectors = [
        "div.player-source iframe",
        "iframe[data-src]",
        "iframe[src]",
    ]

    for selector in selectors:
        for iframe in document.select(selector):
            raw = (
                iframe.get("data-src")
                or iframe.get("src")
                or ""
            )

            url = fix_url(raw)

            if url and url not in sources:
                sources.append(url)

    # Sayfa içinde doğrudan bulunan M3U8 adresleri
    for script in document.select("script"):
        text = script.string or script.get_text(" ", strip=True)

        for url in find_m3u8(text):
            if url not in sources:
                sources.append(url)

    for video in document.select("video source, video"):
        raw = video.get("src")

        url = fix_url(raw)

        if url and url not in sources:
            sources.append(url)

    return sources


# ==========================================================
# YT-DLP İLE OYNATMA ADRESİ ÇÖZME
# ==========================================================

def extract_streams(source_url):
    """
    Kaynağı doğrudan M3U8 ise alır.
    Değilse yt-dlp ile erişilebilir medya adreslerini çözer.
    """

    results = []

    if not source_url:
        return results

    if ".m3u8" in source_url.lower():
        return [source_url]

    try:
        with YoutubeDL(YTDLP_OPTIONS) as ydl:
            info = ydl.extract_info(
                source_url,
                download=False,
            )

        if not info:
            return results

        # Tek bir doğrudan medya adresi
        direct_url = info.get("url")

        if direct_url and (
            ".m3u8" in direct_url.lower()
            or ".mp4" in direct_url.lower()
        ):
            results.append(direct_url)

        # Format listesindeki yayın adresleri
        for item in info.get("formats", []) or []:
            media_url = item.get("url")

            if not media_url:
                continue

            protocol = str(item.get("protocol") or "").lower()
            ext = str(item.get("ext") or "").lower()

            if (
                "m3u8" in protocol
                or ext == "m3u8"
                or ".m3u8" in media_url.lower()
            ):
                results.append(media_url)

        # M3U8 bulunamadıysa MP4 formatını da kabul et
        if not results:
            formats = info.get("formats", []) or []

            mp4_formats = [
                item for item in formats
                if item.get("url")
                and item.get("ext") == "mp4"
                and item.get("vcodec") != "none"
            ]

            if mp4_formats:
                best = max(
                    mp4_formats,
                    key=lambda item: (
                        item.get("height") or 0,
                        item.get("tbr") or 0,
                    ),
                )

                results.append(best["url"])

    except Exception as exc:
        log.warning("Kaynak çözülemedi: %s | %s", source_url, exc)

    # Tekrarlı adresleri temizle
    unique = []

    for url in results:
        if is_valid_media_url(url) and url not in unique:
            unique.append(url)

    return unique


# ==========================================================
# DETAY SAYFASINDAN YAYINLARI AL
# ==========================================================

def get_streams_from_page(page_url):
    document = get_page(page_url)

    if not document:
        return []

    sources = get_player_sources(document)
    streams = []

    # Sayfanın kendi HTML içeriğinde M3U8 varsa ekle
    for url in find_m3u8(str(document)):
        if url not in streams:
            streams.append(url)

    # Her iframe kaynağını çöz
    for source in sources:
        log.info("Oynatıcı kontrol ediliyor: %s", source)

        for stream in extract_streams(source):
            if stream not in streams:
                streams.append(stream)

        time.sleep(0.3)

    return streams


# ==========================================================
# ANA SAYFA KARTLARINI BUL
# ==========================================================

def get_content_cards(category):
    """
    div.content-grid a.poster-card
    seçicisini kullanır.
    """

    first_url = category["url"]
    found = {}

    for page_number in range(1, MAX_PAGES_PER_CATEGORY + 1):

        if page_number == 1:
            page_url = first_url
        else:
            page_url = (
                first_url.rstrip("/")
                + f"/sayfa/{page_number}"
            )

        log.info(
            "Kategori taranıyor: %s | Sayfa %s",
            category["name"],
            page_number,
        )

        document = get_page(page_url)

        if not document:
            break

        cards = document.select(
            "div.content-grid a.poster-card"
        )

        if not cards:
            # Bazı sayfalarda kart yapısı farklı olabilir.
            cards = document.select("a.poster-card")

        new_count = 0

        for card in cards:
            title = clean_text(
                card.select_one("span.poster-card-title").get_text(" ", strip=True)
                if card.select_one("span.poster-card-title")
                else ""
            )

            href = fix_url(card.get("href"))

            if not title or not href:
                continue

            poster_element = card.select_one("img")

            poster = None

            if poster_element:
                poster = fix_url(
                    poster_element.get("data-src")
                    or poster_element.get("data-lazy-src")
                    or poster_element.get("src")
                )

            if href not in found:
                found[href] = {
                    "title": title,
                    "url": href,
                    "poster": poster,
                    "kind": category["kind"],
                    "group": category["name"],
                }
                new_count += 1

        # Sonraki sayfa bağlantısı yoksa dur
        next_link = document.select_one(
            f"a[href*='/sayfa/{page_number + 1}']"
        )

        if not next_link or new_count == 0:
            break

        time.sleep(SLEEP_SECONDS)

    return list(found.values())


# ==========================================================
# DİZİ BÖLÜMLERİNİ BUL
# ==========================================================

def get_series_episodes(series_url):
    document = get_page(series_url)

    if not document:
        return []

    episodes = []

    for episode_list in document.select("div.episode-list"):

        season = (
            episode_list.get("data-season", "").strip()
        )

        for item in episode_list.select("a.episode-item"):

            episode_url = fix_url(item.get("href"))

            if not episode_url:
                continue

            number_text = clean_text(
                item.select_one("span.ep-number").get_text()
                if item.select_one("span.ep-number")
                else ""
            )

            title_text = clean_text(
                item.select_one("span.ep-title").get_text()
                if item.select_one("span.ep-title")
                else ""
            )

            date_text = clean_text(
                item.select_one("span.ep-date").get_text()
                if item.select_one("span.ep-date")
                else ""
            )

            episode_number = None

            match = re.search(r"\d+", number_text)

            if match:
                episode_number = int(match.group())

            if episode_number is None:
                match = re.search(
                    r"bolum-(\d+)",
                    episode_url,
                    re.IGNORECASE,
                )

                if match:
                    episode_number = int(match.group(1))

            season_number = None

            match = re.search(
                r"\d+",
                season,
            )

            if match:
                season_number = int(match.group())

            if season_number is None:
                match = re.search(
                    r"sezon-(\d+)",
                    episode_url,
                    re.IGNORECASE,
                )

                if match:
                    season_number = int(match.group(1))

            episodes.append({
                "url": episode_url,
                "number": episode_number,
                "season": season_number,
                "title": title_text,
                "date": date_text,
            })

    # Tekrarlı bölüm bağlantılarını temizle
    unique = {}
    for episode in episodes:
        unique[episode["url"]] = episode

    episodes = list(unique.values())

    # Bölüm numarasına göre büyükten küçüğe sırala
    episodes.sort(
        key=lambda item: (
            item["season"] or 0,
            item["number"] or 0,
        ),
        reverse=True,
    )

    if MAX_EPISODES_PER_SERIES > 0:
        episodes = episodes[:MAX_EPISODES_PER_SERIES]

    return episodes


# ==========================================================
# POSTER BULMA
# ==========================================================

def get_detail_poster(document, fallback=None):
    if not document:
        return fallback

    selectors = [
        "div.series-hero-poster img",
        "img.sidebar-poster",
        "meta[property='og:image']",
        "meta[name='twitter:image']",
    ]

    for selector in selectors:
        element = document.select_one(selector)

        if not element:
            continue

        raw = (
            element.get("content")
            or element.get("data-src")
            or element.get("src")
            or ""
        )

        poster = fix_url(raw)

        if poster:
            return poster

    return fallback


# ==========================================================
# M3U KAYDI OLUŞTURMA
# ==========================================================

def make_m3u_entry(
    title,
    stream_url,
    group,
    poster=None,
    season=None,
    episode=None,
    episode_title=None,
):
    if episode is not None:
        display_name = f"{title} - {episode}. Bölüm"

        if season is not None:
            display_name = (
                f"{title} - {season}. Sezon "
                f"{episode}. Bölüm"
            )

        if episode_title:
            display_name += f" ({episode_title})"

    else:
        display_name = title

    display_name = safe_name(display_name)
    tvg_name = safe_name(display_name)
    group = safe_name(group)

    logo = poster or ""

    extinf = (
        f'#EXTINF:-1 tvg-name="{tvg_name}" '
        f'tvg-logo="{logo}" '
        f'group-title="{group}",{display_name}'
    )

    return [
        extinf,
        stream_url,
    ]


# ==========================================================
# ESKİ M3U DOSYASINI OKU
# ==========================================================

def read_old_m3u():
    if not os.path.exists(OUTPUT_FILE):
        return [], "#EXTM3U"

    try:
        with open(
            OUTPUT_FILE,
            "r",
            encoding="utf-8-sig",
        ) as file:
            lines = file.read().splitlines()

    except Exception as exc:
        log.error("Eski M3U okunamadı: %s", exc)
        return [], "#EXTM3U"

    header = "#EXTM3U"
    records = []
    current = []

    for line in lines:
        line = line.strip()

        if not line:
            continue

        if line.startswith("#EXTM3U"):
            header = line
            continue

        if line.startswith("#EXTINF"):
            if current:
                records.append(current)

            current = [line]

        elif current:
            current.append(line)

    if current:
        records.append(current)

    return records, header


# ==========================================================
# ESKİ KAYITLARI KORUMA / GÜNCELLEME
# ==========================================================

def get_record_name(record):
    if not record:
        return ""

    line = record[0]

    match = re.search(
        r'tvg-name="([^"]*)"',
        line,
        re.IGNORECASE,
    )

    if match:
        return clean_text(match.group(1))

    if "," in line:
        return clean_text(line.split(",", 1)[1])

    return ""


def get_record_group(record):
    if not record:
        return ""

    match = re.search(
        r'group-title="([^"]*)"',
        record[0],
        re.IGNORECASE,
    )

    return clean_text(match.group(1)) if match else ""


def belongs_to_title(record, title, kind):
    old_name = get_record_name(record).casefold()
    title_key = clean_text(title).casefold()

    if not old_name or not title_key:
        return False

    if kind == "movie":
        return old_name == title_key

    return (
        old_name == title_key
        or old_name.startswith(title_key + " - ")
        or old_name.startswith(title_key + " ")
    )


def save_m3u(new_entries, successful_items):
    old_records, header = read_old_m3u()

    # Önce eski kayıtları koru.
    # Sadece başarıyla güncellenen içeriklerin eski kayıtlarını değiştir.
    kept_records = []

    for record in old_records:
        remove_record = False

        for item in successful_items:
            if belongs_to_title(
                record,
                item["title"],
                item["kind"],
            ):
                remove_record = True
                break

        if not remove_record:
            kept_records.append(record)

    # Eski kayıtlar + yeni kayıtlar
    all_records = kept_records + new_entries

    # URL bazında tekrarları temizle
    unique_records = []
    seen_urls = set()

    for record in all_records:
        if not record:
            continue

        stream_url = record[-1].strip()

        if not is_valid_media_url(stream_url):
            continue

        if stream_url in seen_urls:
            continue

        seen_urls.add(stream_url)
        unique_records.append(record)

    # Önceki dosyanın yedeğini al
    if os.path.exists(OUTPUT_FILE):
        try:
            import shutil
            shutil.copy2(OUTPUT_FILE, BACKUP_FILE)
            log.info("Yedek oluşturuldu: %s", BACKUP_FILE)
        except Exception as exc:
            log.warning("Yedek oluşturulamadı: %s", exc)

    # Güvenli yazım: önce geçici dosya
    temp_file = OUTPUT_FILE + ".tmp"

    with open(
        temp_file,
        "w",
        encoding="utf-8",
        newline="\n",
    ) as file:

        file.write(header + "\n")

        for record in unique_
