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

        # Network'te primeembedpanel yakala
        def handle_response(response):
            url = response.url
            if "primeembedpanel.com" in url and "master.txt" in url:
                print(f"YAKALANDI: {url}")
                if url not in [x[1] for x in all_masters]:
                    all_masters.append(("Video", url))

        page.on("response", handle_response)

        print(f"Gidiliyor: {BASE_URL}")
        page.goto(BASE_URL, timeout=90000)
        page.wait_for_timeout(8000)

        # Ana sayfadaki tüm linkleri al
        hrefs = page.eval_on_selector_all("a", "els => els.map(e => e.href)")
        video_links = [h for h in hrefs if "/video/" in h or "/izle/" in h][:15] # ilk 15'i test
        print(f"{len(video_links)} video bulundu: {video_links[:3]}")

        # Her videoya gir ve m3u8 yakala
        for vlink in video_links:
            try:
                print(f"\nGiriliyor: {vlink}")
                page.goto(vlink, timeout=60000)
                page.wait_for_timeout(7000)
                # play'e tıkla
                try:
                    page.click("video, .jwplayer, .play-button, .plyr", timeout=3000)
                except: 
                    page.mouse.click(300, 300)
                page.wait_for_timeout(5000)
                
                # html içinden de ara
                html = page.content()
                primes = re.findall(r'https?://primeembedpanel\.com/cdn/hls/[^"\']+/master\.txt', html)
                for pr in primes:
                    if pr not in [x[1] for x in all_masters]:
                        title = vlink.split("/")[-1].replace("-", " ")
                        all_masters.append((title, pr))
                        print(f"  HTML'den bulundu: {pr}")

            except Exception as e:
                print(f"Hata {vlink}: {e}")

        browser.close()

    # M3U yaz
    with open("playlist.m3u", "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for title, url in set(all_masters):
            f.write(f'#EXTINF:-1,{title}\n{url}\n')
    
    print(f"\nBİTTİ! Toplam {len(all_masters)} link -> playlist.m3u")

if __name__ == "__main__":
    main()
