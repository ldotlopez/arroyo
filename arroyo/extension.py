# -*- coding: utf-8 -*-

class Extension:
    """
    Basic extension point.
    Its reponsability is link extension.Extension and core.Arroyo
    """
    def __init__(self, app):
        super(Extension, self).__init__()
        self.app = app


class Command(Extension):
    help = ''
    arguments = ()

    @classmethod
    def setup_argparser(cls, cmdargparser):
        arguments = getattr(cls, 'arguments')
        for argument in arguments:
            args, kwargs = argument()
            cmdargparser.add_argument(*args, **kwargs)

    def run(self, arguments):
        raise NotImplementedError()


class Service(Extension):
    pass


def argument(*args, **kwargs):
    """
    argparse argument wrapper to ease the command argument definitions
    """
    def wrapped_arguments():
        return args, kwargs

    return wrapped_arguments
