import argparse
import configparser
import importlib

from ldotcommons import logging, utils

from arroyo import (
    analyzer,
    db,
    downloader,
    mediainfo,
    selector,
    signaler)
import arroyo.exc


class Arroyo:
    def __init__(self, *args,
                 db_uri='sqlite:///:memory:', downloader_name='mock'):

        # Support structures for plugins
        self._extensions = set()
        self._registry = {}
        self._logger = logging.get_logger('app')

        # Support structures for arguments and configs
        self.arguments = argparse.Namespace()
        self.config = configparser.ConfigParser()
        self.config.add_section('main')
        self._arg_parser = argparse.ArgumentParser()

        # Built-in providers
        self.signals = signaler.Signaler()
        self.db = db.Db(db_uri)
        self.downloader = downloader.Downloader(self, downloader_name)

        self.analyzer = analyzer.Analyzer(self)
        self.selector = selector.Selector(self)

        # Mediainfo instance is not never used directly, it can be considered
        # as a "service", but it's keep anyway
        self.mediainfo = mediainfo.Mediainfo(self)

    @staticmethod
    def _build_minimal_parser():
        parser = argparse.ArgumentParser(add_help=False)
        parser.add_argument(
            '-h', '--help',
            action='store_true',
            dest='help')

        parser.add_argument(
            '--config-file',
            dest='config_file',
            default=utils.prog_config_file())

        parser.add_argument(
            '--extension',
            dest='extensions',
            action='append',
            default=[])

        return parser

    def config_subdict(self, ns):
        cfg_dict = utils.configparser_to_dict(self.config)
        multi_depth_cfg = utils.MultiDepthDict(cfg_dict)
        return multi_depth_cfg.subdict(ns)

    def parse_arguments(self, arguments=None, apply=True):
        # Load config and plugins in a first phase
        self._arg_parser = self._build_minimal_parser()
        self._arg_parser.add_argument(
            '--db-uri',
            dest='db_uri')

        self._arg_parser.add_argument(
            '--downloader',
            dest='downloader')

        phase1_args, remaing_args = self._arg_parser.parse_known_args()

        if phase1_args.config_file:
            self.parse_config(phase1_args.config_file, apply=False)

        if phase1_args.extensions:
            self.load_extension(*phase1_args.extensions)

        # Build subcommands
        subparser = self._arg_parser.add_subparsers(
            title='subcommands',
            dest='subcommand',
            description='valid subcommands',
            help='additional help')

        # for cmd in self._instances['command'].values():
        for (name, cmd) in self.get_all_implementations('command').items():
            command_parser = subparser.add_parser(name)
            for argument in cmd.arguments:
                args, kwargs = argument()
                command_parser.add_argument(*args, **kwargs)

        # With a full bootstraped app (with plugins loaded and other stuff)
        # do a full parsing
        self.arguments = self._arg_parser.parse_args(arguments)

        if apply:
            self._apply_settings()

    def get_all_implementations(self, extension_point):
        return {k: v for (k, v) in
                self._registry.get(extension_point, {}).items()}

    def get_implementation(self, extension_point, name):
        try:
            return self._registry.get(extension_point, {})[name]
        except KeyError:
            pass

        raise arroyo.exc.NoImplementationError(extension_point, name)

    def parse_config(self, config_file, apply=True):
        if config_file is None:
            return

        read = self.config.read(config_file)
        if not read or read[0] != config_file:
            self._logger.warning("'{config_file}' can't be read".format(
                config_file=config_file))

        extension_sections = [s for s in self.config.sections()
                              if s.startswith('extension.')]
        for extension_section in extension_sections:
            enabled = self.config.getboolean(extension_section, 'enabled',
                                             fallback=False)
            if enabled:
                extension_name = extension_section[len('extension.'):]
                self.load_extension(extension_name)

        if apply:
            self._apply_settings()

    def _apply_settings(self):
        """
        Aplies global settings from arguments and config
        """

        db_uri = \
            self.arguments.db_uri or \
            self.config.get('main', 'db-uri', fallback=None) or \
            'sqlite:///' + utils.prog_datafile('arroyo.db', create=True)
        self.db = db.Db(db_uri)

        downloader_name = self.arguments.downloader or \
            self.config.get('main', 'downloader', fallback=None) or \
            'mock'
        self.downloader.set_backend(downloader_name)

    def load_extension(self, *names):
        for name in names:
            if name in self._extensions:
                msg = "Extension '{name}' was already loaded"
                self._logger.warning(msg.format(name=name))
                continue

            # Load module
            module_name = 'arroyo.extensions.' + name

            try:
                importlib.import_module(module_name)
                self._extensions.add(name)
            except ImportError as e:
                msg = "Extension '{name}' missing or invalid"
                self._logger.warning(msg.format(name=name))
                self._logger.warning(e)
                continue

    def register(self, extension_point, extension_name):
        def decorator(cls):
            if extension_point not in self._registry:
                self._registry[extension_point] = {}

            if extension_name in self._registry[extension_point]:
                msg = "Extension '{name}' already registered, skipping"
                self._logger.warning(msg.format(name=cls.name))
                return cls

            self._registry[extension_point][extension_name] = cls
            return cls

        return decorator

    def run(self, arguments=None):
        self.parse_arguments(arguments)

        if not self.arguments.subcommand:
            self._arg_parser.print_help()
            return

        self.run_command(self.arguments.subcommand)

    def run_command(self, command):
        try:
            self._registry['command'][command]().run()
        except arroyo.exc.ArgumentError as e:
            self._logger.error(e)
