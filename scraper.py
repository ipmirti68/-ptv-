import re
from playwright.sync_api import sync_playwright

BASE_URL = "https://cimcime179.live"

def main():
    all_masters = []
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        page.on("response", lambda r: print(f"RESPONSE: {r.status} {r.url}") if "m3u8" in r.url or "master.txt" in r.url or "primeembed" in r.url else None)

        print(f"Gidiliyor: {BASE_URL}")
        page.goto(BASE_URL, timeout=90000, wait_until="domcontentloaded")
        page.wait_for_timeout(10000)
        
        # DEBUG: Ne gördük?
        print(f"Sayfa başlığı: {page.title()}")
        html = page.content()
        print(f"HTML uzunluğu: {len(html)}")
        print(html[:3000]) # ilk 3000 karakteri loga bas
        
        page.screenshot(path="debug.png", full_page=True)
        print("debug.png kaydedildi")

        # Cloudflare sayfası mı?
        if "Just a moment" in html or "cf-challenge" in html or "Checking if the site connection is secure" in html:
            print("!!! CLOUDFLARE ENGELİ VAR !!!")
        else:
            hrefs = page.eval_on_selector_all("a", "els => els.map(e => e.href)")
            print(f"Tüm link sayısı: {len(hrefs)}")
            video_links = [h for h in hrefs if "video" in h.lower() or "izle" in h.lower()][:10]
            print(f"Video linkleri: {video_links}")

        browser.close()

    # Boş da olsa dosya oluştur
    with open("playlist.m3u", "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")

if __name__ == "__main__":
    main()
