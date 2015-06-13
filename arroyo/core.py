import argparse
import configparser
import importlib
import logging
from itertools import chain
import sys
import warnings

from ldotcommons import (
    fetchers,
    store,
    utils
)

from arroyo import (
    importer,
    db,
    downloader,
    exts,
    mediainfo,
    selector,
    signaler)

import arroyo.exc

#
# Default extensions
#
_extensions = {
    'commands': ('import', 'db', 'downloads', 'mediainfo', 'search'),
    'downloaders': ('mock', 'transmission'),
    'origins': ('eztv', 'kickass', 'spanishtracker', 'thepiratebay'),
    'selectors': ('source', 'episode', 'movie'),
}

_extensions = chain.from_iterable([
    [ns+'.'+ext for ext in _extensions[ns]]
    for ns in _extensions])

_extensions = [x for x in _extensions]


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


def build_basic_settings(arguments=sys.argv[1:]):
    def _get_validator():
        _type_validator = store.type_validator(types, relaxed=True)

        def _validator(k, v):
            if k.startswith('extensions.') and k.endswith('.enabled'):
                if v.lower() in ('1', 'yes', 'true', 'y'):
                    return True

                if v.lower() in ('0', 'no', 'false', 'n'):
                    return False

                raise ValueError('Invalid value for {}: {}'.format(k, v))

            return _type_validator(k, v)

        return _validator

    types = {
        'legacy': bool,
        'db-uri': str,
        'downloader': str,
        'auto-import': bool,
        'log-level': str,
        'log-format': str,
        'user-agent': str,
        'enable-cache': bool,
        'cache-delta': int
    }

    s = store.Store({
        'db-uri': 'sqlite:///' +
                  utils.user_path('data', 'arroyo.db', create=True),
        'downloader': 'mock',
        'auto-import': False,
        'legacy': False,
        'log-level': 'WARNING',
        'log-format': '[%(levelname)s] [%(name)s] %(message)s',
        'user-agent':
            'Mozilla/5.0 (X11; Linux x86) Home software (KHTML, like Gecko)',
        'enable-cache': True,
        'cache-delta': 60 * 20
    }, validator=_get_validator())

    argparser = build_argument_parser()
    args, remaining = argparser.parse_known_args()

    # Config files
    cp = configparser.RawConfigParser()
    if cp.read(args.config_files):
        delattr(args, 'config_files')

    # Extensions
    exts = _extensions
    if hasattr(args, 'extensions'):
        exts += args.extensions
        delattr(args, 'extensions')

    for ext in _extensions + exts:
        ext = 'extensions.' + ext
        if not cp.has_section(ext):
            cp.add_section(ext)
        if not cp.has_option(ext, 'enabled'):
            cp[ext]['enabled'] = 'yes'

    # Log level
    log_levels = 'CRITICAL ERROR WARNING INFO DEBUG'.split(' ')
    logl = cp.get('main', 'log-level', fallback=s.get('log-level')).upper()

    if logl not in log_levels:
        msg = 'Invalid log level: {level}'
        msg = msg.format(level=logl)
        logl = s.get('log-level').upper()
        warnings.warn(msg)

    logl = log_levels.index(logl)  # Convert to int

    logl = max(0, min(4, logl + args.verbose - args.quiet))
    delattr(args, 'quiet')
    delattr(args, 'verbose')

    cp['main']['log-level'] = log_levels[logl]  # Convert back to str

    s.load_configparser(cp, root_sections=('main',))
    s.load_arguments(args)

    return s


# def build_config_parser(arguments):
#     cp = configparser.RawConfigParser()
#     cp.add_section('main')

#     if 'config_files' in arguments:
#         cp.read(arguments.config_files)

#     for attr in ('db_uri', 'downloader'):
#         if attr in arguments:
#             v = getattr(arguments, attr, None)
#             if v:
#                 cp['main'][attr.replace('_', '-')] = v

#     if 'extensions' in arguments:
#         cp['main']['extensions'] = ','.join(arguments.extensions)

#     for ext in arguments.extensions:
#         sectname = 'extension.' + ext
#         if sectname not in cp:
#             cp.add_section(sectname)

#         cp[sectname]['enabled'] = 'yes'

#     return cp


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


class Arroyo:
    def __init__(self, settings=None):
        self.settings = settings or store.Store()

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
        self.logger.setLevel(self.settings.get('log-level'))

        # Build and configure fetcher
        self.fetcher = fetchers.UrllibFetcher(
            cache=settings.get('enable-cache'),
            cache_delta=settings.get('cache-delta'),
            headers={'User-Agent': settings.get('user-agent')},
            logger=self.logger.getChild('fetcher'))

        # Built-in providers
        self.signals = signaler.Signaler()
        self.db = db.Db(self.settings.get('db-uri'))
        self.downloader = downloader.Downloader(
            self, self.settings.get('downloader'))
        self.importer = importer.Importer(self)
        self.selector = selector.Selector(self)

        # Mediainfo instance is not never used directly, it can be considered
        # as a "service", but it's keep anyway
        self.mediainfo = mediainfo.Mediainfo(self)

        # Load extensions
        for ext in [x for x in _extensions
                    if self.settings.get('extensions.' + x + '.enabled')]:
            self.load_extension(ext)

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
        ext_args = (arg() for arg in extension.arguments)
        ext_args = [x[1].get('dest', x[0][0]) for x in ext_args]

        for k in ext_args:
            self.settings.set('command.' + k, getattr(args, k))

        if self.settings.get('legacy'):
            setattr(self, 'arguments', FakeArgumentsHelper(self))

        extension.run()

        if self.settings.get('legacy'):
            delattr(self, 'arguments')
        self.settings.delete('command')

    # def run_from_args(self, arguments=None):
    #     argparser = build_argument_parser()

    #     subparser = argparser.add_subparsers(
    #         title='subcommands',
    #         dest='subcommand',
    #         description='valid subcommands',
    #         help='additional help')

    #     for (name, cmd) in self.get_implementations('command').items():
    #         command_parser = subparser.add_parser(name, help=cmd.help)
    #         for argument in cmd.arguments:
    #             args, kwargs = argument()
    #             command_parser.add_argument(*args, **kwargs)

    #     args = argparser.parse_args(arguments)
    #     if not args.subcommand:
    #         argparser.print_help()
    #         return

    #     return self.run_command(args.subcommand, args)

    # def run_command(self, command, args):
    #     try:
    #         self.arguments = args
    #         command_settings = build_basic_settings(args)
    #         command_settings.load_arguments(self.arguments)
    #         self.settings.set('command', command_settings)
    #         self.get_extension('command', command).run()
    #         self.settings.delete('command')
    #         delattr(self, 'arguments')
    #     except arroyo.exc.ArgumentError as e:
    #         self.logger.error(e)


class FakeArgumentsHelper(object):
    def __init__(self, app):
        self._app = app

    def __getattr__(self, attr):
        warnings.warn('app.arguments access is deprecated, use settings API')
        app = super(FakeArgumentsHelper, self).__getattribute__('_app')

        for k in ['command.' + attr, attr]:
            try:
                return app.settings.get(k)
            except KeyError:
                pass

        raise AttributeError(attr)
