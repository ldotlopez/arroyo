# -*- coding: utf-8 -*-


import argparse
import asyncio
import importlib
import sys
import warnings


import bs4
import yaml
from appkit import (
    cache,
    keyvaluestore,
    network,
    logging,
    store,
    utils
)
from appkit.application import (
    commands,
    cron,
    services
)

import arroyo.exc
from arroyo import (
    db,
    downloads,
    importer,
    kit,
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
              utils.user_path(utils.UserPathType.DATA, 'arroyo.db',
                              create=True),
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
    'commands.config',
    'commands.cron',
    'commands.db',
    'commands.download',
    'commands.import',
    'commands.mediainfo',
    'commands.search',

    # Downloaders
    'downloaders.mock',
    'downloaders.transmission',

    # Filters
    'filters.episodefields',
    'filters.mediainfo',
    'filters.moviefields',
    'filters.sourcefields',

    # Providers
    'providers.elitetorrent',
    'providers.epublibre',
    'providers.eztv',
    'providers.generic',
    'providers.kickass',
    'providers.thepiratebay',
    'providers.torrentapi',
    'providers.yts',

    # Sorters
    'sorters.basic',

    # Queries
    'queries.episode',
    'queries.movie',
    'queries.source',
]

_defaults.update({'plugins.{}.enabled'.format(x): True
                  for x in _plugins})


def build_basic_settings(arguments=None):
    if arguments is None:
        arguments = []

    global _defaults, _plugins

    # The first task is parse arguments
    argparser = kit.CommandManager.build_base_argument_parser()
    args, remaining = argparser.parse_known_args()

    # Now we have to load default and extra config files.
    # Once they are loaded they are useless in 'args'.
    config_files = getattr(args, 'config-files',
                           utils.user_path(utils.UserPathType.CONFIG,
                                           'arroyo.yml'))

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


class Arroyo(services.ApplicationMixin, kit.Application):
    def __init__(self, settings=None):
        super().__init__('arroyo')

        self.settings = settings or build_basic_settings([])

        # Build and configure logger
        self.logger = logging.getLogger('arroyo')

        lvlname = self.settings.get('log-level')
        lvl = getattr(logging.Level, lvlname)
        self.logger.setLevel(lvl.value)  # Modify level on on the handler

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
        self.commands = kit.CommandManager(self)
        self.cron = kit.CronManager(self)

        self.importer = importer.Importer(self)
        self.selector = selector.Selector(self)
        self.downloads = downloads.Downloads(self)

        # Mediainfo instance is not never used directly, it can be considered
        # as a "service", but it's keep anyway
        self.mediainfo = mediainfo.Mediainfo(self)

        # Load plugins
        # FIXME: Search for enabled plugins thru the keys of settings is a
        # temporal solution.
        plugins = filter(lambda x: x.startswith('plugins.') and x.endswith('.enabled'),
                         self.settings.all_keys())
        plugins = map(lambda x: x[len('plugins.'):-len('.enabled')],
                      plugins)

        for p in set(plugins):
            if self.settings.get('plugins.' + p + '.enabled', default=False):
                self.load_plugin(p)

        # Run cron tasks
        if self.settings.get('auto-cron'):
            self.cron.execute_all()

    # @classmethod
    # def build_argument_parser(cls):
    #     return build_argument_parser()

    def execute(self, *args):
        try:
            return self.commands.execute(*args)

        except (arroyo.exc.BackendError,
                arroyo.exc.NoImplementationError,
                arroyo.exc.FatalError) as e:
            self.logger.critical(e)


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
        self._logger = logging.getLogger('arroyo.settings')

        # if 'validator' not in kwargs:
        #     kwargs['validator'] = _get_validator()

        # Build and configure logger
        # handler = EncodedStreamHandler()
        # formater = logging.Formatter(
        #     self.get('log-format', default=r'%(message)s'))
        # handler.setFormatter(formater)

        # self._logger = logging.getLogger('arroyo.settings')
        # self._logger.addHandler(handler)

    def set(self, key, value):
        parts = key.split('.')

        if len(parts) >= 3 and parts[0] == 'origin' and parts[2] == 'backend':
            msg = "[Configuration Error] Origins use 'provider' instead of 'backend'"
            raise ValueError(msg)

        if key.startswith('plugin.'):
            msg = "[Configuration Error] 'plugin.' namespace is deprecated, use 'plugins.'"
            raise ValueError(msg)

        return super().set(key, value)

    def get(self, key, default=store.UNDEFINED):
        if key.startswith('plugin.'):
            msg = "[Configuration Error] 'plugin.' namespace is deprecated, use 'plugins.'"
            raise ValueError(msg)

        return super().get(key, default=default)

    def dump(self, stream):
        buff = yaml.dump(self.get(None), )
        stream.write(buff)

    def load(self, stream):
        data = store.flatten_dict(yaml.load(stream.read()))

        for (k, v) in data.items():
            self.set(k, v)


class ArroyoAsyncFetcher(network.AsyncFetcher):
    def __init__(self, *args, enable_cache=False, cache_delta=-1, timeout=-1,
                 **kwargs):

        logger = kwargs.get('logger', None)

        self._timeout = timeout

        if enable_cache:
            fetcher_cache = cache.DiskCache(
                basedir=utils.user_path(utils.UserPathType.CACHE, 'network',
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
