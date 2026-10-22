import asyncio
import aiohttp
import urllib.parse

async def test_stream_urls():
    urls = [
        "https://server.asilmedia.org/watch/4310693215/23713",
        "https://server.asilmedia.org/download/4310693215/23713",
        "https://fayllar.com/11/Taksi 4 480p O'zbek tilida (asilmedia.net).mp4",
        "https://fayllar.com/35/kinolar/Taksi- Xazina tog'i 2019 480p (asilmedia.net).mp4",
    ]
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Referer": "https://asilmedia.org/",
    }
    async with aiohttp.ClientSession(headers=headers) as session:
        for u in urls:
            encoded_u = urllib.parse.quote(u, safe=":/%?=&-._~")
            print(f"\n--- Testing URL: {u} (encoded: {encoded_u}) ---")
            try:
                async with session.get(encoded_u, timeout=aiohttp.ClientTimeout(total=10), allow_redirects=True) as resp:
                    print(f"Status: {resp.status}")
                    print(f"Final URL: {resp.url}")
                    print(f"Content-Type: {resp.headers.get('Content-Type')}")
                    print(f"Content-Length: {resp.headers.get('Content-Length')}")
                    content_peek = await resp.content.read(256)
                    print(f"Peek 256 bytes: {content_peek[:100]!r}")
            except Exception as e:
                print(f"ERROR: {type(e).__name__}: {e}")

if __name__ == "__main__":
    asyncio.run(test_stream_urls())
