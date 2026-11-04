import requests
import re
import time

# Site Cloudflare kullanıyorsa User-Agent şart
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
    "Referer": "https://cimcime179.live/"
}

def m3u8_linklerini_bul(sayfa_url):
    try:
        r = requests.get(sayfa_url, headers=HEADERS, timeout=15)
        html = r.text

        # 1. Yöntem: direk .m3u8 ara
        links = re.findall(r'https?://[^\s\'"<>]+\.m3u8[^\s\'"<>]*', html)
        
        # 2. Yöntem: player config içinde file: "link" şeklinde olur
        links += re.findall(r'file["\']?\s*:\s*["\'](https?://[^"\']+\.m3u8[^"\']*)', html)
        links += re.findall(r'source["\']?\s*:\s*["\'](https?://[^"\']+\.m3u8[^"\']*)', html)

        # Tekilleştir
        return list(set(links))
    except Exception as e:
        print(f"Hata {sayfa_url} -> {e}")
        return []

def m3u_listesi_olustur(video_sayfalari, cikti_dosyasi="cimcime.m3u"):
    with open(cikti_dosyasi, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        
        for i, sayfa in enumerate(video_sayfalari):
            print(f"[{i+1}/{len(video_sayfalari)}] Taranıyor: {sayfa}")
            m3u8ler = m3u8_linklerini_bul(sayfa)
            
            for link in m3u8ler:
                # Başlık olarak sayfa url'sini kullanıyoruz, istersen burayı video başlığı ile değiştiririz
                baslik = f"Video {i+1} - {sayfa.split('/')[-1]}"
                f.write(f'#EXTINF:-1,{baslik}\n')
                f.write(f'{link}\n')
                print(f"  -> Bulundu: {link}")
            
            time.sleep(0.5) # Siteyi yormamak için

    print(f"\nBitti! {cikti_dosyasi} oluşturuldu. VLC ile açabilirsin.")

# --- BURAYI KENDİNE GÖRE DOLDUR ---
if __name__ == "__main__":
    # Çekmek istediğin video sayfalarının linklerini buraya liste olarak ekle
    # Örnek:
    video_linkleri = [
        "https://cimcime179.live/video/xxxx1",
        "https://cimcime179.live/video/xxxx2",
        "https://cimcime179.live/video/xxxx3",
    ]
    
    # Eğer tüm sayfaları otomatik bulsun istiyorsan, ana sayfadaki linkleri toplayan bir fonksiyon da ekleyebilirim
    m3u_listesi_olustur(video_linkleri)
