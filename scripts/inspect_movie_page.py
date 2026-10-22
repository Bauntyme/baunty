import asyncio
import aiohttp
from bs4 import BeautifulSoup

async def inspect_page(url):
    print(f"\n--- Inspecting {url} ---")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Referer": "https://asilmedia.org/",
    }
    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.get(url) as resp:
            print(f"Status: {resp.status}")
            html = await resp.text()
            print(f"HTML size: {len(html)} bytes")
            soup = BeautifulSoup(html, "html.parser")
            
            # Check for tg-data, player, iframe, script tags
            tg_data = soup.find(id="tg-data")
            print("id='tg-data':", tg_data.get_text() if tg_data else "NOT FOUND")
            
            episodes_raw = soup.find(id="episodes-raw-data")
            print("id='episodes-raw-data':", episodes_raw if episodes_raw else "NOT FOUND")

            iframes = soup.find_all("iframe")
            print(f"Found {len(iframes)} iframes:")
            for ifr in iframes:
                print("  iframe:", ifr.attrs)
                
            videos = soup.find_all("video")
            print(f"Found {len(videos)} video tags:")
            for v in videos:
                print("  video:", v.attrs)
                
            # Search for player or stream urls in scripts
            import re
            scripts = soup.find_all("script")
            for idx, sc in enumerate(scripts):
                sc_text = sc.get_text()
                if any(k in sc_text for k in ["player", "m3u8", "mp4", "file:", "file", "allvi", "vcdn", "mover"]):
                    print(f"Script #{idx} mentions media/player. First 300 chars:")
                    print(sc_text[:300].strip())
                    # find all urls
                    urls = re.findall(r'https?://[^\s"\'<>]+', sc_text)
                    media_urls = [u for u in urls if any(ext in u.lower() for ext in [".mp4", ".m3u8", "embed", "player", "video"])]
                    if media_urls:
                        print("    Found media urls:", media_urls)

async def main():
    urls = [
        "https://asilmedia.org/11463-taksi-4-taxi-4-uzbek-tilida-2007-ozbekcha-tarjima-kino-hd.html",
        "https://asilmedia.org/17608-taksi-xazina-togi-gibraltarga-taksi-ispaniya-filmi-2019-uzbek-tilida-ozbekcha-tarjima-kino-full-hd-tas-ix-skachat.html",
    ]
    for u in urls:
        await inspect_page(u)

if __name__ == "__main__":
    asyncio.run(main())
