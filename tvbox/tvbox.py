#!/user/bin/env python3
# -*- coding: utf-8 -*-
import json
import os
import base64
import requests
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

DOWNLOAD_MODE = ['serial', 'parallel']


class tvBoxConfig(object):
    valid_file_suffix = ('.jar', '.json', '.txt')

    def __init__(
            self, url, root_dir,
            clan_dir="TVBox", cache_root=False,
            update_cache_file=False, max_worker=None,
            download_mode='parallel'):
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
        self.download_mode = download_mode
        if not os.path.exists(self.root_dir):
            os.mkdir(self.root_dir)

    def _get_root(self):
        try:
            resp = requests.get(self.url, timeout=(5, 10))
        except requests.exceptions.RequestException:
            raise Exception('请求配置失败，请检查网络链接是否正常。')
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
        self._cache_root(root, local_root=True)

    def get_subscribe_url(self, ):
        root_path = self._get_file_path('root-local.json')
        return self._get_clan_addr(filepath=root_path, subscribe_url=True)

    def _cache_root(self, root, local_root=False):
        if not local_root:
            if not self.cache_root:
                return
            filename = 'root.json'
        else:
            filename = 'root-local.json'
        self._save_file(root, filename)

    def _save_file(self, root, filename):
        root_path = self._get_file_path(filename)
        with open(root_path, mode='w', encoding='utf-8') as f:
            f.write(json.dumps(root, ensure_ascii=False))

    def _cache_sites(self, root):
        sites = root['sites']
        if self.download_mode == 'parallel':
            with ThreadPoolExecutor() as pool:
                pool.map(self._cache_site, sites)
        elif self.download_mode == 'serial':
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

    def _get_clan_addr(self, filepath, subscribe_url=False):
        filepath = Path(filepath).as_posix()
        if subscribe_url:
            return "clan://localhost/{}/{}".format(self.clan_dir, filepath)
        return "clan://{}/{}".format(self.clan_dir, filepath)

    def _download(self, file_url, file_path):
        if not file_url.startswith(('https://', 'http://')):
            raise Exception('unknown url schema：{}'.format(file_url))
        clan_addr = self._get_clan_addr(filepath=file_path)
        if not file_url.endswith(self.valid_file_suffix):
            return file_url
        if os.path.exists(file_path) and not self.update_cache_file:
            return clan_addr
        print(file_url)
        dirname = os.path.dirname(file_path)
        if not os.path.exists(dirname):
            os.makedirs(dirname)
        print('req start:{}'.format(file_url))
        req = requests.get(file_url, timeout=(5, 10), stream=True)
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


def local_download():
    while True:
        config_url = input("请输入tvbox远程配置url:").strip()
        if config_url and config_url.startswith(('https://', 'http://')):
            break
        print("请输入正确的url。")

    file_name = os.path.basename(config_url).split('.')[0]
    root_dir = input("请输入本地配置保存路径,默认为:[{}]".format(file_name))
    if not root_dir:
        root_dir = file_name

    print("请选择下载模式: 1.串行下载 2.并行下载。默认为: 2")
    download_index = input("请输入下载模式: ")
    if not download_index or download_index not in ["1", "2"]:
        download_index = 2
    else:
        download_index = int(download_index)

    download_mode = DOWNLOAD_MODE[download_index - 1]
    tv = tvBoxConfig(url=config_url, root_dir=root_dir, download_mode=download_mode)
    tv.parse()
    print("保存结束。请查看root-local.json")
    print("请将保存的目录移动至根盘TVBox。")
    print("本地链接：{}".format(tv.get_subscribe_url()))

if __name__ == '__main__':
    print("----tvbox远程配置本地化脚本----")
    print("source: https://raw.githubusercontent.com/alzuobaba/tools/master/tvbox/tvbox.py")
    print("author: alzuobaba")
    print("本脚本推荐放置于根盘/TVBox目录运行, 如果保存失败可以运行多次。")
    print("-----------------------------")
    local_download()

# https://freed.yuanhsing.cf/TVBox/meowcf.json
