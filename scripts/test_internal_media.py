import asyncio
import aiohttp

async def test_internal_media():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Referer": "https://server.asilmedia.org/watch/4310693215/23713",
        "Origin": "https://server.asilmedia.org",
    }
    urls = [
        "https://server.asilmedia.org/_internal/media/4310693215/23713",
        "https://server.asilmedia.org/_internal/media/4310693215/23713?pjsfr=1&download=1&origin=https%3A%2F%2Fserver.asilmedia.org",
        "https://server.asilmedia.org/player/telegram-embed-adapter.js?v=13",
    ]
    async with aiohttp.ClientSession(headers=headers) as session:
        for u in urls:
            print(f"\nGET {u}")
            try:
                async with session.get(u, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    print(f"Status: {resp.status}")
                    print(f"Content-Type: {resp.headers.get('Content-Type')}")
                    print(f"Content-Length: {resp.headers.get('Content-Length')}")
                    body = await resp.read()
                    print(f"Body len: {len(body)}")
                    print(f"Body preview: {body[:300]!r}")
            except Exception as e:
                print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_internal_media())
