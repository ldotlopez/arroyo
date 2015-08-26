#!/usr/bin/env python3
# -*- coding: utf-8 -*-

if __name__ == '__main__':
    import sys

    import arroyo

    settings = arroyo.core.build_basic_settings(sys.argv[1:])

    try:
        app = arroyo.Arroyo(settings=settings)
        app.run_from_args(sys.argv[1:])
    except arroyo.exc.ArgumentError as e:
        print(str(e), file=sys.stderr)
        sys.exit(2)
