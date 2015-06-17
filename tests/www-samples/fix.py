#!/usr/bin/env python

import re
import sys


def sha1_gen():
    i = 0
    while True:
        yield "{0:040x}".format(i)
        i = i + 1

for x in sys.argv[1:]:

    with open(x) as fh:
        g = sha1_gen()
        buff = fh.read()
        buff = re.sub(r'[a-f0-9]{40}', lambda m: next(g), buff)

        print(buff)
