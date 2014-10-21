#!/usr/bin/env python3


if __name__ == '__main__':
    import sys
    from arroyo import plugins
    from arroyo.app import app
    try:
        app.run()
    except plugins.ArgumentError as e:
        print(str(e), file=sys.stderr)
        sys.exit(2)
