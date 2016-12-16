# -*- coding: utf-8 -*-


import argparse
import asyncio
import importlib
import sys
import warnings


import bs4
from appkit import (
    app,
    cache,
    keyvaluestore,
    network,
    logging,
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
    signaler
)


#
# Default values for config
#
_defaults = {
    'async-max-concurrency': 5,
    'async-timeout': 10,
    'auto-cron': False,
    'auto-import': False,
    'db-uri': 'sqlite:///' +
              utils.user_path('data', 'arroyo.db', create=True),
    'downloader': 'mock',
    'fetcher.cache-delta': 60 * 20,
    'fetcher.enable-cache': True,
    'fetcher.headers': {
        'User-Agent':
            'Mozilla/5.0 (X11; Linux x86) Home software (KHTML, like Gecko)',
        },
    'importer.parser': 'auto',
    'log-format': '[%(levelname)s] [%(name)s] %(message)s',
    'log-level': 'WARNING',
    'selector.query-defaults.age-min': '2H',
    'selector.sorter': 'basic'
}

_defaults_types = {
    'async-max-concurrency': int,
    'async-timeout': float,
    'auto-cron': bool,
    'auto-import': bool,
    'db-uri': str,
    'downloader': str,
    'fetcher': dict,
    'fetcher.cache-delta': int,
    'fetcher.enable-cache': bool,
    'fetcher.headers': dict,
    'importer': dict,
    'importer.parser': str,
    'log-format': str,
    'log-level': str,
    'selector': dict,
    'selector.sorter': str,
    'selector.query-defaults': str
}

