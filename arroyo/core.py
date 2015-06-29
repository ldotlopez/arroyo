import argparse
import configparser
import importlib
import logging
from itertools import chain
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
    exts,
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
    'user-agent':
        'Mozilla/5.0 (X11; Linux x86) Home software (KHTML, like Gecko)',
    'fetcher': 'urllib',
    'fetcher.urllib.cache': True,
    'fetcher.urllib.cache-delta': 60 * 20
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
    'fetcher.urllib.cache': bool,
    'fetcher.urllib.cache-delta': int
}

#
# Default extensions
#
_extensions = {
    'commands': ('cron', 'db', 'downloads', 'import', 'mediainfo', 'search'),
    'downloaders': ('mock', 'transmission'),
    'origins': ('eztv', 'kickass', 'spanishtracker', 'thepiratebay'),
    'filters': ('sourcefields',),
    'queries': ('episode', 'movie', 'source')
}

_extensions = chain.from_iterable([
    [ns+'.'+ext for ext in _extensions[ns]]
    for ns in _extensions])

_extensions = [x for x in _extensions]
_defaults.update({'extensions.{}.enabled'.format(x): True
                  for x in _extensions})


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
            '--extension',
            dest='extensions',
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
            action='store_true',
            dest='auto-import')

        parser.add_argument(
            '--auto-cron',
            action='store_true',
            dest='auto-cron')

        return parser


def build_basic_settings(arguments=sys.argv[1:]):
    global _defaults, _extensions

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

    # a) Extensions must be merged
    for ext in args.extensions:
        store.set('extensions.{}.enabled'.format(ext), True)
    try:
        delattr(args, 'extensions')
    except AttributeError:
        pass

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
    for attr in ['downloader', 'db-uri']:
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

                if key.startswith('extensions.') and key.endswith('.enabled'):
                    return store.cast_value(value, bool)

                return _type_validator(key, value)

            return _validator

        if 'validator' not in kwargs:
            kwargs['validator'] = _get_validator()

        super().__init__(*args, **kwargs)


class Arroyo:
    def __init__(self, settings=None):
        self.settings = settings or build_basic_settings([])

        # Support structures for plugins
        self._extensions = set()
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

        # FIX: Logger feature is missing
        self.fetcher = fetchers.Fetcher(fetcher, **fetcher_opts)
        # self.fetcher = fetchers.UrllibFetcher(
        #     cache=self.settings.get('enable-cache'),
        #     cache_delta=self.settings.get('cache-delta'),
        #     headers={'User-Agent': self.settings.get('user-agent')},
        #     logger=self.logger.getChild('fetcher'))

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

        # Load extensions
        for ext in [x for x in _extensions
                    if self.settings.get('extensions.' + x + '.enabled')]:
            self.load_extension(ext)

        # Run cron tasks
        if self.settings.get('auto-cron'):
            self.cron.run_all()

    def get_implementations(self, extension_point):
        return {k: v for (k, v) in
                self._registry.get(extension_point, {}).items()}

    def get_extension(self, extension_point, name, *args, **kwargs):
        impls = self._registry.get(extension_point, {})
        if name not in impls:
            raise arroyo.exc.NoImplementationError(extension_point, name)

        return impls[name](self, *args, **kwargs)

    def load_extension(self, *names):
        for name in names:
            if name in self._extensions:
                msg = "Extension '{name}' was already loaded"
                self.logger.warning(msg.format(name=name))
                continue

            # Load module
            module_name = 'arroyo.exts.' + name

            try:
                m = importlib.import_module(module_name)
                mod_exts = getattr(m, '__arroyo_extensions__', [])
                if not mod_exts:
                    raise ImportError("Module doesn't define any extension")

                for (ext_point, ext_name, ext_cls) in mod_exts:
                    self.register(ext_point, ext_name, ext_cls)
                    if issubclass(ext_cls, exts.Service) and \
                       ext_cls not in self._services:
                        self._services[ext_cls] = ext_cls(self)

                self._extensions.add(name)

            except ImportError as e:
                msg = "Extension '{name}' missing or invalid: {msg}"
                self.logger.warning(msg.format(name=name, msg=str(e)))
                continue

    def register(self, extension_point, extension_name, extension_class):
        if extension_point not in self._registry:
            self._registry[extension_point] = {}

        if extension_name in self._registry[extension_point]:
            msg = "Extension '{name}' already registered, skipping"
            msg = msg.format(name=extension_name)
            raise ImportError(msg)

        self._registry[extension_point][extension_name] = extension_class

    def run_from_args(self, command_line_arguments=sys.argv[1:]):
        # Build full argument parser
        argparser = build_argument_parser()
        subparser = argparser.add_subparsers(
            title='subcommands',
            dest='subcommand',
            description='valid subcommands',
            help='additional help')

        for (name, cmd) in self.get_implementations('command').items():
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
        extension = self.get_extension('command', args.subcommand)
        try:
            extension.run(args)
        except (arroyo.exc.BackendError,
                arroyo.exc.NoImplementationError) as e:
            self.logger.critical(e)
