#!/usr/bin/env python3
# -*- coding: utf-8 -*-

if __name__ == '__main__':
    import sys

    import arroyo

    settings = arroyo.core.build_basic_settings(sys.argv[1:])

    app = arroyo.Arroyo(settings=settings)
    app.execute(*sys.argv[1:])
