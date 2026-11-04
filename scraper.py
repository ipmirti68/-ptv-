import requests
from bs4 import BeautifulSoup
import re
import os

BASE_URL = "https://cimcime179.live"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
    "Referer": f"{BASE_URL}/"
}

def get_video_pages():
    print(f"Ana sayfa taranıyor: {BASE_URL}")
    r = requests.get(BASE_URL, headers=HEADERS, timeout=20)
    soup = BeautifulSoup(r.text, 'lxml')
    links = set()
    # Sitedeki video linkleri genelde /video/ , /izle/ , /bolum/ gibi olur - hepsini topla
    for a in soup.find_all('a', href=True):
        href = a['href']
        if '/video' in href or '/izle' in href or '/bolum' in href or '/episode' in href:
            if href.startswith('/'):
                href = BASE_URL + href
            if BASE_URL in href:
                links.add(href.split('?')[0])
    
    print(f"{len(links)} video sayfası bulundu")
    return list(links)[:100] # ilk 100 tanesini al, GitHub limitine takılmamak için

def extract_m3u8(page_url):
    try:
        r = requests.get(page_url, headers=HEADERS, timeout=15)
        html = r.text
        
        # Tüm m3u8 patternlerini dene
        patterns = [
            r'https?://[^\s\'"<>]+\.m3u8[^\s\'"<>]*',
            r'file:\s*["\'](https?://[^"\']+\.m3u8[^"\']*)',
            r'source:\s*["\'](https?://[^"\']+\.m3u8[^"\']*)',
            r'src:\s*["\'](https?://[^"\']+\.m3u8[^"\']*)',
        ]
        
        found = []
        for pat in patterns:
            found += re.findall(pat, html)
        
        # Base64 içinde gizlenmişse çöz
        b64_m3u8 = re.findall(r'atob\(["\']([^"\']+\.m3u8[^"\']*)', html)
        found += b64_m3u8

        return list(set(found))
    except Exception as e:
        print(f"Hata {page_url}: {e}")
        return []

def create_m3u():
    video_pages = get_video_pages()
    
    with open("playlist.m3u", "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        
        for page in video_pages:
            print(f"Taranıyor: {page}")
            m3u8_list = extract_m3u8(page)
            if not m3u8_list:
                continue
            
            # Başlık olarak sayfa başlığını al
            try:
                title = page.split('/')[-1].replace('-', ' ').title()
            except:
                title = page

            for m3u8 in m3u8_list:
                # En kaliteli link genelde master.m3u8 olur
                f.write(f'#EXTINF:-1,{title}\n')
                f.write(f'{m3u8}\n')
                print(f" -> Eklendi: {m3u8}")

    # GitHub için raw linkin olacak: https://raw.githubusercontent.com/KULLANICI_ADIN/REPO_ADI/main/playlist.m3u
    print("\nplaylist.m3u oluşturuldu!")

if __name__ == "__main__":
    create_m3u()
