# -*- coding: utf-8 -*-
# [SublimeLinter pep8-max-line-length:119]
# vim: set fileencoding=utf-8 :

import argparse
import re
import sys
import warnings

from appkit import logging
from appkit import messaging
from appkit import sqlalchemy as ldotsa
from appkit import utils

import arroyo
from arroyo import models


DEFAULT_URI = 'sqlite:///' + \
    utils.prog_datafile('arroyo.sqlite3', prog='arroyo', create=True)

DEFAULT_DOWNLOADER_NAME = 'transmission'

_LISTING_FMT = "[{icon}] {id} {name}"
_STATE_SYMBOL_TABLE = {
    models.Source.State.INITIALIZING: '⋯',
    models.Source.State.PAUSED: '‖',
    models.Source.State.DOWNLOADING: '↓',
    models.Source.State.SHARING: '⇅',
    models.Source.State.DONE: '✓',
    models.Source.State.ARCHIVED: '▣'
}


_logger = logging.get_logger('main')


def source_repr(source):
    return _LISTING_FMT.format(
        icon=_STATE_SYMBOL_TABLE.get(source.state, ' '),
        id=source.id,
        name=source.name)


def _build_argument_parser():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(
        dest='subcommand',
        help='sub-command help')

    # Use const instead of default, see 2nd case in:
    # http://docs.python.org/3.3/library/argparse.html?highlight=argparser#const
    parser.add_argument(
        '-c', '--config',
        dest='config_file',
        nargs='?',
        const=utils.prog_configfile('arroyo.ini', prog='arroyo'),
        help="Use configuration file")

    # Global arguments

    parser.add_argument(
        '-u', '--db-uri',
        dest='db_uri',
        type=str,
        # default=DEFAULT_URI,
        help='URI for db')

    parser.add_argument(
        '-d', '--downloader',
        dest='downloader_name',
        help='Downloader to use')

    parser.add_argument(
        '-n', '--notifier',
        dest='notifiers',
        type=str,
        action='append',
        help='notifiers')

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

    # Analizer arguments

    parser_anlz = subparsers.add_parser('analize', help='Analize sources')

    parser_anlz.add_argument(
        '-a', '--analizer',
        dest='analizer_name',
        type=str,
        help='analizer to run'),

    parser_anlz.add_argument(
        '-u', '--url',
        dest='seed_url',
        type=str,
        default=None,
        help='Seed URL')

    parser_anlz.add_argument(
        '-i', '--iterations',
        dest='iterations',
        type=int,
        help='iterations to run',
        default=1)

    parser_anlz.add_argument(
        '-t', '--type',
        dest='type',
        type=str,
        help='force type of found sources')

    parser_anlz.add_argument(
        '-l', '--language',
        dest='language',
        type=str,
        help='force language of found sources')

    # sync
    subparsers.add_parser('sync', help='Sync downloader info')

    # mediainfo

    subparsers.add_parser('mediainfo', help='Update mediainfo')

    # Search
    parser_search = subparsers.add_parser(
        'search', help='Search for sources and optionally download.')

    parser_search.add_argument(
        '-a', '--all',
        dest='all_states',
        action='store_true',
        help='Include all results (by default only sources with NONE state are displayed)')

    parser_search.add_argument(
        '-p', '--push',
        dest='push',
        action='store_true',
        help='Push found sources to downloader.')

    parser_search.add_argument(
        'keywords',
        nargs='+',
        type=str,
        help='Keywords to search')

    # Query
    parser_query = subparsers.add_parser(
        'query', help='Advanced search, see search help')

    parser_query.add_argument(
        '-f', '--filter',
        dest='filters',
        type=str,
        action=utils.DictAction,
        help='Filters to apply in key_mod=value form')

    parser_query.add_argument(
        '-a', '--all',
        dest='all_states',
        action='store_true',
        help='Include all results (by default only sources with NONE state are displayed)')

    parser_query.add_argument(
        '-p', '--push',
        dest='push',
        action='store_true',
        help='Push found sources to downloader.')

    parser_downloads = subparsers.add_parser('downloads', help='Show and manage downloads')

    parser_downloads.add_argument(
        '-l', '--list',
        dest='show',
        action='store_true',
        help='Show current downloads')

    parser_downloads.add_argument(
        '-a', '--add',
        dest='add_source_id',
        help='Download a source ID')

    parser_downloads.add_argument(
        '-r', '--remove',
        dest='remove_source_id',
        help='Cancel (and/or remove) a source ID')

    # Db arguments
    parser_db = subparsers.add_parser('db', help='Manage database commands')

    parser_db.add_argument(
        '--shell',
        dest='shell',
        action='store_true',
        help='Start a interactive python interpreter in the db environment')

    parser_db.add_argument(
        '--reset-db',
        dest='reset_db',
        action='store_true',
        help='Empty db')

    parser_db.add_argument(
        '--reset-states',
        dest='reset_states',
        action='store_true',
        help='Sets state to NONE on all sources')

    parser_db.add_argument(
        '--archive-all',
        dest='archive_all',
        action='store_true',
        help='Sets state to ARCHIVED on all sources')

    parser_db.add_argument(
        '--reset',
        dest='reset_source_id',
        help='Reset state of a source')

    parser_db.add_argument(
        '--archive',
        dest='archive_source_id',
        help='Archive a source')

    # Webui

    parser_webui = subparsers.add_parser('webui')

    parser_webui.add_argument(
        '-i', '--interface',
        dest='interface',
        help='IP adress to use')

    parser_webui.add_argument(
        '-p', '--port',
        dest='port',
        type=int,
        help='Port to use')

    return parser


