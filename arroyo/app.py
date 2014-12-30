from arroyo.core import Arroyo


def argument(*args, **kwargs):
    """argparse argument wrapper to ease the command argument definitions"""
    def wrapped_arguments():
        return args, kwargs

    return wrapped_arguments


app = Arroyo()

extensions = {
    'importers': ('eztv', 'spanishtracker', 'thepiratebay'),
    'selectors': ('source', 'episode'),
    'commands': ('analyze', 'db', 'downloads', 'mediainfo', 'search'),
    'downloaders': ('mock', 'transmission')
}

for (k, v) in extensions.items():
    exts = ["%s.%s" % (k, e) for e in v]
    app.load_extension(*exts)
