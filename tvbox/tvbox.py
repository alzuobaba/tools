#!/user/bin/env python3
# -*- coding: utf-8 -*-
import base64
import hashlib
import json
import os
import sys
import requests
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

DOWNLOAD_MODE = ['serial', 'parallel']
CLAN_PREFIX = 'clan://'
HTTPS_PREFIX = ('https://', 'http://')
VALID_FILE_SUFFIX = ('.jar', '.json', '.txt')
IGNORE_SUFFIX = ("vod/", "vod")

Failed_URLS = set()


def add_failed(func, *args, **kwargs):
    def wrap(*args, **kwargs):
        file_url = kwargs.get('file_url')
        clan_url = func(*args, **kwargs)
        if file_url == clan_url:
            Failed_URLS.add(file_url)
        return clan_url

    return wrap


def md5_calculate(filepath):
    md5_hash = hashlib.md5()
    with open(filepath, "rb") as f:
        #  the iter() function needs an empty byte string
        #  for the returned iterator to halt (停止) at EOF,
        #  since read() returns b'' (not just '').
        for byte_block in iter(lambda: f.read(8192), b""):
            md5_hash.update(byte_block)
        return md5_hash.hexdigest()


class tvBoxConfig(object):

    def __init__(
            self, root_dir,
            clan_dir="TVBox", cache_root=False,
            update_cache_file=False, max_worker=None,
            download_mode='parallel'):
        """
        :param root_dir: 根路径内的子路径
        :param clan_dir: 根路径默认为TVBox
        :param cache_root: 是否保存原远程json
        :param update_cache_file: 是否更新本地文件
        :param max_worker: 线程数，最大32 默认cpu-cores+4
        """
        self.requests = self._init_session()
        self.root_dir = root_dir
        self.clan_dir = clan_dir
        self.cache_root = cache_root
        self.update_cache_file = update_cache_file
        self.max_worker = max_worker
        self.download_mode = download_mode
        if not os.path.exists(self.root_dir):
            os.mkdir(self.root_dir)

    @staticmethod
    def _init_session():
        retry_strategy = Retry(
            total=3,
            status_forcelist=[429, 500, 502, 503, 504],
            method_whitelist=["HEAD", "GET", "OPTIONS"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        request = requests.Session()
        request.mount("https://", adapter)
        request.mount("http://", adapter)
        return request

    def _parse_remote_root(self, config_url):
        try:
            resp = self.requests.get(config_url, timeout=(7, 15))
        except requests.exceptions.RequestException:
            raise Exception('请求配置失败:{}，请检查网络链接是否正常。'.format(config_url))
        if resp.status_code != 200:
            raise Exception('配置下载失败')
        return resp.text

    def _parse_local_root(self, filename):
        if not os.path.exists(filename):
            raise Exception("输入的本地文件：%s不存在。" % filename)
        with open(filename, encoding='utf-8') as f:
            text = f.read()
        return text

    def parse(self, config_url=None, config_file=None):
        root = self._parse_root(config_url=config_url, filename=config_file)
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
            f.write(json.dumps(root, ensure_ascii=False, indent=4))

    def _cache_sites(self, root):
        sites = root['sites']
        if self.download_mode == 'parallel':
            with ThreadPoolExecutor() as pool:
                pool.map(self._cache_site, sites)
        elif self.download_mode == 'serial':
            for site in sites:
                self._cache_site(site)

    def _cache_site(self, site):
        # add multi spider support.
        if site.get('spider'):
            self._cache_spider(site, use_file_name=True)
        if not 'ext' in site or not site['ext']:
            return
        file_url = site['ext']
        filename = os.path.basename(file_url)
        site_api = str(site['api']).lower()
        if site_api.startswith("csp_"):
            filename = "{}_{}".format(site_api, filename)
        filepath = self._get_file_path(filename=filename, parent_dir='sites')
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

    def _cache_spider(self, root, use_file_name=False):
        spider_name = 'spider.jar'
        spider = root['spider'].split(";")[0]
        if use_file_name:
            spider_name = os.path.basename(spider)
        file_path = self._get_file_path(filename=spider_name, parent_dir='jar')
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

    @add_failed
    def _download(self, file_url, file_path):
        if not file_url:
            return file_url
        elif file_url.startswith(CLAN_PREFIX):
            print("略过clan://路径：{}".format(file_url))
            return file_url
        elif not file_url.startswith(HTTPS_PREFIX):
            print('unknown url schema：{}'.format(file_url))
            return file_url
        elif not file_url.endswith(VALID_FILE_SUFFIX):
            if not file_url.endswith(IGNORE_SUFFIX):
                print("略过未定义后缀文件路径：{}".format(file_url))
            return file_url
        clan_addr = self._get_clan_addr(filepath=file_path)
        if os.path.exists(file_path) and not self.update_cache_file:
            return clan_addr
        dirname = os.path.dirname(file_path)
        if not os.path.exists(dirname):
            os.makedirs(dirname)
        # print('req start:{}'.format(file_url))
        try:
            req = self.requests.get(file_url, timeout=(7, 15), stream=True)
        except requests.exceptions.RequestException:
            print('req failed:{}，请检查网络链接是否正常。'.format(file_url))
            return file_url
        if req.status_code != 200:
            print('req failed code {}:{}'.format(req.status_code, file_url))
            return file_url
        # print('req ok:{}'.format(file_url))
        md5_check = False
        if os.path.exists(file_path):
            # os.remove(file_path)
            md5_check = True
            old_check_sum = md5_calculate(file_path)
        md5_hash = hashlib.md5()
        with open(file_path, "wb") as f:
            for chunk in req.iter_content(chunk_size=8192):
                f.write(chunk)
                md5_hash.update(chunk)
        if md5_check:
            new_checksum = md5_hash.hexdigest()
            if new_checksum != old_check_sum:
                print("update file:{}".format(file_url))
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

    def _parse_root(self, config_url=None, filename=None):
        if config_url:
            text = self._parse_remote_root(config_url)
        elif filename:
            text = self._parse_local_root(filename)
        else:
            raise Exception("请输入正确的配置")
        root = self._remove_comment(text)
        self._cache_root(root)
        return root


def local_download():
    os.chdir(sys.path[0])
    print("本脚本推荐放置于根盘/TVBox目录运行, 如果保存失败可以运行多次。")
    parse_index = input("请选择解析模式: 1.解析远程配置 2.解析本地文件。默认为1:")
    if not parse_index or parse_index not in ["1", "2"]:
        parse_index = "1"
    if parse_index == "1":
        parse_remote()
    else:
        parse_local()


def parse_remote():
    print("远程解析模式：-------")
    while True:
        config_url = input("请输入tvbox远程配置url,按q退出:").strip()
        if config_url == 'q':
            exit()
        if config_url and config_url.startswith(HTTPS_PREFIX):
            break
        print("请输入正确的url。")
    file_name = os.path.basename(config_url).split('.')[0]
    root_dir = input("请输入配置保存路径,默认为[{}]:".format(file_name))
    if not root_dir:
        root_dir = file_name
    parse_common(root_dir, config_url=config_url)


def parse_local():
    print("本地解析模式：-------")
    print("请将待解析本地配置放置于脚本同级目录。")
    print("本地配置解析不会解析clan://路径，仅将远程文件本地化，请手动修正原有clan://路径")
    while True:
        config_file = input("请输入tvbox本地配置名称,按q退出:").strip()
        if config_file == 'q':
            exit()
        if not config_file:
            print("请输入正确的本地文件名称")
        elif not os.path.exists(config_file):
            print("未找到相关文件，请查看配置文件是否与脚本处于同级目录")
        else:
            break
    file_name = os.path.basename(config_file).split('.')[0]
    root_dir = input("请输入配置保存路径,默认为[{}]:".format(file_name))
    if not root_dir:
        root_dir = file_name
    parse_common(root_dir, config_file=config_file)


def parse_common(root_dir, config_url=None, config_file=None):
    download_index = input("请选择下载模式: 1.串行下载 2.并行下载。默认为2:")
    if not download_index or download_index not in ["1", "2"]:
        download_index = 2
    else:
        download_index = int(download_index)

    update_file_flag = input("是否更新本地文件: 1.否 2.是。默认为1:")
    if not update_file_flag or update_file_flag not in ["1", "2"] or update_file_flag == '1':
        update_file_flag = False
    else:
        update_file_flag = True

    download_mode = DOWNLOAD_MODE[download_index - 1]
    tv = tvBoxConfig(root_dir=root_dir, download_mode=download_mode, update_cache_file=update_file_flag)
    tv.parse(config_url=config_url, config_file=config_file)
    print("----------")
    print("以下链接处理失败，请再次运行本脚本或者手动处理:")
    print("start:-----failed list-----")
    for file_url in Failed_URLS:
        if not file_url.endswith(IGNORE_SUFFIX):
            print(file_url)
    print("end:-----failed list-----")

    print("保存结束。请查看root-local.json")
    print("请将保存的目录移动至根盘TVBox。")
    print("本地链接：{}".format(tv.get_subscribe_url()))


if __name__ == '__main__':
    print("----tvbox远程配置本地化脚本----")
    print("source: https://raw.githubusercontent.com/alzuobaba/tools/master/tvbox/tvbox.py")
    print("author: alzuobaba")
    print("-----------------------------")
    local_download()

# https://freed.yuanhsing.cf/TVBox/meowcf.json
# https://shuyuan.miaogongzi.net/shuyuan/1658731733.json
