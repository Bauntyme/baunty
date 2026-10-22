import asyncio
import aiohttp
from bs4 import BeautifulSoup

async def dump_scripts():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Referer": "https://asilmedia.org/",
    }
    async with aiohttp.ClientSession(headers=headers) as session:
        for mode in ["watch", "download"]:
            u = f"https://server.asilmedia.org/{mode}/4310693215/23713"
            async with session.get(u) as resp:
                html = await resp.text()
                soup = BeautifulSoup(html, "html.parser")
                with open(f"scratch/server_{mode}.html", "w", encoding="utf-8") as f:
                    f.write(html)
                print(f"Saved scratch/server_{mode}.html ({len(html)} bytes)")

if __name__ == "__main__":
    import os
    os.makedirs("scratch", exist_ok=True)
    asyncio.run(dump_scripts())