def _configure_messaging(cfg, *names):
    for name in names:
        cfg_notifier = None
        backend = None

        try:
            cfg_notifier = cfg[name]
            backend = cfg_notifier.pop('backend')
        except KeyError as e:
            _logger.error('{name}: Not properly configured'.format(name=name))
            backend = None

        if not backend:
            continue

        try:
            messaging.enable(name, backend, **cfg_notifier)
        except utils.FactoryError as e:
            msg = "{name}: Can't create a notifier for '{backend}' based " + \
                "on the parameters {parameters}"
            _logger.error(msg.format(
                name=name, backend=backend, parameters=repr(cfg_notifier)
            ))
            _logger.error("{name}: Error reported was:".format(name=name))
            _logger.error("{name}: {error}".format(name=name, error=repr(e)))


def keywords_to_query(*keywords):
    keywords = ' '.join(keywords)
    keywords = re.sub(r'\s+', '*', keywords)

    return {'name_like': '*' + keywords + '*'}


def query_params_glob_to_like(query_params):
    ret = {}

    for (param, value) in query_params.items():
        if param.endswith('_like'):
            value = ldotsa.glob_to_like(value)

            if not value.startswith('%'):
                value = '%' + value

            if not value.endswith('%'):
                value = value + '%'

        ret[param] = value

    return ret


def _handle_analize(core, origins):
    if not isinstance(origins, dict) or len(origins) < 1:
        raise arroyo.ArgumentError('No origins specified')

    # Setup a signal handler
    sources_store = []

    def on_source_add(sender, source, **kwargs):
        nonlocal sources_store
        sources_store.append(source)

    arroyo.SIGNALS['source-add'].connect(on_source_add)

    for (origin, opts) in origins.items():
        sources_store = []  # Reset source_store for each origin
        fmt_vars = {'origin': origin}

        _logger.info("{origin}: Analisys started".format(**fmt_vars))

        try:
            opts['iterations'] = int(opts.get('iterations', 1))
        except (TypeError, ValueError, KeyError):
            opts['iterations'] = 1

        opts['type_'] = opts.pop('type', None)
        try:
            core.analize(**opts)
        except arroyo.ArgumentError as e:
            _logger.error(e)
            continue

        fmt_vars = {
            'origin': origin,
            'sources': sources_store,
            'n_sources': len(sources_store)}

        if sources_store:
            msg = "{origin}: Found {n_sources} source(s)".format(**fmt_vars)
        else:
            msg = "{origin}: No new sources found".format(**fmt_vars)

    arroyo.SIGNALS['source-add'].disconnect(on_source_add)


