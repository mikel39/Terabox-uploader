import toml
import httpx
from terabox import Terabox
import sys
from pathlib import Path

config = Path(__file__).parent / 'config.toml'
file = toml.load(config)

path = sys.argv[1]
remote_path = sys.argv[2] if len(sys.argv) > 2 else None

if remote_path:
    file['config']['target_path'] = remote_path


with httpx.Client(
    base_url='https://www.terabox.com',
    headers=file['headers'],
    cookies=file['cookies'],
    follow_redirects=True,
    timeout=200.0,
) as client:
    terabox = Terabox(client, file['config'])
    terabox.upload_files(path)
