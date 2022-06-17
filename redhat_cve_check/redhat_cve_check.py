# coding=utf-8
# openpyxl require python3
import json
from pprint import pprint

import requests
from openpyxl import load_workbook
from lxml import etree
import re

# 抽取漏洞出现比较多的关键词
keys = ['ssh', 'python', 'nginx', 'apache', 'openssl']

# CVE 详情页面，和errata rpm页面，平台名称有差异，此处做个map
REDHAT_PLATFORM_NAME = {
    # <product alias name>: <affect name in cve page > ,<name for rpm packages locate>
    "rhel7": ('Red Hat Enterprise Linux 7', 'Red Hat Enterprise Linux Server 7')
}

def get_cves():
    # 打开一个workbook
    wb = load_workbook(filename="cve.xlsx")

    # 获取当前活跃的worksheet,默认就是第一个worksheet
    # ws = wb.active

    # 当然也可以使用下面的方法

    # 获取所有表格(worksheet)的名字
    sheets = wb.sheetnames
    # 第一个表格的名称
    sheet_first = sheets[0]
    # 获取特定的worksheet
    ws = wb[sheet_first]

    # 获取表格所有行和列，两者都是可迭代的
    cves = []
    for row in ws.iter_rows(min_row=2, max_row=ws.max_row - 1):
        # print(line)
        cve_num = None
        title = row[1].value
        level = row[2].value
        search_obj = re.search('cve.*\d', title, re.I)
        if search_obj:
            cve_num = search_obj.group()
        key = next(filter(lambda x: x in title.lower(), keys), 'other')
        item_obj = Cve(cve_num, title, level, key)
        cves.append(item_obj)
    return cves


class Cve(object):
    errata_info = None

    def __init__(self, num, title=None, level=None, key=None, description=None):
        self.cve_num = num
        self.title = title
        self.level = level
        self.key = key
        self.description = description

    def to_json(self):
        return json.dumps(self.__dict__)


# class RedHatCVECheck(object):


class RedHatCveCheck(object):

    def __init__(self, cve_num, affect_product_alias='rhel7'):
        self.cve_num = cve_num
        self.platform_name_in_cve = REDHAT_PLATFORM_NAME[affect_product_alias][0]
        self.platform_name_in_errata = REDHAT_PLATFORM_NAME[affect_product_alias][1]

    def get_cve_erratas(self):
        url = "https://access.redhat.com/api/redhat_node/{}.json".format(self.cve_num)
        print(url)
        cve_state = '红帽已处理'
        affect_products = []
        response = requests.request("GET", url)
        if response.status_code == 200:
            res = response.json()
            objs = res['field_cve_releases_txt']['und'][0]['object']
            objs = [obj for obj in objs if obj['product'] == self.platform_name_in_cve]
            if not objs:
                cve_state = "未找到相关修复：%s" % self.platform_name
            for obj in objs:
                fixed_rpms = None
                errate_url = obj['advisory'].get('url')
                if errate_url:
                    fixed_rpms = self._get_errata_rpm_packages(errate_url)
                products = {
                    'errate_state': obj['state'],
                    'errate_url': errate_url,
                    'fixed_rpms': fixed_rpms,
                    'errate_package_name': obj['package']
                }
                affect_products.append(products)
        else:
            cve_state = '红帽未收录'
        errata_infos = {
            'cve_url': url,
            'cve_state': cve_state,
            'affect_products': affect_products
        }
        return errata_infos

    def _get_errata_rpm_packages(self, errate_url):
        rpm_infos = None
        response = requests.request("GET", errate_url)
        html = etree.HTML(response.text)
        title_node = html.xpath('//*[@id="packages"]/h2[text()="{}"]'.format(self.platform_name_in_errata))
        if title_node and title_node[0].getnext().tag == 'table':
            table = title_node[0].getnext()
            rpm_infos = table.xpath('.//tr/td[@class="name"]//text()')
            rpm_infos = [str(s).strip() for s in rpm_infos]
        return rpm_infos


if __name__ == '__main__':
    cves = get_cves()
    check = RedHatCveCheck(cves[1].cve_num)
    errates = check.get_cve_erratas()
    pprint(errates)
    # for cve in cves:
    #     check = RedHatCveCheck(cve.cve_num)
    #     check.get_cve_erratas()
        # errata_details = get_errata_details(cve_num)
        # cve['errata_details'] = errata_details
        # pprint(cve.__dict__)
        # print('-------')

# with open('cve_rpms.info', 'w') as file:
#     for cve, cve_num in cves.items():
#         print(cve)
#         rpm_info_str = get_errata_detail(cve_num)
#         file.write(cve + '：\n')
#         file.write(rpm_info_str + '\n')
#         file.write('\n----------------------\n')

