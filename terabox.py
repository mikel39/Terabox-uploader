import json
import re
import urllib.parse
from pathlib import Path
from decorators import logger
import aiofiles
import asyncio
import gc


class Terabox:
    def __init__(self, client, config):
        self.client = client
        self.target_path = config['target_path']
        self.chunk_size = config['chunck_size'] * 1024 * 1024
        self.remove = config['remove_after']
        self.parallel = config['parallel']
        self.jstoken = None
        self.bdstoken = None

    async def _get_info(self):
        response = await self.client.get('')
        data = urllib.parse.unquote(response.text)
        bdstoken = re.search(r'"(bdstoken)\W{3}(\w*)",', data, re.I)
        jstoken = re.search(r'"?(jstoken).*fn\W*(\w*)', data, re.I)

        if not bdstoken or not jstoken:
            print('Failed to get jstoken, bdstoken')
            return

        self.bdstoken = bdstoken.group(2)
        self.jstoken = jstoken.group(2)

    async def _precreate(self, path_file, size, blocklist):
        path = Path(self.target_path) / path_file
        path = str(path).replace(':', '').replace('?', '')

        data = {
            'target_path': self.target_path,
            'path': path,
            'autoinit': 1,
            'size': size,
            'block_list': blocklist,
        }
        precreate_url = f'/api/precreate?app_id=250528&web=1&channel=dubox&clienttype=0&jsToken={self.jstoken}'
        response = await self.client.post(precreate_url, data=data)
        response = response.json()

        if response['errmsg']:
            print(f'Error at PC error message: {response["errmsg"]}')
            return

        return response['uploadid']

    async def _upload(self, uploadid, file_name, chunck, part):
        path = Path(self.target_path) / file_name
        upload_url = f'https://c-jp.terabox.com/rest/2.0/pcs/superfile2?method=upload&app_id=250528&channel=dubox&clienttype=0&web=1&path={path}&uploadid={uploadid}&uploadsign=0&partseq={part}'
        response = await self.client.post(
            upload_url, files={'file': chunck}, timeout=60.0
        )
        response = response.json()

        md5 = response.get('md5')
        if not md5:
            print(f'Error at UP error message: {response["error_msg"]}')
            return

        return md5

    async def _create(self, path_file, size, uploadid, blocklist):
        create_url = f'/api/create?isdir=0&rtype=1&bdstoken={self.bdstoken}&app_id=250528&web=1&channel=dubox&clienttype=0&jsToken={self.jstoken}'

        path = Path(self.target_path) / path_file
        path = str(path).replace(':', '').replace('?', '')

        data = {
            'path': path,
            'size': size,
            'uploadid': uploadid,
            'target_path': self.target_path,
            'block_list': blocklist,
        }

        response = await self.client.post(create_url, data=data)
        response = response.json()

        if response['errmsg']:
            print(f'Error at CR  error message: {response["errmsg"]}')
            return

        return True

    def _get_bl_hash(self, path_file):
        path = Path(path_file)
        size = path.stat().st_size
        md51 = '5910a591dd8fc18c32a8f3df4fdc1761'
        md52 = 'a5fc157d78e6ad1c7e114b056c92821e'
        blocklist = [md51] if size < self.chunk_size else [md51, md52]
        blocklist = json.dumps(blocklist)
        return size, blocklist

    @logger
    async def _upload_file(self, path_file, remote_path):
        async with aiofiles.open(path_file, 'rb') as file:
            size, blocklist = self._get_bl_hash(path_file)
            uploadid = await self._precreate(remote_path, size, blocklist)

            if not uploadid:
                return

            part = 0
            hashes = []
            tasks = []

            while True:
                chunk = await file.read(self.chunk_size)

                if not chunk:
                    break

                md5 = self._upload(uploadid, remote_path, chunk, part)

                tasks.append(md5)

                if len(tasks) >= self.parallel:
                    result = await tasks.pop(0)
                    hashes.append(result)
                    gc.collect()

                part += 1

            if tasks:
                result = await asyncio.gather(*tasks)
                hashes.extend(result)
                tasks.clear()

            success = await self._create(
                remote_path, size, uploadid, json.dumps(hashes)
            )

            if success and self.remove:
                Path(path_file).unlink()

            return success

    async def upload_files(self, files):
        await self._get_info()

        if not self.bdstoken or not self.jstoken:
            return

        paths = []

        def get_files(*f):
            for file in f:
                path = Path(file)
                isdir = path.is_dir()
                if isdir:
                    get_files(*path.iterdir())
                else:
                    paths.append(str(path))

        get_files(files)

        path = Path(files)

        for file in paths:
            remote_path = Path(file).relative_to(Path(*path.parts[0:-1]))

            await self._upload_file(file, str(remote_path))
