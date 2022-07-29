#!/user/bin/env python3
# -*- coding: utf-8 -*-
import json
import os
import base64
# from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import requests
from pathlib import Path


class tvBoxConfig(object):
    def __init__(self, url, root_dir, clan_dir="TVBox", cache_root=False, update_cache_file=False, max_worker=None):
        """

        :param url: tvbox or pluto player 配置地址
        :param root_dir: 根路径内的子路径
        :param clan_dir: 根路径默认为TVBox
        :param cache_root: 是否保存原远程json
        :param update_cache_file: 是否更新本地文件
        :param max_worker: 线程数，最大32 默认cpu-cores+4
        """
        self.url = url
        self.root_dir = root_dir
        self.clan_dir = clan_dir
        self.cache_root = cache_root
        self.update_cache_file = update_cache_file
        self.max_worker = max_worker
        if not os.path.exists(self.root_dir):
            os.mkdir(self.root_dir)

    def _get_root(self):
        resp = requests.get(self.url)
        if resp.status_code != 200:
            raise Exception('配置下载失败')
        text = resp.text
        # for test ------- start
        # root_path = self._get_file_path('root.json')
        # with open(root_path, encoding='utf-8') as f:
        #     text = f.read()
        # for test ------- end
        root = self._remove_comment(text)
        self._cache_root(root)
        return root

    def parse(self):
        root = self._get_root()
        self._cache_spider(root)
        self._cache_lives(root)
        self._cache_sites(root)
        self._save_file(root, filename='root-local.json')

    def _cache_root(self, root, filename='root.json'):
        if not self.cache_root:
            return
        self._save_file(root, filename)

    def _save_file(self, root, filename):
        root_path = self._get_file_path(filename)
        with open(root_path, mode='w', encoding='utf-8') as f:
            f.write(json.dumps(root, ensure_ascii=False))

    def _cache_sites(self, root):
        sites = root['sites']
        # with ThreadPoolExecutor(max_workers=32) as pool:
        #     pool.map(self._cache_site, sites)
        for site in sites:
            self._cache_site(site)

    def _cache_site(self, site):
        if not 'ext' in site:
            return
        file_url = site['ext']
        filepath = self._get_file_path(filename=os.path.basename(file_url), parent_dir='sites')
        site['ext'] = self._download(file_url=file_url, file_path=filepath)

    def _cache_lives(self, root):
        lives = root['lives']
        for live in lives:
            for channel in live["channels"]:
                urls = []
                for url in channel['urls']:
                    url_list = url.split('ext=')
                    file_url = str(base64.b64decode(url_list[-1]).decode('utf-8'))
                    filepath = self._get_file_path(filename=os.path.basename(file_url), parent_dir='tv')
                    clan_addr = self._download(file_url=file_url, file_path=filepath)
                    url_list[-1] = base64.b64encode(clan_addr.encode('utf-8')).decode('utf-8')
                    urls.append('ext='.join(url_list))
                channel['urls'] = urls

    def _cache_spider(self, root):
        spider = root['spider']
        file_path = self._get_file_path(filename='spider.jar', parent_dir='jar')
        root['spider'] = self._download(file_url=spider, file_path=file_path)

    def _get_file_path(self, filename, parent_dir=None):
        if not parent_dir:
            path = os.path.join(self.root_dir, filename)
        else:
            path = os.path.join(self.root_dir, parent_dir, filename)
        return path

    def _get_clan_addr(self, filepath):
        filepath = Path(filepath).as_posix()
        return "clan://localhost/{}/{}".format(self.clan_dir, filepath)

    def _download(self, file_url, file_path):
        if not file_url.startswith(('https://', 'http://')):
            raise Exception('unknown url schema：{}'.format(file_url))
        clan_addr = self._get_clan_addr(filepath=file_path)
        if os.path.exists(file_path) and not self.update_cache_file:
            return clan_addr
        dirname = os.path.dirname(file_path)
        if not os.path.exists(dirname):
            os.makedirs(dirname)
        req = requests.get(file_url, stream=True)
        if req.status_code != 200:
            print('req failed: {}'.format(file_url))
            return file_url
        print('req ok:{}'.format(file_url))
        if os.path.exists(file_path):
            os.remove(file_path)
        with open(file_path, "wb") as f:
            for chunk in req.iter_content(chunk_size=8192):  # 每次加载1024字节
                f.write(chunk)
        return clan_addr

    @staticmethod
    def _remove_comment(resp):
        all_lines = resp.splitlines()
        pass
        res = []
        for line in all_lines:
            line = line.strip()
            if line.startswith(("#", "//")):
                continue
            res.append(line)
        str_res = "".join(res)
        return json.loads(str_res)


if __name__ == '__main__':
    config_url = 'https://freed.yuanhsing.cf/TVBox/meowcf.json'
    tv = tvBoxConfig(config_url, 'yuanhsing')
    tv.parse()
