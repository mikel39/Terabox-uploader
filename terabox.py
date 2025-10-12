import json
import re
import urllib.parse
from pathlib import Path
from decorators import logger


class Terabox:
    def __init__(self, client, config):
        self.client = client
        self.target_path = config['target_path']
        self.chunk_size = config['chunck_size'] * 1024 * 1024
        self.remove = config['remove_after']
        self.bdstoken, self.jstoken = self._get_info()

    def _get_info(self):
        response = self.client.get('')
        data = urllib.parse.unquote(response.text)
        bdstoken = re.search(r'"(bdstoken)\W{3}(\w*)",', data, re.I)
        jstoken = re.search(r'"?(jstoken).*fn\W*(\w*)', data, re.I)

        if not bdstoken or not jstoken:
            print('Failed to get jstoken, bdstoken')
            return None, None

        return bdstoken.group(2), jstoken.group(2)

    def _precreate(self, path_file, size, blocklist):
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
        response = self.client.post(precreate_url, data=data)
        response = response.json()

        if response['errmsg']:
            print(f'Error at PC error message: {response["errmsg"]}')
            return

        return response['uploadid']

    def _upload(self, uploadid, file_name, chunck, part):
        path = Path(self.target_path) / file_name
        upload_url = f'https://c-jp.terabox.com/rest/2.0/pcs/superfile2?method=upload&app_id=250528&channel=dubox&clienttype=0&web=1&path={path}&uploadid={uploadid}&uploadsign=0&partseq={part}'
        response = self.client.post(upload_url, files={'file': chunck})
        response = response.json()

        md5 = response.get('md5')
        if not md5:
            print(f'Error at UP error message: {response["error_msg"]}')
            return

        return md5

    def _create(self, path_file, size, uploadid, blocklist):
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

        response = self.client.post(create_url, data=data)
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
    def _upload_file(self, path_file, remote_path):
        with open(path_file, 'rb') as file:
            size, blocklist = self._get_bl_hash(path_file)
            uploadid = self._precreate(remote_path, size, blocklist)

            if not uploadid:
                return

            part = 0
            hashes = []

            while True:
                chunk = file.read(self.chunk_size)

                if not chunk:
                    break

                md5 = self._upload(uploadid, remote_path, chunk, part)

                if not md5:
                    return

                hashes.append(md5)
                part += 1

            success = self._create(remote_path, size, uploadid, json.dumps(hashes))

            if success and self.remove:
                Path(path_file).unlink()

            return success

    def upload_files(self, files):
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

            self._upload_file(file, str(remote_path))
