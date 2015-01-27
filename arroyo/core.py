import argparse
import configparser
import importlib
from itertools import chain

from ldotcommons import logging, utils

from arroyo import (
    analyzer,
    db,
    downloader,
    exts,
    mediainfo,
    selector,
    signaler)
import arroyo.exc


def build_argument_parser():
        parser = argparse.ArgumentParser(add_help=False)
        parser.add_argument(
            '-h', '--help',
            action='store_true',
            dest='help')

        parser.add_argument(
            '--config-file',
            dest='config_files',
            action='append',
            default=[utils.user_path('config', 'arroyo.ini')])

        parser.add_argument(
            '--extension',
            dest='extensions',
            action='append',
            default=[])

        parser.add_argument(
            '--db-uri',
            dest='db_uri')

        parser.add_argument(
            '--downloader',
            dest='downloader')

        return parser


def build_config_parser(arguments):
    cp = configparser.ConfigParser()
    cp.add_section('main')

    if 'config_files' in arguments:
        cp.read(arguments.config_files)

    for attr in ('db_uri', 'downloader'):
        if attr in arguments:
            cp['main'][attr.replace('_', '-')] = getattr(arguments, attr) or ''

    if 'extensions' in arguments:
        cp['main']['extensions'] = ','.join(arguments.extensions)

    for ext in arguments.extensions:
        sectname = 'extension.' + ext
        if sectname not in cp:
            cp.add_section(sectname)

        cp[sectname]['enabled'] = 'yes'

    return cp


class Arroyo:
    def __init__(self,
                 db_uri=None, downloader_name=None, extensions=[],
                 config=None):
        if config is None:
            config = configparser.ConfigParser()

        if not config.has_section('main'):
            config.add_section('main')

        # Support structures for plugins
        self._extensions = set()
        self._registry = {}
        self._logger = logging.get_logger('app')

        self.config = config

        # Built-in providers
        self.signals = signaler.Signaler()

        self.db = db.Db(
            db_uri or
            self.config.get('main', 'db-uri', fallback=None) or
            'sqlite:///' + utils.user_path('data', 'arroyo.db', create=True))

        self.downloader = downloader.Downloader(
            self,
            (downloader_name or
             self.config.get('main', 'downloader', fallback=None) or
             'mock'))

        self.analyzer = analyzer.Analyzer(self)
        self.selector = selector.Selector(self)

        # Mediainfo instance is not never used directly, it can be considered
        # as a "service", but it's keep anyway
        self.mediainfo = mediainfo.Mediainfo(self)

        # Load extensions
        # FIXME: Weird, I know, I will work on this some day
        exts = chain(
            extensions,
            (x.strip() for x in
             self.config.get('main', 'extensions', fallback='').split(',')
             if x),
            (ext for ext in
             self.config_subdict('extension')
             if self.config.getboolean('extension.'+ext, 'enabled',
                                       fallback=False))
        )

        for ext in exts:
            self.load_extension(ext)

    def config_subdict(self, ns):
        cfg_dict = utils.configparser_to_dict(self.config)
        multi_depth_cfg = utils.MultiDepthDict(cfg_dict)
        return multi_depth_cfg.subdict(ns)

    def get_implementations(self, extension_point):
        return {k: v for (k, v) in
                self._registry.get(extension_point, {}).items()}

    def get_extension(self, extension_point, name, **params):
        try:
            impl_cls = self._registry.get(extension_point, {})[name]
            return impl_cls(self, **params)
        except KeyError:
            pass

        raise arroyo.exc.NoImplementationError(extension_point, name)

    def load_extension(self, *names):
        for name in names:
            if name in self._extensions:
                msg = "Extension '{name}' was already loaded"
                self._logger.warning(msg.format(name=name))
                continue

            # Load module
            module_name = 'arroyo.exts.' + name

            try:
                m = importlib.import_module(module_name)
                mod_exts = getattr(m, '__arroyo_extensions__', [])
                if not exts:
                    raise ImportError("Module doesn't define any extension")

                for (ext_point, ext_name, ext_cls) in mod_exts:
                    self.register(ext_point, ext_name, ext_cls)
                    print(ext_cls)
                    if issubclass(ext_cls, exts.Service):
                        ext_cls(self)

                self._extensions.add(name)

            except ImportError as e:
                msg = "Extension '{name}' missing or invalid: {msg}"
                self._logger.warning(msg.format(name=name, msg=str(e)))
                self._logger.warning(e)
                continue

    def register(self, extension_point, extension_name, extension_class):
        if extension_point not in self._registry:
            self._registry[extension_point] = {}

        if extension_name in self._registry[extension_point]:
            msg = "Extension '{name}' already registered, skipping"
            msg = msg.format(name=extension_name)
            raise ImportError(msg)

        self._registry[extension_point][extension_name] = extension_class

    def run_from_args(self, arguments=None):
        argparser = build_argument_parser()

        subparser = argparser.add_subparsers(
            title='subcommands',
            dest='subcommand',
            description='valid subcommands',
            help='additional help')

        for (name, cmd) in self.get_implementations('command').items():
            command_parser = subparser.add_parser(name)
            for argument in cmd.arguments:
                args, kwargs = argument()
                command_parser.add_argument(*args, **kwargs)

        args = argparser.parse_args(arguments)
        if not args.subcommand:
            argparser.print_help()
            return

        return self.run_command(args.subcommand, args)

    def run_command(self, command, args):
        try:
            # FIXME: Remove arguments from self
            self.arguments = args
            self.get_extension('command', command).run()
            delattr(self, 'arguments')
        except arroyo.exc.ArgumentError as e:
            self._logger.error(e)