def _handle_search(**opts):
    core = opts.pop('core')

    keywords = opts.pop('keywords')
    if not isinstance(keywords, list) or len(keywords) == 0:
        raise arroyo.ArgumentError('Missing keywords argument')

    opts['queries'] = {
        ' '.join(keywords): keywords_to_query(*keywords)
    }
    return _handle_query(core, **opts)


def _handle_query(core, queries, all_states, push):
    if not queries:
        raise arroyo.ArgumentError('Missing search/query')

    core.sync()

    for (search, opts) in queries.items():
        _logger.info("{search}: Search started".format(search=search))

        # Convert glob filters to db (sqlite basically) 'like' format
        opts = query_params_glob_to_like(opts)

        try:
            sources = core.search(all_states=all_states, **opts)

            for src in sources:
                print(source_repr(src))
                if push:
                    core.downloader.add(src)

        except arroyo.ArgumentError as e:
            _logger.error(e)

    if push:
        core.sync()


def _handle_downloads(core,
                      show=False, add=False, remove=False, source_id=None):
    if sum([1 if x else 0 for x in [show, add, remove]]) != 1:
        msg = 'Only one option from show/add/remove is allowed'
        raise arroyo.ArgumentError(msg)

    need_source_id = (add or remove)
    valid_source_id = isinstance(source_id, str) and source_id != ''

    if need_source_id and not valid_source_id:
        raise arroyo.ArgumentError('Invalid source id')

    core.sync()

    if show:
        for src in core.get_active():
            print(source_repr(src))

    elif add:
        try:
            source = core.get_source_by_id(source_id)
        except arroyo.SourceNotFound:
            _logger.error("No source {source_id}".format(source_id=source_id))
            return

        core.downloader.add(source)

    elif remove:
        try:
            source = core.get_source_by_id(source_id)
            if source not in core.get_active():
                _logger.warn('Source {source.name} {source.id} is not active'.format(source=source))
        except arroyo.SourceNotFound:
            _logger.error("No source {source_id}".format(source_id=source_id))
            return

        core.downloader.remove(source)


def _handle_sync(core):
    def on_source_state_change(sender, source, *kwargs):
        if source.state == models.Source.State.NONE:
            return

        msg = "Source {}: {}".format(source.state_name, source.name)
        messaging.send(msg)

    arroyo.SIGNALS['source-state-change'].connect(on_source_state_change)
    core.sync()
    arroyo.SIGNALS['source-state-change'].connect(on_source_state_change)


def _handle_db_cmd(core, reset, shell, reset_states, archive_all, reset_source_id, archive_source_id):
    test = [1 for x in (reset, shell, reset_states, archive_all, reset_source_id, archive_source_id) if x]

    if sum(test) == 0:
        raise arroyo.ArgumentError('No action specified')

    elif sum(test) > 1:
        msg = 'Just one option can be specified at one time'
        raise arroyo.ArgumentError(msg)

    if reset:
        core.reset()

    if reset_states:
        core.update_all_states(models.Source.State.NONE)

    if archive_all:
        core.update_all_states(models.Source.State.ARCHIVED)

    if shell:
        core.shell()

    if reset_source_id or archive_source_id:
        if reset_source_id:
            state = models.Source.State.NONE
        else:
            state = models.Source.State.ARCHIVED

        core.update_source_state(
            reset_source_id or archive_source_id,
            state)


