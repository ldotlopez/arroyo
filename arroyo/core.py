# -*- coding: utf-8 -*-

import argparse
import configparser
import importlib
import logging
import sys
import warnings

from ldotcommons import (
    fetchers,
    keyvaluestore,
    store,
    utils
)

import arroyo.exc
from arroyo import (
    importer,
    cron,
    db,
    downloads,
    extension,
    mediainfo,
    models,
    selector,
    signaler)

#
# Default values for config
#
_defaults = {
    'db-uri': 'sqlite:///' +
              utils.user_path('data', 'arroyo.db', create=True),
    'downloader': 'mock',
    'auto-cron': False,
    'auto-import': False,
    'legacy': False,
    'log-level': 'WARNING',
    'log-format': '[%(levelname)s] [%(name)s] %(message)s',
    'fetcher': 'urllib',
    'fetcher.options.enable-cache': True,
    'fetcher.options.cache-delta': 60 * 20,
    'fetcher.options.user-agent':
        'Mozilla/5.0 (X11; Linux x86) Home software (KHTML, like Gecko)',
    'async-max-concurrency': 5,
    'async-timeout': 10
}

_defaults_types = {
    'db-uri': str,
    'downloader': str,
    'auto-cron': bool,
    'auto-import': bool,
    'log-level': str,
    'log-format': str,
    'user-agent': str,
    'fetcher': str,
    'fetcher.options.enable-cache': bool,
    'fetcher.options.cache-delta': int,
    'fetcher.options.user-agent': str,
    'async-max-concurrency': int,
    'async-timeout': float
}

#
# Default plugins
#
_plugins = [
    # Commands
    'cron', 'db', 'downloads', 'import', 'mediainfo', 'search',

    # Downloaders
    'mockdownloader', 'transmission',

    # Filters
    'sourcefilters', 'episodefilters', 'mediainfofilters', 'moviefilters',

    # Origins
    'eztv', 'kickass', 'spanishtracker', 'thepiratebay',

    # Sorters
    'basicsorter',

    # Queries
    'sourcequery', 'episodequery', 'moviequery'
    ]

_defaults.update({'plugin.{}.enabled'.format(x): True
                  for x in _plugins})


def build_argument_parser():
        parser = argparse.ArgumentParser(add_help=False)
        parser.add_argument(
            '-h', '--help',
            action='store_true',
            dest='help')

        parser.add_argument(
            '-v', '--verbose',
            dest='verbose',
            default=0,
            action='count')

        parser.add_argument(
            '-q', '--quiet',
            dest='quiet',
            default=0,
            action='count')

        parser.add_argument(
            '-c', '--config-file',
            dest='config-files',
            action='append',
            default=[])

        parser.add_argument(
            '--plugin',
            dest='plugins',
            action='append',
            default=[])

        parser.add_argument(
            '--db-uri',
            dest='db-uri')

        parser.add_argument(
            '--downloader',
            dest='downloader')

        parser.add_argument(
            '--auto-import',
            default=None,
            action='store_true',
            dest='auto-import')

        parser.add_argument(
            '--auto-cron',
            default=None,
            action='store_true',
            dest='auto-cron')

        return parser


