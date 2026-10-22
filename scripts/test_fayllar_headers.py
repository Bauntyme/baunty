import asyncio
import aiohttp

async def test_fayllar_headers():
    url = "https://11.fayllar.com/11/Taksi%204%20480p%20O'zbek%20tilida%20(asilmedia.net).mp4"
    variants = [
        {"Referer": "https://asilmedia.org/"},
        {"Referer": "https://asilmedia.net/"},
        {"Referer": "https://fayllar.com/"},
        {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
        {"User-Agent": "Mozilla/5.0", "Referer": "https://asilmedia.org/", "Origin": "https://asilmedia.org"},
        {"User-Agent": "Mozilla/5.0", "Referer": "https://asilmedia.net/", "Origin": "https://asilmedia.net"},
        {"Range": "bytes=0-1024", "Referer": "https://asilmedia.org/"},
    ]
    for idx, h in enumerate(variants):
        try:
            async with aiohttp.ClientSession(headers=h) as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    print(f"Variant #{idx} (headers: {h}) -> Status: {resp.status}")
                    if resp.status in (200, 206):
                        peek = await resp.content.read(64)
                        print(f"  SUCCESS! Content-Type: {resp.headers.get('Content-Type')}, peek: {peek[:16]!r}")
        except Exception as e:
            print(f"Variant #{idx} error: {e}")

if __name__ == "__main__":
    asyncio.run(test_fayllar_headers())
