class Extension:
    def __init__(self, app):
        self.app = app
        super(Extension, self).__init__()


class Service(Extension):
    pass


class Importer(Extension):
    def search(self, query):
        yield None


class Command(Extension):
    pass


class Downloader(Extension):
    pass


class Selector(Extension):
    pass


def argument(*args, **kwargs):
    """argparse argument wrapper to ease the command argument definitions"""
    def wrapped_arguments():
        return args, kwargs

    return wrapped_arguments
