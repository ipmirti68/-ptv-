
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
MEDYA HAVUZU V4

Canlı TV, film ve diziler için otomatik M3U üretici.

- Farklı M3U kaynaklarını birleştirir.
- TV kanallarını kategorilere ayırır.
- Film ve dizileri ayrı tutar.
- Tekrarlanan kayıtları temizler.
- Ulusal kanalları öne alır.
- Boş listelerde önceki dosyaları korur.
- Durum raporu üretir.

Yalnızca kullanım izni bulunan kaynakları kullanın.
"""

from __future__ import annotations

import concurrent.futures
import datetime as dt
import json
import os
from pathlib import Path
import re
import tempfile
import urllib.error
import urllib.parse
import urllib.request


ROOT = Path(__file__).resolve().parent

USER_AGENT = (
    "Mozilla/5.0 "
    "(compatible; MedyaHavuzu/4.0; +https://github.com/)"
)

ATTR_RE = re.compile(
    r'([\w-]+)\s*=\s*"([^"]*)"'
)

TITLE_GROUPS = [
    "01 | ULUSAL",
    "02 | SPOR",
    "03 | HABER",
    "04 | SİNEMA",
    "05 | BELGESEL",
    "06 | ÇOCUK",
    "07 | MÜZİK",
    "08 | YEREL",
    "09 | DİĞER",
    "10 | YABANCI",
]

NATIONAL = [
    "trt 1",
    "atv",
    "kanal d",
    "show tv",
    "star tv",
    "now",
    "tv8",
    "kanal 7",
    "teve2",
    "360 tv",
    "beyaz tv",
    "a2 tv",
]

SPORT = [
    "spor",
    "sport",
    "sports",
    "futbol",
    "basket",
    "gs tv",
    "fb tv",
    "tivibu spor",
]

NEWS = [
    "haber",
    "news",
    "cnn",
    "ntv",
    "habertürk",
    "haberturk",
    "tvnet",
    "bloomberg",
    "ekotürk",
    "ekoturk",
]

MOVIE = [
    "sinema",
    "cinema",
    "movie",
    "film",
    "movies",
]

DOC = [
    "belgesel",
    "documentary",
    "discovery",
    "nature",
    "history",
    "national geographic",
]

KIDS = [
    "çocuk",
    "cocuk",
    "kids",
    "cartoon",
    "minika",
    "baby",
    "nick",
    "disney",
]

MUSIC = [
    "müzik",
    "muzik",
    "music",
    "power",
    "kral pop",
    "number1",
    "dream türk",
    "dream turk",
]

LOCAL = [
    "yerel",
    "local",
    "belediye",
    "kent tv",
    "şehir tv",
]


def clean(value: str) -> str:
    return re.sub(
        r'[\r\n\x00-\x1f"]',
        " ",
        str(value or "")
    ).strip()


def http_url(value: str) -> bool:
    try:
        parsed = urllib.parse.urlsplit(
            value.strip()
        )

        return (
            parsed.scheme.lower() in ("http", "https")
            and bool(parsed.hostname)
            and not (
                parsed.username or parsed.password
            )
        )

    except ValueError:
        return False


def fetch(
    url: str,
    timeout: int,
    max_bytes: int
) -> str:

    if not http_url(url):
        raise ValueError(
            "HTTP(S) kaynak adresi gerekli"
        )

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "*/*",
        }
    )

    with urllib.request.urlopen(
        request,
        timeout=timeout
    ) as response:

        final = response.geturl()

        if not http_url(final):
            raise ValueError(
                "Geçersiz yönlendirme"
            )

        data = response.read(
            max_bytes + 1
        )

        if len(data) > max_bytes:
            raise ValueError(
                "Kaynak boyut sınırını aştı"
            )

    return data.decode(
        "utf-8-sig",
        errors="replace"
    )


def parse_m3u(
    text: str,
    source: str
) -> list[dict]:

    if not text.lstrip().startswith(
        "#EXTM3U"
    ):
        raise ValueError(
            "Kaynak M3U değil"
        )

    output = []
    entry = None

    for raw in text.splitlines():

        line = raw.strip()

        if line.startswith("#EXTINF:"):

            attrs = dict(
                ATTR_RE.findall(line)
            )

            name = (
                line.split(",", 1)[1].strip()
                if "," in line
                else ""
            )

            entry = {
                "ad": clean(name),
                "logo": attrs.get(
                    "tvg-logo", ""
                ),
                "id": attrs.get(
                    "tvg-id", ""
                ),
                "grup": attrs.get(
                    "group-title", ""
                ),
                "dil": attrs.get(
                    "tvg-language", ""
                ),
                "kaynak": source,
            }

        elif line.startswith("#") or not line:
            continue

        elif entry is not None:

            if (
                http_url(line)
                and entry["ad"]
            ):
                entry["url"] = line
                output.append(entry)

            entry = None

    return output


def category(
    item: dict,
    region: str
) -> str:

    if region != "TR":
        return TITLE_GROUPS[-1]

    name = re.sub(
        r'\s*\([^)]*\)|\s*\[[^]]*\]',
        "",
        item["ad"]
    ).casefold().strip()

    grp = item["grup"].casefold()

    if (
        name in NATIONAL
        or any(
            name.startswith(x + " ")
            for x in NATIONAL
        )
    ):
        return TITLE_GROUPS[0]

    groups = [
        (SPORT, 1),
        (NEWS, 2),
        (MOVIE, 3),
        (DOC, 4),
        (KIDS, 5),
        (MUSIC, 6),
        (LOCAL, 7),
    ]

    for keys, label in groups:

        if any(
            word in name or word in grp
            for word in keys
        ):
            return TITLE_GROUPS[label]

    return TITLE_GROUPS[8]


def order_key(item: dict) -> tuple:

    normalized = (
        item["ad"]
        .casefold()
        .replace("türk", "turk")
    )

    national_position = next(
        (
            i
            for i, x in enumerate(NATIONAL)
            if (
                normalized == x
                or normalized.startswith(x + " ")
            )
        ),
        999
    )

    return (
        item["grup"],
        national_position,
        normalized,
        item["url"],
    )


def normalize(
    entries: list[dict],
    kind: str,
    region: str = "TR"
) -> list[dict]:

    seen = set()
    result = []

    for raw in entries:

        item = dict(raw)

        key = (
            item["ad"].casefold(),
            item["url"].strip(),
        )

        if key in seen:
            continue

        seen.add(key)

        if kind == "canli":

            item["grup"] = category(
                item, region
            )

        elif kind == "filmler":

            item["grup"] = (
                "FİLMLER | "
                + clean(item["kaynak"])
            )

        else:

            item["grup"] = (
                "DİZİLER | "
                + clean(item["kaynak"])
            )

        result.append(item)

    return result


def render(items: list[dict]) -> str:

    rows = ["#EXTM3U"]

    for x in sorted(
        items,
        key=order_key
    ):

        rows.append(
            f'#EXTINF:-1 '
            f'tvg-id="{clean(x["id"])}" '
            f'tvg-logo="{clean(x["logo"])}" '
            f'tvg-language="{clean(x["dil"])}" '
            f'group-title="{clean(x["grup"])}",'
            f'{clean(x["ad"])}'
        )

        rows.append(x["url"])

    return "\n".join(rows) + "\n"


def write_atomic(
    filename: str,
    content: str
) -> None:

    fd, temp = tempfile.mkstemp(
        dir=ROOT,
        prefix=".liste-",
        suffix=".tmp"
    )

    try:

        with os.fdopen(
            fd,
            "w",
            encoding="utf-8",
            newline="\n"
        ) as stream:

            stream.write(content)

        os.replace(
            temp,
            ROOT / filename
        )

    finally:

        if os.path.exists(temp):
            os.unlink(temp)


def check_stream(
    item: dict,
    timeout: int = 8
) -> bool:

    """
    Hafif HTTP kontrolü.

    Bu işlem yayının kesin oynatılacağını
    garanti etmez.
    """

    try:

        req = urllib.request.Request(
            item["url"],
            headers={
                "User-Agent": USER_AGENT,
                "Range": "bytes=0-1023",
            }
        )

        with urllib.request.urlopen(
            req,
            timeout=timeout
        ) as resp:

            data = resp.read(1024)

            mime = resp.headers.get(
                "content-type", ""
            ).lower()

            return (
                resp.status in (200, 206)
                and bool(data)
                and "text/html" not in mime
                and b"<html" not in data[:300].lower()
            )

    except (
        urllib.error.URLError,
        ValueError,
        TimeoutError,
        OSError
    ):
        return False


def update() -> None:

    config_path = ROOT / "kaynaklar.json"

    config = json.loads(
        config_path.read_text(
            encoding="utf-8"
        )
    )

    settings = config.get(
        "ayarlar", {}
    )

    timeout = int(
        settings.get(
            "zaman_asimi_saniye",
            20
        )
    )

    limit = (
        int(
            settings.get(
                "kaynak_boyut_limiti_mb",
                30
            )
        )
        * 1024
        * 1024
    )

    validate = bool(
        settings.get(
            "yayini_dogrula",
            False
        )
    )

    source_jobs = [
        (kind, src)

        for kind in (
            "canli",
            "filmler",
            "diziler"
        )

        for src in config.get(
            kind, []
        )

        if src.get("aktif", False)
    ]

    rows = {
        "canli": [],
        "filmler": [],
        "diziler": [],
    }

    failures = []
    successful = []

    def task(job):

        kind, src = job

        content = fetch(
            src["url"],
            timeout,
            limit
        )

        items = parse_m3u(
            content,
            src["ad"]
        )

        return kind, src, items

    with concurrent.futures.ThreadPoolExecutor(
        max_workers=6
    ) as pool:

        future_map = {
            pool.submit(task, job): job
            for job in source_jobs
        }

        for future in concurrent.futures.as_completed(
            future_map
        ):

            kind, src = future_map[future]

            try:

                _, _, items = future.result()

                region = src.get(
                    "bolge", "TR"
                )

                items = normalize(
                    items,
                    kind,
                    region
                )

                rows[kind].extend(items)

                successful.append({
                    "tur": kind,
                    "kaynak": src["ad"],
                    "kayit": len(items),
                })

                print(
                    f'[OK] {kind}: '
                    f'{src["ad"]}: '
                    f'{len(items)} kayıt'
                )

            except Exception as exc:

                failures.append({
                    "tur": kind,
                    "kaynak": src.get(
                        "ad", "?"
                    ),
                    "hata": str(exc),
                })

                print(
                    f'[HATA] {kind}: '
                    f'{src.get("ad")}: '
                    f'{exc}'
                )

    # Kaynaklar arasında yinelenenleri temizle.

    for kind in rows:

        source_order = {
            src["ad"]: i

            for i, src in enumerate(
                config.get(kind, [])
            )
        }

        rows[kind].sort(
            key=lambda item:
            source_order.get(
                item["kaynak"],
                999
            )
        )

        seen = set()
        deduped = []

        for item in rows[kind]:

            key = (
                item["ad"].casefold(),
                item["url"]
            )

            if key not in seen:

                deduped.append(item)
                seen.add(key)

        rows[kind] = deduped

    # İsteğe bağlı yayın doğrulaması.

    if validate:

        for kind in rows:

            with concurrent.futures.ThreadPoolExecutor(
                max_workers=12
            ) as pool:

                mask = list(
                    pool.map(
                        check_stream,
                        rows[kind]
                    )
                )

            rows[kind] = [
                item
                for item, valid in zip(
                    rows[kind],
                    mask
                )
                if valid
            ]

    files = {
        "canli": "canli_tv.m3u",
        "filmler": "filmler.m3u",
        "diziler": "diziler.m3u",
    }

    saved = {}

    for kind, filename in files.items():

        minimum = int(
            settings.get(
                "min_" + kind,
                1
            )
        )

        if len(rows[kind]) >= minimum:

            write_atomic(
                filename,
                render(rows[kind])
            )

            saved[kind] = "güncellendi"

        else:

            saved[kind] = (
                "önceki dosya korundu"
            )

        print(
            f'{filename}: '
            f'{len(rows[kind])} aday -> '
            f'{saved[kind]}'
        )

    # Canlı TV + Film + Dizi birleştir.

    combined = ["#EXTM3U"]

    for filename in files.values():

        path = ROOT / filename

        if not path.exists():
            continue

        content = path.read_text(
            encoding="utf-8-sig",
            errors="replace"
        )

        if content.lstrip().startswith(
            "#EXTM3U"
        ):

            combined.extend(
                content.splitlines()[1:]
            )

    if len(combined) > 1:

        write_atomic(
            "tum_icerikler.m3u",
            "\n".join(combined) + "\n"
        )

    # Durum raporu.

    report = {
        "guncellendi_utc": (
            dt.datetime.now(
                dt.timezone.utc
            ).isoformat()
        ),

        "aday_sayilari": {
            key: len(value)
            for key, value in rows.items()
        },

        "dosya_durumlari": saved,

        "basarili_kaynaklar": successful,

        "hatalar": failures,

        "uyari": (
            "HTTP kontrolü oynatılabilirlik "
            "garantisi değildir. Bazı bölgesel "
            "ve DRM yayınları çalışmayabilir."
        ),
    }

    write_atomic(
        "durum.json",
        json.dumps(
            report,
            ensure_ascii=False,
            indent=2
        ) + "\n"
    )

    if not successful:

        print(
            "UYARI: Hiçbir kaynak indirilemedi. "
            "Önceki listeler korundu."
        )


if __name__ == "__main__":
    update()
