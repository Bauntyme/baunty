import asyncio
import aiohttp
from bs4 import BeautifulSoup
import re

async def check_titles():
    queries = ["Attack on Titan", "Chuqur", "Forsaj"]
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Referer": "https://asilmedia.org/",
    }
    async with aiohttp.ClientSession(headers=headers) as session:
        for q in queries:
            print(f"\n=================== SEARCH: {q} ===================")
            params = {"do": "search", "subaction": "search", "story": q}
            async with session.get("https://asilmedia.org/", params=params) as resp:
                html = await resp.text()
                soup = BeautifulSoup(html, "html.parser")
                links = []
                for a in soup.find_all("a", href=True):
                    m = re.search(r'/(\d+-[^/]+\.html)', a['href'])
                    if m and m.group(1) not in links:
                        links.append(a['href'] if a['href'].startswith('http') else f"https://asilmedia.org/{m.group(1)}")
                print(f"Found {len(links)} results. Top 3:")
                for l in links[:3]:
                    print(" ", l)
                    
                if links:
                    first_url = links[0]
                    async with session.get(first_url) as page_resp:
                        page_html = await page_resp.text()
                        psoup = BeautifulSoup(page_html, "html.parser")
                        tg_data = psoup.find(id="tg-data")
                        print(f"  tg-data for {first_url}:")
                        if tg_data:
                            print("   ", tg_data.get_text().strip()[:200])
                        else:
                            print("    None")
                        iframes = psoup.find_all("iframe")
                        print(f"  iframes ({len(iframes)}):")
                        for ifr in iframes:
                            print("   ", ifr.attrs)

if __name__ == "__main__":
    asyncio.run(check_titles())
