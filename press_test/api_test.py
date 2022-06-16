#!/usr/bin/env python
# -*- coding:utf-8 -*-

import requests, time, json, threading, random
import urllib3
from concurrent.futures import ThreadPoolExecutor
urllib3.disable_warnings()

class Presstest(object):
    
    def __init__(self, login_url, press_url, username, password):
        self.login_url = login_url
        self.press_url = press_url
        self.username = username
        self.password = password
        self.session = requests.session()

    def login(self):
        '''登陆获取session'''
        print("portal login")
        data = {
            "username": self.username,
            "password": self.password,
        }
        rsp = self.session.post(url=self.login_url, data=data, verify=False)
        print(self.login_url, data, rsp.status_code, rsp.text)
        if rsp.status_code != 200:
            raise Exception("portal login error")

    def testinterface(self):
        '''压测接口'''
        rsp = None
        print("----start------")
        try:
            rsp = self.session.get(self.press_url, verify=False)
        except Exception as e:
            print(e)
        print(rsp.status_code)

    def testonework(self):
        '''一次并发处理单个任务'''
        i = 0
        while i < ONE_WORKER_NUM:
            i += 1
            self.testinterface()
        time.sleep(0.1)

    def run(self, func):
        '''使用多线程进程并发测试'''
        t1 = time.time()
        func()
        t2 = time.time()

        print("===============压测结果===================")
        print("URL:", self.press_url)
        print("任务数量:", THREAD_NUM, "*", ONE_WORKER_NUM, "=", THREAD_NUM * ONE_WORKER_NUM)
        print("总耗时(秒):", t2 - t1)
        print("每次请求耗时(秒):", (t2 - t1) / (THREAD_NUM * ONE_WORKER_NUM))
        print("每秒承载请求数:", 1 / ((t2 - t1) / (THREAD_NUM * ONE_WORKER_NUM)))

    def _run1(self):
        print("---use run1----")
        Threads = []
        for i in range(THREAD_NUM):
            t = threading.Thread(target=self.testonework, name="T" + str(i))
            t.setDaemon(True)
            Threads.append(t)

        for t in Threads:
            t.start()
        for t in Threads:
            t.join()

    def _run2(self):
        print("---use run2----")
        futures = []
        with ThreadPoolExecutor(max_workers=THREAD_NUM) as t:
            for i in range(THREAD_NUM):
                future = t.submit(self.testonework)
        #         futures.append(future)
        #
        # for future in futures:
        #     print(future.result())


if __name__ == '__main__':
    vip = "xxxx"
    username = "admin"
    password = "xxxx"
    press_url = 'https://{}/xxxxx'.format(vip)

    login_url = 'https://{}/xxxxx/login/'.format(vip)


    THREAD_NUM = 10  # 并发线程总数
    ONE_WORKER_NUM = 1  # 每个线程的循环次数

    obj = Presstest(login_url=login_url, press_url=press_url, username=username, password=password)
    obj.login()
    # obj.testinterface()
    obj.run(obj._run1)
    obj.run(obj._run2)
