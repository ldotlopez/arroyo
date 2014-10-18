import argparse
import configparser
import importlib

import sqlalchemy
from sqlalchemy import orm
from sqlalchemy.orm import exc
from ldotcommons import logging, sqlalchemy as ldotsa, utils

from arroyo import models, plugins, signals, downloaders, \
    SourceNotFound, ReadOnlyProperty


_logger = logging.get_logger('app')


def _build_minimal_parser():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument(
        '-h', '--help',
        action='store_true',
        dest='help')

    parser.add_argument(
        '--config-file',
        dest='config_file',
        default=utils.prog_basic_configfile())

    parser.add_argument(
        '--plugin',
        dest='plugins',
        action='append',
        default=[])

    return parser


class Arroyo:
    def __init__(self, *args, db_uri='sqlite:///:memory:', downloader='mock'):
        # Built-in providers
        self.db = db_uri
        self.downloader = downloader

        # Support structures for arguments and configs
        self.arguments = argparse.Namespace()
        self.config = configparser.ConfigParser()
        self.config.add_section('main')

        self._arg_parser = argparse.ArgumentParser()

        # Support structures for plugins
        self._modules = set()
        self._instances = {}

    @property
    def db(self):
        return self._db

    @db.setter
    def db(self, db_uri):
        try:
            self._db = Db(db_uri) if db_uri else None
        except exc.ArgumentError:
            raise ValueError()

    @property
    def downloader(self):
        return self._downloader

    @downloader.setter
    def downloader(self, value):
        if not value:
            self._downloader = None
            return

        self._downloader = Downloader(value, db_session=self.db.session)

    def parse_arguments(self, arguments=None, apply=True):
        # Load config and plugins in a first phase
        self._arg_parser = _build_minimal_parser()
        self._arg_parser.add_argument(
            '--db-uri',
            dest='db_uri')

        self._arg_parser.add_argument(
            '--downloader',
            dest='downloader')

        phase1_args, remaing_args = self._arg_parser.parse_known_args()

        if phase1_args.config_file:
            self.parse_config(phase1_args.config_file, apply=False)

        self.load_plugin(*phase1_args.plugins)

        # Build subcommands
        subparser = self._arg_parser.add_subparsers(
            title='subcommands',
            dest='subcommand',
            description='valid subcommands',
            help='additional help')

        for cmd in self._instances['command'].values():
            command_parser = subparser.add_parser(cmd.name)
            for argument in cmd.arguments:
                args, kwargs = argument()
                command_parser.add_argument(*args, **kwargs)

        # With a full bootstraped app (with plugins loaded and other stuff)
        # do a full parsing
        self.arguments = self._arg_parser.parse_args(arguments)

        if apply:
            self._apply_settings()

    def parse_config(self, config_file, apply=True):
        if config_file is None:
            return

        read = self.config.read(config_file)
        if not read or read[0] != config_file:
            _logger.warning("'{config_file}' can't be read".format(
                config_file=config_file))

        plugin_sections = [s for s in self.config.sections()
                           if s.startswith('plugin.')]
        for plugin_section in plugin_sections:
            enabled = self.config.getboolean(plugin_section, 'enabled',
                                             fallback=False)
            if enabled:
                plugin_name = plugin_section[len('plugin.'):]
                self.load_plugin(plugin_name)

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

        self.downloader = \
            self.arguments.downloader or \
            self.config.get('main', 'downloader', fallback=None) or \
            'mock'

    def load_plugin(self, *names):
        for name in names:
            if name in self._modules:
                msg = "Plugin '{name}' was already loaded"
                _logger.warning(msg.format(name=name))
                continue

            # Load module
            module_name = 'arroyo.plugins.' + name

            try:
                importlib.import_module(module_name)
                self._modules.add(name)
            except ImportError as e:
                msg = "Plugin '{name}' missing or invalid"
                _logger.warning(msg.format(name=name))
                _logger.warning(e)
                continue

    def register(self, typ='generic'):
        def decorator(cls):
            if typ not in self._instances:
                self._instances[typ] = {}

            if cls.name in self._instances[typ]:
                msg = "Plugin '{name}' already registered, skipping"
                _logger.warning(msg.format(name=cls.name))
                return cls

            self._instances[typ][cls.name] = cls()
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
            self._instances['command'][command].run()
        except plugins.ArgumentError as e:
            _logger.error(e)


