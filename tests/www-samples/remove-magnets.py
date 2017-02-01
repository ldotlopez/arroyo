#!/usr/bin/env python

import re
import sys


class Rewriter:
    def __init__(self):
        self._d = {}
        self._i = 0

    def get_fake_id(self, x):
        if x not in self._d:
            r = "{0:040x}".format(self._i)
            self._i += 1
            self._d[x] = r
            return r
        else:
            return self._d[x]

    def rewrite(self, buff):
        return re.sub(
            r'([a-f0-9]{40})',
            lambda m: self.get_fake_id(m.group(1)),
            buff)


if __name__ == '__main__':
    print(Rewriter().rewrite(sys.stdin.read()), file=sys.stdout)
