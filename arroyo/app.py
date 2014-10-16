import argparse
import configparser
import importlib
from itertools import chain

import sqlalchemy
from sqlalchemy import exc, orm

from ldotcommons import logging, sqlalchemy as ldotsa, utils

from arroyo import models, plugins, signals, downloaders


_logger = logging.get_logger('app')


class Arroyo:
    def __init__(self, *args, db_uri='sqlite:///:memory:', downloader='mock'):
        # Built-in providers
        self.db = db_uri
        self.downloader = downloader

        # Support structures for arguments and configs
        self.arguments = argparse.Namespace()
        self.config = configparser.ConfigParser()
        self.config.add_section('main')

        # Support structures for plugins
        self._plugins = {}
        self._commands = {}

        # Build basic argument parser, plugins will add their options
        self._arg_parser = argparse.ArgumentParser()

        self._arg_parser.add_argument(
            '--config-file',
            dest='config_file',
            default=utils.prog_basic_configfile())

        self._arg_parser.add_argument(
            '--db-uri',
            dest='db_uri')

        self._arg_parser.add_argument(
            '--downloader',
            dest='downloader')

        self._arg_parser.add_argument(
            '--plugin',
            dest='plugins',
            action='append',
            nargs=1,
            default=[])

        self._cmd_parser = self._arg_parser.add_subparsers(
            title='subcommands',
            dest='subcommand',
            description='valid subcommands',
            help='additional help')

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
        self.arguments = self._arg_parser.parse_args(arguments)

        # Load config file if it is specified in arguments
        if self.arguments.config_file:
            self.parse_config(self.arguments.config_file, apply=False)

        # Handle plugins
        self.arguments.plugins = chain.from_iterable(self.arguments.plugins)
        self.load_plugin(*self.arguments.plugins)

        if apply:
            self._apply_settings()

    def parse_config(self, config_file, apply=True):
        if config_file is None:
            return

        read = self.config.read(config_file)
        if not read or read[0] != config_file:
            _logger.warning("'{config_file}' can't be read".format(
                config_file=config_file))

        if apply:
            self._apply_settings()

    def _apply_settings(self):
        """
        Aplies global settings from arguments and config
        """

        self.db = \
            self.arguments.db_uri or \
            self.config.get('main', 'db-uri') or \
            'sqlite:///' + utils.prog_datafile('arroyo.db', create=True)

        self.downloader = \
            self.arguments.downloader or \
            self.config.get('main', 'downloader') or \
            'mock'

    def load_plugin(self, *plugins):
        for p in [p for p in plugins if p not in self._plugins]:
            try:
                module_name = 'arroyo.plugins.' + p
                self._plugins[p] = importlib.import_module(module_name)
            except ImportError as e:
                _logger.warning("Plugin '{name}' missing".format(name=p))
                _logger.warning(e)
                continue

            # Build config section
            plugin_section = 'plugin.' + p
            if not self.config.has_section(plugin_section):
                self.config.add_section(plugin_section)
            self.config.set(plugin_section, 'enabled', 'true')

    def register_plugin(self, plugin_cls):
        self._plugins[plugin_cls.name] = plugin_cls()

    def register_command(self, cmd_cls):
        command_parser = self._cmd_parser.add_parser(cmd_cls.name)
        for argument in cmd_cls.arguments:
            args, kwargs = argument()
            command_parser.add_argument(*args, **kwargs)

        self._commands[cmd_cls.name] = cmd_cls
        _logger.info("Command '{name}' registered".format(name=cmd_cls.name))

    def run(self, arguments=None):
        if not self.arguments.subcommand:
            self._arg_parser.print_help()
            return

        self.run_command(self.arguments.subcommand)

    def run_command(self, command):
        try:
            self._commands[command]().run()
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
