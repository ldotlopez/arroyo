class Plugin:
    def __init__(self):
        raise NotImplementedError()


class Command:
    name = None
    help = None
    arguments = ()

    def run(self):
        raise NotImplementedError()


class Filter:
    def filter_query(self):
        raise NotImplementedError()

    def filter_iterable(self):
        raise NotImplementedError()


class Listener:
    signals = ()


class ArgumentError(Exception):
    def __init__(self, msg, *args, tip=True, **kwargs):
        if not msg.endswith('.'):
            msg += "."
        msg += " Try -h/--help switch for more information"
        super(ArgumentError, self).__init__(msg, *args, **kwargs)


def argument(*args, **kwargs):
    """argparse argument wrapper to ease the command argument definitions"""
    def wrapped_arguments():
        return args, kwargs

    return wrapped_arguments
