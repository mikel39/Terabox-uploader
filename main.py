import toml
import httpx
from terabox import Terabox
import sys
from pathlib import Path
import asyncio

config = Path(__file__).parent / 'config.toml'
file = toml.load(config)

path = sys.argv[1]
remote_path = sys.argv[2] if len(sys.argv) > 2 else None

if remote_path:
    file['config']['target_path'] = remote_path

transport = httpx.AsyncHTTPTransport(retries=5)


async def main():
    async with httpx.AsyncClient(
        base_url='https://www.terabox.com',
        headers=file['headers'],
        cookies=file['cookies'],
        follow_redirects=True,
        timeout=20.0,
        transport=transport,
    ) as client:
        terabox = Terabox(client, file['config'])
        await terabox.upload_files(path)


asyncio.run(main())