class Db:
    def __init__(self, db_uri='sqlite:////:memory:'):
        engine = sqlalchemy.create_engine(db_uri)
        sessmaker = orm.sessionmaker()
        sessmaker.configure(bind=engine)
        models.Base.metadata.create_all(engine)
        self._sess = sessmaker()

    @property
    def session(self):
        return self._sess

    @session.setter
    def session(self, value):
        raise ReadOnlyProperty()

    def get(self, model, **kwargs):
        query = self.session.query(model)
        for (attr, value) in kwargs.items():
            attr = getattr(model, attr)
            query = query.filter(attr == value)

        try:
            return query.one()
        except exc.NoResultFound:
            return None

        # FIXME: Handle multiple rows found?

    def reset(self):
        for model in [models.Source, models.Movie, models.Episode]:
            for src in self._sess.query(model):
                self._sess.delete(src)
        self._sess.commit()

    def update_all_states(self, state):
        for src in self._sess.query(models.Source):
            src.state = state
        self._sess.commit()

    def shell(self):
        print("[!!] Database connection in 'sess' {}".format(self._sess))
        print("[!!] If you make any changes remember to call sess.commit()")

        sess = self._sess
        utils.get_debugger().set_trace()
        del(sess)  # Just to fix PEP-8 warning

    def search(self, all_states=False, **kwargs):
        query = ldotsa.query_from_params(self._sess, models.Source, **kwargs)
        if not all_states:
            query = query.filter(
                models.Source.state == models.Source.State.NONE)

        return query

    def get_source_by_id(self, id_):
        query = self._sess.query(models.Source)
        query = query.filter(models.Source.id == id_)

        try:
            return query.one()
        except exc.NoResultFound:
            raise SourceNotFound()

    def get_active(self):
        query = self._sess.query(models.Source)
        query = query.filter(~models.Source.state.in_(
            (models.Source.State.NONE, models.Source.State.ARCHIVED)))

        return query

    def update_source_state(self, id_, state):
        source = self.get_source_by_id(id_)
        source.state = state
        self.session.commit()


class Downloader:

    def __init__(self, downloader_name, db_session):
        self._sess = db_session

        backend_name = 'arroyo.downloaders.' + downloader_name
        backend_mod = importlib.import_module(backend_name)
        backend_cls = getattr(backend_mod, 'Downloader')

        self._backend = backend_cls(db_session=self._sess)

    def add(self, *sources):
        for src in sources:
            self._backend.do_add(src)
            src.state = models.Source.State.INITIALIZING
            self._sess.commit()

    def remove(self, *sources):
        translations = {}
        for dler_obj in self._backend.do_list():
            try:
                db_obj = self._backend.translate_item(dler_obj)
                translations[db_obj] = dler_obj
            except downloaders.NoMatchingItem:
                pass

        for src in sources:
            try:
                self._backend.do_remove(translations[src])
                src.state = models.Source.State.NONE
                self._sess.commit()

            except KeyError:
                _logger.warning(
                    "No matching object in backend for '{}'".format(src))

    def list(self):
        ret = []

        for dler_obj in self._backend.do_list():
            # Filter out objects from downloader unknow for the db
            try:
                db_obj = self._backend.translate_item(dler_obj)
            except downloaders.NoMatchingItem as e:
                _logger.warn("No matching db object for {}".format(e.item))
                continue

            # Warn about unknow states
            try:
                dler_state = self._backend.get_state(dler_obj)
            except downloaders.NoMatchingState as e:
                _logger.warn(
                    "No matching state '{}' for {}".format(e.state, db_obj))
                continue

            ret.append(db_obj)
            db_state = db_obj.state
            if db_state != dler_state:
                db_obj.state = dler_state
                signals.SIGNALS['source-state-change'].send(source=db_obj)

        self._sess.commit()
        return ret


app = Arroyo()
app.load_plugin('core')


__all__ = ['app']
