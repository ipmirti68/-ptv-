import requests
import re
from urllib.parse import urljoin

BASE_URL = "https://cimcime179.live"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
    "Referer": "https://cimcime179.live/"
}

def get_prime_links():
    # 1. Ana sayfadaki video linklerini al
    r = requests.get(BASE_URL, headers=HEADERS, timeout=20)
    video_pages = re.findall(r'href="(/video/[^"]+|/izle/[^"]+)"', r.text)
    video_pages = list(set(video_pages))[:20] # test için ilk 20
    print(f"{len(video_pages)} video sayfası bulundu")

    all_masters = []

    for path in video_pages:
        page_url = BASE_URL + path
        try:
            print(f"Taranıyor: {page_url}")
            html = requests.get(page_url, headers=HEADERS, timeout=15).text
            
            # Senin attığın gibi primeembed linkini yakala
            # https://primeembedpanel.com/cdn/hls/xxxx/master.txt
            primes = re.findall(r'https?://primeembedpanel\.com/cdn/hls/[^"\']+/master\.txt', html)
            # bazen embed kodu base64'lü oluyor
            primes += re.findall(r'https?://primeembedpanel\.com[^\s"\'<>]+', html)

            for p in primes:
                if "master.txt" in p:
                    # master.txt -> gerçek m3u8 içeriğini al
                    # Bu link kalıcı değil, o yüzden m3u'ya direkt bunu yazıyoruz
                    title = path.replace("/video/", "").replace("-", " ").title()
                    all_masters.append((title, p))
                    print(f"  -> Bulundu: {p}")

        except Exception as e:
            print(f"Hata {page_url}: {e}")

    return all_masters

def main():
    links = get_prime_links()
    
    with open("playlist.m3u", "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for title, url in links:
            # VLC master.txt'yi m3u8 gibi okur, uzantıyı değiştirsek daha iyi çalışır
            # ama orijinali de çalışır
            f.write(f'#EXTINF:-1,{title}\n')
            f.write(f'{url}\n')
    
    print(f"\nBitti! {len(links)} adet link ile playlist.m3u oluşturuldu")
    print("Örnek linkin: " + links[0][1] if links else "Link bulunamadı")

if __name__ == "__main__":
    main()
