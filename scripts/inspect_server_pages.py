import asyncio
import aiohttp
from bs4 import BeautifulSoup
import re

async def inspect_server_pages():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Referer": "https://asilmedia.org/",
    }
    urls = [
        "https://server.asilmedia.org/watch/4310693215/23713",
        "https://server.asilmedia.org/download/4310693215/23713",
    ]
    async with aiohttp.ClientSession(headers=headers) as session:
        for u in urls:
            print(f"\n====================== {u} ======================")
            async with session.get(u) as resp:
                html = await resp.text()
                soup = BeautifulSoup(html, "html.parser")
                print("Title:", soup.find("title").get_text() if soup.find("title") else "No title")
                
                # Check for forms, buttons, links (a tags)
                links = soup.find_all("a", href=True)
                print(f"Found {len(links)} links:")
                for a in links:
                    print("  a:", a.get_text(strip=True), "->", a['href'])
                    
                # Check video tags
                for v in soup.find_all("video"):
                    print("  video tag:", v.attrs)
                    for src in v.find_all("source"):
                        print("    source:", src.attrs)
                        
                # Check scripts
                for sc in soup.find_all("script"):
                    txt = sc.get_text()
                    if any(k in txt for k in ["http", "file", "player", "token", "url", "video"]):
                        print("  Script snippet:")
                        print(txt[:400])
                        urls_found = re.findall(r'https?://[^\s"\'<>]+', txt)
                        print("  Urls in script:", urls_found)

if __name__ == "__main__":
    asyncio.run(inspect_server_pages())
