#!/user/bin/env python3
# -*- coding: utf-8 -*-


import re
import copy
import logging

LOG = logging.getLogger(__name__)


class Config(object):
    _path = None
    _content = None

    def __init__(self, path):
        self._path = path
        with open(path, 'r') as f:
            self._content = f.read()

    def _get_section(self, section):
        """Get section form config"""
        content = self._content
        r = re.search(r'^\[%s\].*^\[' % section, content, re.M | re.S)
        if r:
            return content[r.start(): r.end() - 1]
        r = re.search(r'^\[%s\].*' % section, content, re.M | re.S)
        if r:
            return content[r.start(): r.end()]
        raise Exception("Section %s NotFound" % section)

    def _get_key(self, section, key, multiple=False):
        """Get key form section"""
        if not section:
            return None
        values = []
        for line in section.split("\n"):
            r = re.search(r'%s\s?=\s?(.*)' % key, line)
            if r:
                value = r.groups()[0]
                values.append(value)
        if multiple:
            return values
        return values[-1] if values else None

    def _remove_key(self, section, key):
        """Remove key form section"""
        n_sec = re.sub(r'%s\s?=\s?.*\n' % key, '', section, re.S)
        return n_sec

    def _add_key(self, section, key, values):
        """Add key to section"""
        if not isinstance(values, list):
            values = [values]
        for value in values:
            section += "%s = %s\n" % (key, value)
        return section

    def update(self, section, key, value):
        """Update Config"""
        LOG.info("osconfig set [%s] %s = %s", section, key, value)
        o_sec = self._get_section(section)
        n_sec = copy.copy(o_sec)
        n_sec = self._remove_key(n_sec, key)
        n_sec = self._add_key(n_sec, key, value)
        self._content = self._content.replace(o_sec, n_sec)

    def remove(self, section, key):
        """Update Config"""
        LOG.info("osconfig remove [%s] %s", section, key)
        o_sec = self._get_section(section)
        n_sec = copy.copy(o_sec)
        n_sec = self._remove_key(n_sec, key)
        self._content = self._content.replace(o_sec, n_sec)

    def get(self, section, key, multiple=False):
        """Get value form config"""
        section = self._get_section(section)
        value = self._get_key(section, key, multiple=multiple)
        LOG.info("osconfig get [%s] %s = %s", section, key, value)
        return value

    def save(self):
        LOG.info("osconfig save to %s", self._path)
        with open(self._path, 'w') as f:
            f.write(self._content)


with open('test.conf') as f:
    content = f.read()

if __name__ == '__main__':
    config = Config('test.conf')
    names = config.get('test1', 'name', multiple=True)
    print(names)
    config.update('test2', 'sex', 'male')
    config.save()
