#!/usr/bin/env python

import re
import sys


class Sha1Generator:
    def __init__(self):
        self._d = {}
        self._i = 0

    def replace(self, x):
        if x not in self._d:
            r = "{0:040x}".format(self._i)
            self._i += 1
            self._d[x] = r
            return r
        else:
            return self._d[x]

for x in sys.argv[1:]:
    repl = Sha1Generator()
    with open(x) as fh:
        buff = fh.read()
        buff = re.sub(
            r'([a-f0-9]{40})',
            lambda m: repl.replace(m.group(1)),
            buff)

        print(buff)
