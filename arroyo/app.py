import argparse
import configparser
import importlib


import blinker
from sqlalchemy import orm
from ldotcommons import logging, sqlalchemy as ldotsa, utils


from arroyo import (
    analyzer,
    downloader,
    mediainfo,
    models,
    selector)
import arroyo.exc

_logger = logging.get_logger('app')


def argument(*args, **kwargs):
    """argparse argument wrapper to ease the command argument definitions"""
    def wrapped_arguments():
        return args, kwargs

    return wrapped_arguments


class Arroyo:
    def __init__(self, *args,
                 db_uri='sqlite:///:memory:', downloader_name='mock'):

        # Support structures for plugins
        self._extensions = set()
        self._registry = {}

        # Support structures for arguments and configs
        self.arguments = argparse.Namespace()
        self.config = configparser.ConfigParser()
        self.config.add_section('main')
        self._arg_parser = argparse.ArgumentParser()

        # Built-in providers
        self.signals = Signaler()
        self.db = db_uri
        self.downloader = downloader.Downloader(self, downloader_name)

        self.analyzer = analyzer.Analyzer(self)
        self.mediainfo = mediainfo.Mediainfo(self)
        self.selector = selector.Selector(self)

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

    @property
    def db(self):
        return self._db

    @db.setter
    def db(self, db_uri):
        try:
            self._db = Db(db_uri) if db_uri else None
        except arroyo.exc.ArgumentError:
            raise ValueError()

    # @property
    # def downloader(self):
    #     return self._downloader

    # @downloader.setter
    # def downloader(self, value):
    #     if not value:
    #         self._downloader = None
    #         return

    #     try:
    #         self._downloader = Downloader(value, db_session=self.db.session)
    #     except arroyo.exc.InvalidBackend as e:
    #         msg = "{error}: {original_exception}"
    #         raise arroyo.exc.ArgumentError(msg.format(
    #             error=e.args[0],
    #             original_exception=e.args[1]))

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
            _logger.warning("'{config_file}' can't be read".format(
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

        self.db = \
            self.arguments.db_uri or \
            self.config.get('main', 'db-uri', fallback=None) or \
            'sqlite:///' + utils.prog_datafile('arroyo.db', create=True)

        downloader_name = self.arguments.downloader or \
            self.config.get('main', 'downloader', fallback=None) or \
            'mock'
        self.downloader.set_backend(downloader_name)

    def load_extension(self, *names):
        for name in names:
            if name in self._extensions:
                msg = "Extension '{name}' was already loaded"
                _logger.warning(msg.format(name=name))
                continue

            # Load module
            module_name = 'arroyo.extensions.' + name

            try:
                importlib.import_module(module_name)
                self._extensions.add(name)
            except ImportError as e:
                msg = "Extension '{name}' missing or invalid"
                _logger.warning(msg.format(name=name))
                _logger.warning(e)
                continue

    # def get(self, typ, name):
    #     try:
    #         return self._instances[typ][name]
    #     except KeyError:
    #         return None

    # def get_all(self, typ):
    #     return self._instances.get(typ, {}).values()

    # def load_plugin(self, *names):
    #     for name in names:
    #         if name in self._modules:
    #             msg = "Plugin '{name}' was already loaded"
    #             _logger.warning(msg.format(name=name))
    #             continue

    #         # Load module
    #         module_name = 'arroyo.plugins.' + name

    #         try:
    #             importlib.import_module(module_name)
    #             self._modules.add(name)
    #         except ImportError as e:
    #             msg = "Plugin '{name}' missing or invalid"
    #             _logger.warning(msg.format(name=name))
    #             _logger.warning(e)
    #             continue

    # def register(self, typ='generic'):
    #     def decorator(cls):
    #         if typ not in self._instances:
    #             self._instances[typ] = {}

    #         if not hasattr(cls, 'name'):
    #             msg = "Plugin {class_name} has no name property, skipping"
    #             _logger.error(msg.format(class_name=cls.__name__))
    #             return cls

    #         if cls.name in self._instances[typ]:
    #             msg = "Plugin '{name}' already registered, skipping"
    #             _logger.warning(msg.format(name=cls.name))
    #             return cls

    #         try:
    #             self._instances[typ][cls.name] = cls()
    #         except plugins.ArgumentError as e:
    #             msg = "Plugin '{name}' can't be initialized: {reason}"
    #             _logger.error(msg.format(name=cls.name, reason=str(e)))
    #         return cls

    #     return decorator

    def register(self, extension_point, extension_name):
        def decorator(cls):
            if extension_point not in self._registry:
                self._registry[extension_point] = {}

            if extension_name in self._registry[extension_point]:
                msg = "Extension '{name}' already registered, skipping"
                _logger.warning(msg.format(name=cls.name))
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
            _logger.error(e)


class Db:
    def __init__(self, db_uri='sqlite:////:memory:'):
        # engine = sqlalchemy.create_engine(db_uri)
        # sessmaker = orm.sessionmaker()
        # sessmaker.configure(bind=engine)
        # models.Base.metadata.create_all(engine)
        # self._sess = sessmaker()
        # FIXME: ldotcommons.sqlalchemy.create_session it's not totally safe,
        # review this.
        self._sess = ldotsa.create_session(db_uri)

    @property
    def session(self):
        return self._sess

    @session.setter
    def session(self, value):
        raise arroyo.exc.ReadOnlyProperty()

    def get(self, model, **kwargs):
        query = self.session.query(model).filter_by(**kwargs)

        # FIXME: Handle multiple rows found?
        try:
            return query.one()
        except orm.exc.NoResultFound:
            return None

    def get_or_create(self, model, **kwargs):
        obj = self.get(model, **kwargs)
        if not obj:
            return model(**kwargs), True
        else:
            return obj, False

    def reset(self):
        for model in [models.Source, models.Movie, models.Episode]:
            for src in self._sess.query(model):
                self._sess.delete(src)
        self._sess.commit()

    def update_all_states(self, state):
        for src in self._sess.query(models.Source):
            src.state = state
        if state == models.Source.State.NONE:
            self._sess.query(models.Selection).delete()
        self._sess.commit()

    def shell(self):
        print("[!!] Database connection in 'sess' {}".format(self._sess))
        print("[!!] If you make any changes remember to call sess.commit()")
        sess = self._sess  # nopep8
        utils.get_debugger().set_trace()

    def search(self, all_states=False, **kwargs):
        query = ldotsa.query_from_params(self._sess, models.Source, **kwargs)
        if not all_states:
            query = query.filter(
                models.Source.state == models.Source.State.NONE)

        return query

    def get_active(self):
        query = self._sess.query(models.Source)
        query = query.filter(~models.Source.state.in_(
            (models.Source.State.NONE, models.Source.State.ARCHIVED)))

        return query


class Signaler:
    def __init__(self):
        self._signals = {}

    def register(self, name):
        if name in self._signals:
            msg = "Signal '{name}' was already registered"
            raise ValueError(msg.format(name=name))

        ret = blinker.signal(name)
        self._signals[name] = ret

        return ret

    def connect(self, name, call, *args, **kwargs):
        self._signals[name].connect(call, *args, **kwargs)

    def send(self, name, *args, **kwargs):
        self._signals[name].send(*args, **kwargs)


app = Arroyo()

extensions = {
    'importers': ('eztv', 'spanishtracker', 'thepiratebay'),
    'selectors': ('source', 'episode'),
    'commands': ('analyze', 'db', 'downloads', 'mediainfo', 'search'),
    'downloaders': ('mock', 'transmission')
}

for (k, v) in extensions.items():
    exts = ["%s.%s" % (k, e) for e in v]
    app.load_extension(*exts)


__all__ = ['app']