def build_basic_settings(arguments=[]):
    global _defaults, _plugins

    # The first task is parse arguments
    argparser = build_argument_parser()
    args, remaining = argparser.parse_known_args()

    # Now we have to load default and extra config files.
    # Once they are loaded they are useless in 'args'.
    cp = configparser.RawConfigParser()
    if cp.read(getattr(args, 'config-files',
                       utils.user_path('config', 'arroyo.ini'))):
        delattr(args, 'config-files')

    # With every parameter loaded we build the settings store
    store = ArroyoStore()
    store.load_configparser(cp, root_sections=('main',))

    # Arguments must be loaded with care.

    # a) Plugins must be merged
    for ext in args.plugins:
        store.set('plugin.{}.enabled'.format(ext), True)
    delattr(args, 'plugins')

    # b) log level modifers must me handled and removed from args
    log_levels = 'CRITICAL ERROR WARNING INFO DEBUG'.split(' ')
    log_level = store.get('log-level', 'WARNING')
    try:
        log_level = log_levels.index(log_level)
    except ValueError:
        warnings.warn("Invalid log level: {}, using 'WARNING'".format(
            log_level))
        log_level = 2

    log_level = max(0, min(4, log_level - args.quiet + args.verbose))
    delattr(args, 'quiet')
    delattr(args, 'verbose')
    store.set('log-level', log_levels[log_level])

    # Clean up args before merging with store
    delattr(args, 'help')
    for attr in ['downloader', 'db-uri', 'auto-cron', 'auto-import']:
        if getattr(args, attr, None) is None:
            delattr(args, attr)

    store.load_arguments(args)

    # Finally insert defaults
    for key in _defaults:
        if key not in store:
            store.set(key, _defaults[key])

    return store


class EncodedStreamHandler(logging.StreamHandler):
    def __init__(self, encoding='utf-8', *args, **kwargs):
        super(EncodedStreamHandler, self).__init__(*args, **kwargs)
        self.encoding = encoding
        self.terminator = self.terminator.encode(self.encoding)

    def emit(self, record):
        try:
            msg = self.format(record).encode(self.encoding)
            stream = self.stream
            stream.buffer.write(msg)
            stream.buffer.write(self.terminator)
            self.flush()
        except Exception:
            self.handleError(record)


class ArroyoStore(store.Store):
    def __init__(self, *args, **kwargs):
        def _get_validator():
            _log_lvls = 'CRITICAL ERROR WARNING INFO DEBUG'.split(' ')
            _type_validator = store.type_validator(_defaults_types,
                                                   relaxed=True)

            def _validator(key, value):
                if key == 'log-level' and value not in _log_lvls:
                    raise ValueError(value)

                if key.startswith('plugin.') and key.endswith('.enabled'):
                    return store.cast_value(value, bool)

                return _type_validator(key, value)

            return _validator

        if 'validator' not in kwargs:
            kwargs['validator'] = _get_validator()

        # Build and configure logger
        handler = EncodedStreamHandler()
        formater = logging.Formatter(self.get('log-format', r'%(message)s'))
        handler.setFormatter(formater)

        self._logger = logging.getLogger('arroyo.settings')
        self._logger.addHandler(handler)

        super().__init__(*args, **kwargs)

    def __setitem__(self, key, value):
        try:
            super().__setitem__(key, value)
        except ValueError as e:
            self._logger.error(str(e))


