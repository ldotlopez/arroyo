import argparse
import configparser
from itertools import chain
import sys

import sqlalchemy
from sqlalchemy import exc, orm

from ldotcommons import logging, sqlalchemy as ldotsa, utils

from arroyo import models


_logger = logging.get_logger('app')


class SourceNotFound(Exception):
    pass


class ReadOnlyProperty(Exception):
    pass


def _build_parser_base():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument(
        '--config-file',
        dest='config_file',
        default=utils.prog_basic_configfile())
    parser.add_argument(
        '--db-uri',
        dest='db_uri',
        default='sqlite:///' + utils.prog_datafile('arroyo.db', create=True))
    parser.add_argument(
        '--plugin',
        dest='plugins',
        action='append',
        nargs=1,
        default=[])
    parser.add_subparsers(
        title='subcommands',
        dest='subcommand',
        description='valid subcommands',
        help='additional help')
    return parser


def parse_options():
    """
    Parse those options that are essentials and very influential in App's
    behaviour
    """
    parser = _build_parser_base()

    basic_args, remaining_args = parser.parse_known_args()
    basic_args.plugins = list(chain.from_iterable(basic_args.plugins))

    config = configparser.ConfigParser()
    config.read(basic_args.config_file)

 

    return config


class ArroyoNG(metaclass=utils.SingletonMetaclass):
    def __init__(self, *args, db_uri='sqlite:///:memory:'):
        super(ArroyoNG, self).__init__()

        # Built-in providers
        self.db = db_uri
        self._downloader = None

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
            dest='db_uri',
            default='sqlite:///' + utils.prog_datafile('arroyo.db', create=True))
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
        if not self._downloader:
            raise Exception('db not configured')

        return self._downloader

    @downloader.setter
    def downloader(self):
        raise ValueError()

    def parse_arguments(self, arguments=None, apply=True):
        self.arguments = self._arg_parser.parse_args(arguments)

        # Load config file if it is specified in arguments
        if self.arguments.config_file:
            self.parse_config(self.arguments.config_file, apply=False)

        # Sync db-uri
        self.config.set('main', 'db-uri', self.arguments.db_uri)

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

        # Note: Global options are in sync from arguments so there is no need of additional checks
        self.db = self.config.get('main', 'db-uri')

    def load_plugin(self, *plugins):
        plugin_factory = utils.ModuleFactory('arroyo.plugins')

        for p in [p for p in plugins if p not in self._plugins]:
            try:
                self._plugins[p] = plugin_factory(p)
            except KeyError:
                _logger.warning("Plugin '{name}' missing".format(name=p))
                continue

            # Build config section
            plugin_section = 'plugin.' + p
            if not self.config.has_section(plugin_section):
                self.config.add_section(plugin_section)
            self.config.set(plugin_section, 'enabled', 'true')

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
        self._commands[command]().run()


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

app = ArroyoNG()
app.load_plugin('core')


__all__ = ['app']
