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

proxy = "http://zgjifncy:lclg2hmhbjav@38.153.152.244:9594"  # Replace with one of your proxies
asyncio.run(test_proxy(proxy))