#
# Default plugins
#
_plugins = [
    # Commands
    'configcmd', 'croncmd', 'dbcmd', 'downloadcmd', 'importcmd',
    'mediainfocmd', 'searchcmd',

    # Downloaders
    'mockdownloader', 'transmission',

    # Filters
    'sourcefilters', 'episodefilters', 'mediainfofilters', 'moviefilters',

    # Origins
    'elitetorrent', 'eztv', 'genericorigin', 'kickass', 'spanishtracker',
    'thepiratebay',

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


def build_basic_settings(arguments=None):
    if arguments is None:
        arguments = []

    global _defaults, _plugins

    # The first task is parse arguments
    argparser = build_argument_parser()
    args, remaining = argparser.parse_known_args()

    # Now we have to load default and extra config files.
    # Once they are loaded they are useless in 'args'.
    config_files = getattr(args, 'config-files',
                           utils.user_path('config', 'arroyo.yml'))

    # With every parameter loaded we build the settings store
    store = ArroyoStore()
    for cfg in config_files:
        with open(cfg) as fh:
            store.load(fh)
    try:
        delattr(args, 'config-files')
    except AttributeError:
        pass

    # Arguments must be loaded with care.

    # a) Plugins must be merged
    for ext in args.plugins:
        store.set('plugin.{}.enabled'.format(ext), True)
    delattr(args, 'plugins')

    # b) log level modifers must me handled and removed from args
    log_levels = 'CRITICAL ERROR WARNING INFO DEBUG'.split(' ')
    log_level = store.get('log-level', default='WARNING')
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


# class EncodedStreamHandler(logging.StreamHandler):
#     def __init__(self, encoding='utf-8', *args, **kwargs):
#         super(EncodedStreamHandler, self).__init__(*args, **kwargs)
#         self.encoding = encoding
#         self.terminator = self.terminator.encode(self.encoding)

#     def emit(self, record):
#         try:
#             msg = self.format(record).encode(self.encoding)
#             stream = self.stream
#             stream.buffer.write(msg)
#             stream.buffer.write(self.terminator)
#             self.flush()
#         except Exception:
#             self.handleError(record)

class ArroyoAsyncFetcher(network.AsyncFetcher):
    def __init__(self, *args, enable_cache=False, cache_delta=-1, timeout=-1,
                 **kwargs):

        logger = kwargs.get('logger', None)

        self._timeout = timeout

        if enable_cache:
            fetcher_cache = cache.DiskCache(
                basedir=utils.user_path('cache', 'network',
                                        create=True, is_folder=True),
                delta=cache_delta,
                logger=logger)

            if logger:
                msg = "{clsname} using cachepath '{path}'"
                msg = msg.format(clsname=self.__class__.__name__,
                                 path=fetcher_cache.basedir)
                logger.debug(msg)
        else:
            fetcher_cache = None

        kwargs['cache'] = fetcher_cache
        super().__init__(*args, **kwargs)

    @asyncio.coroutine
    def fetch_full(self, *args, **kwargs):
        kwargs['timeout'] = self._timeout
        resp, content = yield from super().fetch_full(*args, **kwargs)
        return resp, content


class ArroyoStore(store.Store):
    def __init__(self, items={}):
        # def _get_validator():
        #     _log_lvls = 'CRITICAL ERROR WARNING INFO DEBUG'.split(' ')
        #     _type_validator = store.type_validator(_defaults_types,
        #                                            relaxed=True)

        #     def _validator(key, value):
        #         if key == 'log-level' and value not in _log_lvls:
        #             raise ValueError(value)

        #         if key.startswith('plugin.') and key.endswith('.enabled'):
        #             return store.cast_value(value, bool)

        #         return _type_validator(key, value)

        #     return _validator

        super().__init__(
            items=items,
            validators=[store.TypeValidator(_defaults_types)]
        )
        self._logger = logging.get_logger('arroyo.settings')

        # if 'validator' not in kwargs:
        #     kwargs['validator'] = _get_validator()

        # Build and configure logger
        # handler = EncodedStreamHandler()
        # formater = logging.Formatter(
        #     self.get('log-format', default=r'%(message)s'))
        # handler.setFormatter(formater)

        # self._logger = logging.getLogger('arroyo.settings')
        # self._logger.addHandler(handler)

    def get(self, *args, **kwargs):
        try:
            return super().get(*args, **kwargs)
        except (
            store.IllegalKeyError,
            store.KeyNotFoundError,
            store.ValidationError
        ) as e:
            self._logger.error(str(e))
            raise

    def set(self, *args, **kwargs):
        try:
            return super().set(*args, **kwargs)
        except (
            store.IllegalKeyError,
            store.ValidationError
        ) as e:
            self._logger.error(str(e))
            raise

    def delete(self, *args, **kwargs):
        try:
            super().delete(*args, **kwargs)
        except (
            store.IllegalKeyError,
            store.KeyNotFoundError,
            store.ValidationError
        ) as e:
            self._logger.error(str(e))
            raise

    def children(self, *args, **kwargs):
        try:
            return super().children(*args, **kwargs)
        except (
            store.IllegalKeyError,
            store.KeyNotFoundError,
            store.ValidationError
        ) as e:
            self._logger.error(str(e))
            raise


class CommandlineArroyoAppMixin(app.CommandlineAppMixin):
    COMMAND_EXTENSION_POINT = extension.Command


class Arroyo(app.ServiceAppMixin, CommandlineArroyoAppMixin, app.BaseApp):
    def __init__(self, settings=None):
        super().__init__('arroyo')

        self.settings = settings or build_basic_settings([])

        # Build and configure logger
        # handler = EncodedStreamHandler()
        # handler.setFormatter(logging.Formatter(
        #     self.settings.get('log-format')))
        # self.logger = logging.getLogger('arroyo')
        # self.logger.addHandler(handler)
        self.logger = logging.get_logger('arroyo')

        lvlname = self.settings.get('log-level')
        self.logger.setLevel(getattr(logging, lvlname))

        # Auto setting: importer parser
        if self.settings.get('importer.parser') == 'auto':
            for parser in ['lxml', 'html.parser', 'html5lib']:
                try:
                    bs4.BeautifulSoup('', parser)
                    self.settings.set('importer.parser', parser)
                    msg = "Using '{parser}' as bs4 parser"
                    msg = msg.format(parser=parser)
                    self.logger.debug(msg)
                    break
                except bs4.FeatureNotFound:
                    pass
            else:
                msg = "Unable to find any parser"
                raise ValueError(msg)

        # Configure fetcher object
        fetcher_opts = self.settings.get('fetcher')
        fetcher_opts = {
            k.replace('-', '_'): v
            for (k, v) in fetcher_opts.items()
        }

        logger = self.logger.getChild('fetcher')
        enable_cache = fetcher_opts.pop('enable_cache')
        cache_delta = fetcher_opts.pop('cache_delta')

        self.fetcher = ArroyoAsyncFetcher(
            logger=logger,
            enable_cache=enable_cache,
            cache_delta=cache_delta,
            max_requests=self.settings.get('async-max-concurrency'),
            timeout=self.settings.get('async-timeout'),
            **fetcher_opts
        )

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
        plugins = filter(lambda x: x.startswith('plugin.'),
                         self.settings.all_keys())
        plugins = map(lambda x: x.split('.'), plugins)
        plugins = filter(lambda x: len(x) >= 2, plugins)
        plugins = map(lambda x: x[1], plugins)

        for p in set(plugins):
            if self.settings.get('plugin.' + p + '.enabled', default=True):
                self.load_plugin(p)

        # Run cron tasks
        if self.settings.get('auto-cron'):
            self.cron.run_all()

    def get_extension(self, extension_point, name, *args, **kwargs):
        return super().get_extension(extension_point, name, self,
                                     *args, **kwargs)

    # def run_from_args(self, command_line_arguments=sys.argv[1:]):
    #     # Build full argument parser
    #     argparser = build_argument_parser()
    #     subparser = argparser.add_subparsers(
    #         title='subcommands',
    #         dest='subcommand',
    #         description='valid subcommands',
    #         help='additional help')

    #     impls = self.get_implementations(extension.Command)
    #     subargparsers = {}
    #     for cmdcls in impls:
    #         name = cmdcls.__extension_name__
    #         subargparsers[name] = subparser.add_parser(
    #             name, help=cmdcls.help)
    #         cmdcls.setup_argparser(subargparsers[name])

    #     # Parse arguments
    #     args = argparser.parse_args(command_line_arguments)
    #     if not args.subcommand:
    #         argparser.print_help()
    #         return

    #     # Get extension instances and extract its argument names
    #     ext = self.get_extension(extension.Command, args.subcommand)
    #     try:
    #         ext.run(args)

    #     except arroyo.exc.PluginArgumentError as e:
    #         subargparsers[args.subcommand].print_help()
    #         print("\nError message: {}".format(e), file=sys.stderr)

    #     except (arroyo.exc.BackendError,
    #             arroyo.exc.NoImplementationError,
    #             arroyo.exc.FatalError) as e:
    #         self.logger.critical(e)
