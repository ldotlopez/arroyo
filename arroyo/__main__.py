#!/usr/bin/env python3


if __name__ == '__main__':
    import sys
    import arroyo.exc
    from arroyo.app import app
    try:
        app.run()
    except arroyo.exc.ArgumentError as e:
        print(str(e), file=sys.stderr)
        sys.exit(2)
