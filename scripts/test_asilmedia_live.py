import asyncio
import aiohttp
import ssl

async def test_domain(url, search_query=None):
    print(f"\n--- Testing {url} ---")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "uz,ru;q=0.9,en;q=0.8",
    }
    timeout = aiohttp.ClientTimeout(total=10)
    try:
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(url, timeout=timeout) as resp:
                print(f"GET {url} -> Status: {resp.status}, Content-Type: {resp.headers.get('Content-Type')}")
                text = await resp.text()
                print(f"Response length: {len(text)} bytes. Preview: {text[:200]!r}")
                
            if search_query:
                search_url = f"{url.rstrip('/')}/"
                params = {"do": "search", "subaction": "search", "story": search_query}
                async with session.get(search_url, params=params, timeout=timeout) as s_resp:
                    print(f"SEARCH GET {search_query} -> Status: {s_resp.status}")
                    s_text = await s_resp.text()
                    print(f"Search results length: {len(s_text)} bytes")
                    import re
                    links = re.findall(r'href="([^"]*\.html)"', s_text)
                    print(f"Found {len(links)} html links. First 5: {links[:5]}")
    except Exception as e:
        print(f"ERROR connecting to {url}: {type(e).__name__}: {e}")

async def main():
    domains = [
        "https://asilmedia.org",
        "https://asilmedia.net",
        "https://asilmedia.uz",
        "https://asilmedia.tv",
        "https://asilmedia.org/index.php",
    ]
    for d in domains:
        await test_domain(d, search_query="Taksi")

if __name__ == "__main__":
    asyncio.run(main())