class Arroyo:
    def __init__(self, settings=None):
        self.settings = settings or build_basic_settings([])

        # Support structures for plugins
        self._services = {}
        self._registry = {}

        # Build and configure logger
        handler = EncodedStreamHandler()
        handler.setFormatter(logging.Formatter(
            self.settings.get('log-format')))
        self.logger = logging.getLogger('arroyo')
        self.logger.addHandler(handler)

        lvlname = self.settings.get('log-level')
        self.logger.setLevel(getattr(logging, lvlname))

        # Build and configure fetcher
        fetcher = self.settings.get('fetcher')
        try:
            fetcher_opts = self.settings.get_tree('fetcher.' + fetcher)
            fetcher_opts = {k.replace('-', '_'): v
                            for (k, v) in fetcher_opts.items()}

        except KeyError:
            fetcher_opts = {}

        self.fetcher = fetchers.Fetcher(
            fetcher,
            logger=self.logger.getChild('fetcher.' + fetcher),
            **fetcher_opts)

        # Built-in providers
        self.db = db.Db(self.settings.get('db-uri'))
        self.variables = keyvaluestore.KeyValueManager(models.Variable,
                                                       session=self.db.session)
        self.signals = signaler.Signaler()
        self.cron = cron.CronManager(self)

        self.importer = importer.Importer(self)
        self.selector = selector.Selector(self)
        self.downloads = downloads.Downloads(self)

        # Mediainfo instance is not never used directly, it can be considered
        # as a "service", but it's keep anyway
        self.mediainfo = mediainfo.Mediainfo(self)

        # Load plugins
        # FIXME: Search for enabled plugins thru the keys of settings is a
        # temporal solution.
        plugins = filter(lambda x: x.startswith('plugin.'), self.settings)
        plugins = map(lambda x: x.split('.'), plugins)
        plugins = filter(lambda x: len(x) >= 2, plugins)
        plugins = map(lambda x: x[1], plugins)

        for p in set(plugins):
            if self.settings.get('plugin.' + p + '.enabled', True):
                self.load_plugin(p)

        # Run cron tasks
        if self.settings.get('auto-cron'):
            self.cron.run_all()

    def load_plugin(self, name):
        # Load module
        module_name = 'arroyo.plugins.' + name

        try:
            m = importlib.import_module(module_name)
            mod_exts = getattr(m, '__arroyo_extensions__', [])
            if not mod_exts:
                raise ImportError("Plugin doesn't define any extension")
            for ext_def in mod_exts:
                self.register_extension(*ext_def)

        except ImportError as e:
            msg = "Extension '{name}' missing or invalid: {msg}"
            self.logger.warning(msg.format(name=name, msg=str(e)))

    def register_extension(self, name, cls):
        # Check extension type
        typ = None
        for x in extension.Extension.__subclasses__():
            if issubclass(cls, x):
                typ = x
                break

        if not typ:
            msg = "Extension '{name}' has invalid type"
            msg = msg.format(name=name)
            raise ImportError(msg)

        if typ not in self._registry:
            self._registry[typ] = {}

        if name in self._registry[typ]:
            msg = "Extension '{name}' already registered, skipping"
            msg = msg.format(name=name)
            raise ImportError(msg)

        self._registry[typ][name] = cls

        if issubclass(cls, extension.Service):
            if name in self._services:
                msg = ("Service '{name}' already registered by "
                       "'{cls}'")
                msg = msg.format(
                    name=name,
                    cls=type(self._services[name]))
                self.logger.critical(msg)
            else:
                try:
                    self._services[cls] = cls(self)
                except arroyo.exc.ArgumentError as e:
                    self.logger.critical(str(e))

    def get_implementations(self, extension_point):
        if isinstance(extension_point, str):
            raise Exception(extension_point)

        return {k: v for (k, v) in
                self._registry.get(extension_point, {}).items()}

    def get_implementation(self, extension_point, name):
        if isinstance(extension_point, str):
            raise Exception(extension_point)

        impls = self._registry.get(extension_point, {})
        if name not in impls:
            raise arroyo.exc.NoImplementationError(extension_point, name)

        return impls[name]

    def get_extension(self, extension_point, name, *args, **kwargs):
        impl = self.get_implementation(extension_point, name)
        return impl(self, *args, **kwargs)

    def run_from_args(self, command_line_arguments=sys.argv[1:]):
        # Build full argument parser
        argparser = build_argument_parser()
        subparser = argparser.add_subparsers(
            title='subcommands',
            dest='subcommand',
            description='valid subcommands',
            help='additional help')

        for (name, cmd) in self.get_implementations(extension.Command).items():
            command_parser = subparser.add_parser(name, help=cmd.help)
            for argument in cmd.arguments:
                args, kwargs = argument()
                command_parser.add_argument(*args, **kwargs)

        # Parse arguments
        args = argparser.parse_args(command_line_arguments)
        if not args.subcommand:
            argparser.print_help()
            return

        # Get extension instances and extract its argument names
        ext = self.get_extension(extension.Command, args.subcommand)
        try:
            ext.run(args)
        except (arroyo.exc.BackendError,
                arroyo.exc.NoImplementationError) as e:
            self.logger.critical(e)