def _handle_webui(core, interface, port, debug):
    if not isinstance(interface, str) or port == '':
        msg = "Invalid inteface parameter: {interface}"
        msg = msg.format(interface=interface)
        raise arroyo.ArgumentError(msg)

    orig_port = port
    if not isinstance(port, int):
        try:
            port = int(port)
        except ValueError:
            port = 0

    if port <= 0:
        msg = \
            "webui: value for port parameter ({port}) is invalid, " + \
            "it must be a number greater than 0"
        msg = msg.format(port=orig_port)

        raise arroyo.ArgumentError(msg)

    core.webui = True
    core.sync()
    ret = core.webui.run(host=interface, port=port, debug=debug)
    core.webui = False

    return ret

if __name__ == '__main__':
    #
    # Main parses both command line arguments and config file
    #
    # In a first stage it populates opts_cmdl from command line. Global
    # options are sanitized and opts dict is populated
    #
    # Once the config file is loaded its values from the main section are
    # copied into opts dict
    #
    # Finally for each subcommand a similar process is made:
    # - Ensure a subdict in opts dict for subcommand especific options
    # - Load those (sanitized) suboptions from (and in this order): command
    # line, config file and default hardcoded value

    # Initialize command line and arguments

    arg_parser = _build_argument_parser()
    opts_cmdl = vars(arg_parser.parse_args(sys.argv[1:]))
    opts = {}

    # Load config file if any

    opts['config_file'] = opts_cmdl.get('config_file', None)

    if opts['config_file']:
        cfg = utils.ini_load(opts['config_file'])
        if 'main' not in cfg:
            cfg['main'] = {}
    else:
        cfg = {'main': {}}

    cfg = utils.MultiDepthDict(cfg)

    # Configure loglevel ASAP

    opt_cmdl_quiet = opts_cmdl.get('quiet', 0)
    opt_cmdl_verbose = opts_cmdl.get('verbose', 0)

    if opt_cmdl_quiet or opt_cmdl_verbose:
        v = 2
        v = max(0, v - opt_cmdl_quiet)
        v = min(4, v + opt_cmdl_verbose)

        logging_levels = 'critical error warning info debug'.split(' ')
        logging_levels = [x.upper() for x in logging_levels]
        logging_levels = [getattr(logging.logging, x) for x in logging_levels]
        opts['logging_level'] = logging_levels[v]
    else:
        opts['logging_level'] = cfg['main'].get('logging_level', 'WARNING')

    del(opt_cmdl_quiet)
    del(opt_cmdl_verbose)

    try:
        logging.set_level(opts['logging_level'])
    except ValueError:
        opts['logging_level'] = 'WARNING'
        msg = "Invalid logging level, fallback to {level}"
        warnings.warn(msg.format(level=opts['logging_level']))
        logging.set_level(opts['logging_level'])

    # Handle global options

    opts['db_uri'] = opts_cmdl.get('db_uri', None) \
        or cfg['main'].get('db_uri', None) \
        or DEFAULT_URI

    opts['downloader_name'] = opts_cmdl.get('downloader_name', None) \
        or cfg['main'].get('downloader_name', None) \
        or DEFAULT_DOWNLOADER_NAME

    # Configure notifiers

    notifiers = cfg['main'].get('notifiers')
    if notifiers:
        notifiers = re.split(r'\s*,\s*', notifiers)
    else:
        notifiers = opts_cmdl.get('notifiers') or ()

    _configure_messaging(cfg.subdict('notifier'), *notifiers)

    # Get subcommand
    subcommand = opts_cmdl.get('subcommand')
    if not subcommand:
        arg_parser.print_usage(sys.stderr)
        sys.exit(1)

    try:
        core = arroyo.Arroyo(
            db_uri=opts['db_uri'],
            downloader_name=opts['downloader_name'])
    except arroyo.downloaders.BackendError as e:
        _logger.critical('Error within the downloader backend')
        _logger.critical(e.exception.original)
        sys.exit(1)

    #
    # Analize
    # This subcommand has no specific options.
    # Config file can include [origin.label] sections
    #
    if subcommand == 'analize':

        if opts_cmdl.get('analizer_name'):
            s = '[command line]'
            origins = {s: {}}
            keys = (
                'analizer_name',
                'seed_url',
                'iterations',
                'type',
                'language')
            for k in keys:
                origins[s][k] = opts_cmdl.get(k, None)
        else:
            origins = {k: v for (k, v) in cfg.subdict('origin').items()}

        try:
            _handle_analize(
                core=core,
                origins=origins)
        except arroyo.ArgumentError as e:
            _logger.critical(e)
            sys.exit(1)

    # Search
    # Simple alias to query subcommand
    elif subcommand == 'search':

        try:
            _handle_search(
                core=core,
                keywords=opts_cmdl.get('keywords'),
                push=opts_cmdl.get('push', False),
                all_states=opts_cmdl.get('all_states', False))

        except arroyo.ArgumentError as e:
            _logger.critical(e)
            sys.exit(1)

    #
    # Query
    # This subcommand has no specific options.
    # Config file can include [filter.label] sections
    # 'downloader_name' and 'all_states' options are only available thru
    # command line
    #
    elif subcommand == 'query':

        if opts_cmdl.get('filters', False):
            searches = {'[command line]': opts_cmdl['filters']}
        else:
            searches = cfg.subdict('filter')

        try:
            _handle_query(
                core=core,
                queries=searches,
                all_states=opts_cmdl.get('all_states', False),
                push=opts_cmdl.get('push', False))

        except arroyo.ArgumentError as e:
            _logger.critical(e)
            sys.exit(1)

    #
    # sync
    # This subcommand has no specific options.
    # 'downloader_name' must be specified at command line
    #
    elif subcommand == 'sync':

        try:
            _handle_sync(core=core)

        except arroyo.ArgumentError as e:
            _logger.critical(e)
            sys.exit(1)

    elif subcommand == 'downloads':
        show = opts_cmdl.get('show') or False
        add, remove = False, False
        source_id = None

        source_id_add = opts_cmdl.get('add_source_id') or None
        if source_id_add:
            add, source_id = True, source_id_add

        source_id_remove = opts_cmdl.get('remove_source_id') or None
        if source_id_remove:
            remove, source_id = True, source_id_remove

        if not add and not remove:
            show = True

        try:
            _handle_downloads(
                core=core,
                show=show,
                add=add,
                remove=remove,
                source_id=source_id)

        except arroyo.ArgumentError as e:
            _logger.critical(e)
            sys.exit(1)

    #
    # DB
    # This subcommand has no specific options.
    # 'reset', 'shell', 'reset_states' and 'archive_all' options are only
    # available thru command line
    #
    elif subcommand == 'db':

        try:
            _handle_db_cmd(
                core=core,
                reset=opts_cmdl.get('reset', False),
                shell=opts_cmdl.get('shell', False),
                reset_states=opts_cmdl.get('reset_states', False),
                archive_all=opts_cmdl.get('archive_all', False),
                reset_source_id=opts_cmdl.get('reset_source_id', None),
                archive_source_id=opts_cmdl.get('archive_source_id', None))
        except arroyo.ArgumentError as e:
            _logger.critical(e)
            sys.exit(1)

    #
    # WebUI
    # Config file subsection: [webui]
    # Options include: 'downloader_name', 'interface' and 'port'
    #
    elif subcommand == 'webui':

        if 'webui' not in cfg:
            cfg['webui'] = {}

        downloader_name = opts_cmdl.get('downloader_name', None) or \
            cfg['webui'].get('downloader_name', None) or \
            None

        interface = opts_cmdl.get('interface') or \
            cfg['webui'].get('interface', None) or \
            '0.0.0.0'

        port = opts_cmdl.get('port', None) or \
            cfg['webui'].get('port', None) or \
            5000

        try:
            _handle_webui(
                core=core,
                interface=interface,
                port=port,
                debug=True)
        except arroyo.ArgumentError as e:
            _logger.critical(e)
            sys.exit(1)

    #
    # Unknow or missing subcommand, print help and exit
    else:

        arg_parser.print_usage()
        sys.exit(1)

    sys.exit(0)
