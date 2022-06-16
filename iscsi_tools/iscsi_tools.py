#!/user/bin/env python3
# -*- coding: utf-8 -*-

from .cmd_utils import exec_cmd


def run(cmd):
    cmd = cmd.split( )
    r, out, e = exec_cmd(cmd)
    return out.decode("utf-8")

def parse(out):
    res = []
    for line in out.splitlines():
        rest, iqn = line.split()
        rest, tpgt = rest.split(",")
        ip, port = rest.split(':', 1)
        res.append({ "iqn": iqn, "portal": ip, "port":port , "iqn": iqn})
    return res


def node_logout(node):
    print("-----node-logout----")
    node_cmd = "iscsiadm -m node --targetname %(iqn)s -p %(portal)s:%(port)s"
    cmd = node_cmd + " " + "--logout"
    out = run(cmd % node)

def node_login(node):
    print("-----node-login----")
    node_cmd = "iscsiadm -m node --targetname %(iqn)s -p %(portal)s:%(port)s"
    cmd = node_cmd + " " + "-l"
    out = run(cmd % node)

def node_delete(node):
    print("-----node-delete----")
    node_cmd = "iscsiadm -m node --targetname %(iqn)s -p %(portal)s:%(port)s"
    cmd = node_cmd + " " + "-o delete"
    out = run(cmd % node)

def get_node_list():
    node_list_cmd = "iscsiadm -m node"
    out = run(node_list_cmd)
    return parse(out)

def node_discovery(portal):
    cmd = "iscsiadm --mode discovery --type sendtargets --portal %s" % portal
    out = run(cmd)
    return parse(out)

def clean_all():
    print("----clean all nodes-----")
    nodes = get_node_list()
    for node in nodes:
        node_logout(node)
        node_delete(node)

if __name__ == '__main__':
    clean_all()
    ips = [
        "10.0.0.4",
        "10.0.0.5",
        "10.0.0.6",
        "10.0.0.7",
        "10.0.0.8",
    ]
    all_nodes = []
    for ip in ips:
        nodes = node_discovery(ip)
        all_nodes += nodes
    for node in all_nodes:
        node_login(node)
