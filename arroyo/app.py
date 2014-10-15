import argparse
import configparser

from ldotcommons import utils


class ArroyoSingleton(metaclass=utils.SingletonMetaclass):
    def register_command(self, cmd_cls):
        pass


def _create_app():
    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument(
        '-c', '--config',
        dest='config_file',
        default=utils.prog_basic_configfile())
    arg_parser.add_argument(
        '-p', '--plugin',
        dest='plugins',
        nargs='*',
        default=[])

    config_parser = configparser.ConfigParser()

    print(repr(vars(arg_parser.parse_args())))

    return ArroyoSingleton()


app = _create_app()
