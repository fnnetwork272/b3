import aiohttp
import asyncio

async def test_proxy(proxy):
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            async with session.get("http://api.ipify.org", proxy=proxy) as response:
                if response.status == 200:
                    print(f"Proxy {proxy} is live: {await response.text()}")
                    return True
        return False
    except Exception as e:
        print(f"Proxy {proxy} failed: {str(e)}")
        return False

proxy = "http://slrnujin-rotate:gp3pn6aymeka@p.webshare.io:80"  # Replace with one of your proxies
asyncio.run(test_proxy(proxy))
