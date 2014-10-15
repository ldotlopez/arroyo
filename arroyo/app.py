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


class ArroyoNG(metaclass=utils.SingletonMetaclass):
    def __init__(self, *args, **kwargs):
        super(ArroyoNG, self).__init__()

        self.db = Db()

        self._plugins = {}
        self._commands = {}

        self._config_parser = configparser.ConfigParser()

        self._global_arg_parser = argparse.ArgumentParser(add_help=False)
        self._global_arg_parser.add_argument(
            '--config',
            dest='config_file',
            default=utils.prog_basic_configfile())
        self._global_arg_parser.add_argument(
            '--plugin',
            dest='plugins',
            action='append',
            nargs=1,
            default=[])
        self._global_arg_parser.add_argument(
            '--db-uri',
            dest='db_uri',
            default=utils.prog_datafile('arroyo.db', create=True))

        self._arg_parser = argparse.ArgumentParser()
        self._subparsers = self._arg_parser.add_subparsers(
            title='subcommands',
            dest='subcommand',
            description='valid subcommands',
            help='additional help')

    def load_plugins(self, *plugins):
        plugin_factory = utils.ModuleFactory('arroyo.plugins')

        for p in [p for p in plugins if p not in self._plugins]:
            try:
                self._plugins[p] = plugin_factory(p)
            except KeyError:
                _logger.warning("Plugin '{name}' missing".format(name=p))

    def register_command(self, cmd_cls):
        command_parser = self._subparsers.add_parser(cmd_cls.name)
        for argument in cmd_cls.arguments:
            args, kwargs = argument()
            command_parser.add_argument(*args, **kwargs)

        self._commands[cmd_cls.name] = cmd_cls
        _logger.info("Command '{name}' registered".format(name=cmd_cls.name))

    def _parse_arguments(self, arguments=None):
        args, remaining_args = self._global_arg_parser.parse_known_args(
            arguments)
        args.plugins = list(chain.from_iterable(args.plugins))
        self.load_plugins(*args.plugins)
        if args.config_file:
            self._parse_config_file(args.config_file)

        args = self._arg_parser.parse_args(remaining_args)
        if not args.subcommand:
            self._arg_parser.print_help()
            sys.exit(2)

        return args

    def _parse_config_file(self, config_file_path):
        read = self._config_parser.read(config_file_path)
        if not read or read[0] != config_file_path:
            _logger.warning("unable to read '{path}'".format(
                path=config_file_path))

    def run(self, arguments=None):
        args = self._parse_arguments(arguments)
        self.run_command(args.subcommand)

    def run_command(self, command):
        try:
            self._commands[command]().run()
        except KeyError:
            _logger.error("subcommand '{name}' not found".format(name=command))


class Db:
    def __init__(self, db_uri='sqlite:////:memory:'):
        engine = sqlalchemy.create_engine('sqlite:///:memory:')
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
app.load_plugins('core')


__all__ = ['app']
