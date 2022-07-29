#!/user/bin/env python3
# -*- coding: utf-8 -*-
import requests


class Quark(object):
    headers = {
        'content-type': 'application/json;charset=UTF-8',
        'cookie': ''
    }
    base_url = "https://drive.quark.cn/1/clouddrive/file/"

    def __init__(self, cookies):
        self.headers['cookie'] = cookies

    def retrive_dir_fids(self, dir_id=None):
        url = self.base_url + "sort?pr=ucpro&fr=pc&_size=200"
        if dir_id:
            url += "&pdir_fid={}".format(dir_id)
        response = requests.get(url, headers=self.headers)
        json_data = response.json()
        for item in json_data['data']['list']:
            print(item)
        return [item['fid'] for item in json_data['data']['list']]

    def retrive_download_urls(self, fids):
        url = self.base_url + "download?pr=ucpro&fr=pc"
        payload = {"fids": fids}
        response = requests.post(url, headers=self.headers, json=payload)
        json_data = response.json()
        return [item['download_url'] for item in json_data['data']]

    def retrive(self, url, method='GET'):
        resp = requests.request(method, url, headers=self.headers)
        print(resp.text)

if __name__ == '__main__':
    cookies = ''
    q = Quark(cookies)
    fids = q.retrive_dir_fids(dir_id='')
    dw_urls = q.retrive_download_urls(fids)
    for item in dw_urls:
        print(item)
