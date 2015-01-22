#!/usr/bin/env python3


if __name__ == '__main__':
    import sys

    import arroyo

    app = arroyo.Arroyo()

    extensions = {
        'importers': ('eztv', 'kickass', 'spanishtracker', 'thepiratebay'),
        'selectors': ('source', 'episode'),
        'commands': ('analyze', 'db', 'downloads', 'mediainfo', 'search'),
        'downloaders': ('mock', 'transmission')
    }

    for (k, v) in extensions.items():
        exts = ["%s.%s" % (k, e) for e in v]
        app.load_extension(*exts)

    try:
        app.run()
    except arroyo.exc.ArgumentError as e:
        print(str(e), file=sys.stderr)
        sys.exit(2)
