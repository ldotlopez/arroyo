#!/usr/bin/env python3

if __name__ == '__main__':
    import sys

    import arroyo

    settings = arroyo.core.build_basic_settings(sys.argv)

    try:
        app = arroyo.Arroyo(settings=settings)
        app.run_from_args()
    except arroyo.exc.ArgumentError as e:
        print(str(e), file=sys.stderr)
        sys.exit(2)
