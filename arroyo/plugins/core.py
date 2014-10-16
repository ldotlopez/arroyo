from urllib import parse

from ldotcommons import fetchers, logging, sqlalchemy as ldotsa, utils

import arroyo
from arroyo import importers, signals, models, plugins
from arroyo.app import app


_logger = logging.get_logger('arroyo.plugins.core')

_UA = 'Mozilla/5.0 (X11; Linux x86) Home software (KHTML, like Gecko)'

#
# Notes:
# - Module level funcions MUST NOT have side effects, they CAN NOT call
#   other module level functions. p.ex. query() calling sync()
# - Module level functions can (and must) do argument checking but MUST NOT
#   do transformations or interpretations on them because...
# - Command classes MUST interpret parameters from user and MUST DO any
#   transformations or interpretations on them
# - Message or logging MUST be responsability of the run() method of command
#   classes
#
# Commands/functions following those rules are:
# - QueryCommand / query


def _source_repr(source):
    _LISTING_FMT = "[{icon}] {id} {name}"
    _STATE_SYMBOL_TABLE = {
        models.Source.State.INITIALIZING: '⋯',
        models.Source.State.PAUSED: '‖',
        models.Source.State.DOWNLOADING: '↓',
        models.Source.State.SHARING: '⇅',
        models.Source.State.DONE: '✓',
        models.Source.State.ARCHIVED: '▣'
    }

    return _LISTING_FMT.format(
        icon=_STATE_SYMBOL_TABLE.get(source.state, ' '),
        id=source.id,
        name=source.name)


def _sub_config_dict(ns):
    cfg_dict = utils.configparser_to_dict(app.config)
    multi_depth_cfg = utils.MultiDepthDict(cfg_dict)
    return multi_depth_cfg.subdict(ns)


def _query_params_glob_to_like(query_params):
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


class AnalizeCommand:
    name = 'analize'
    help = 'Analize an origin merging discovered sources into the database'

    arguments = (
        plugins.argument(
            '-a', '--analizer',
            dest='analizer',
            type=str,
            help='analizer to run'),
        plugins.argument(
            '-u', '--url',
            dest='url',
            type=str,
            default=None,
            help='Seed URL'),
        plugins.argument(
            '-i', '--iterations',
            dest='iterations',
            type=int,
            help='iterations to run',
            default=1),
        plugins.argument(
            '-t', '--type',
            dest='type',
            type=str,
            help='force type of found sources'),
        plugins.argument(
            '-l', '--language',
            dest='language',
            type=str,
            help='force language of found sources')
    )

    def run(self):
        analizer_name = app.arguments.analizer
        seed_url = app.arguments.url
        iterations = app.arguments.iterations
        typ = app.arguments.type
        language = app.arguments.language

        if analizer_name and isinstance(analizer_name, str):
            if not isinstance(seed_url, (str, type(None))):
                raise plugins.ArgumentError(
                    'seed_url must be an string or None')

            if not isinstance(iterations, int) or iterations < 1:
                raise plugins.ArgumentError(
                    'iterations must be an integer greater than 1')

            if not isinstance(typ, (str, type(None))):
                raise plugins.ArgumentError(
                    'type must be an string or None')

            if not isinstance(language, (str, type(None))):
                raise plugins.ArgumentError(
                    'languge must be an string or None')

            origins = {
                'command line': {
                    'analizer_name': analizer_name,
                    'seed_url': seed_url,
                    'iterations': iterations,
                    'type': typ,
                    'language': language
                }
            }

        else:
            origins = _sub_config_dict('origin')

        if not origins:
            raise plugins.ArgumentError("No origins specified")

        sources = []
        for (origin_name, opts) in origins.items():
            opts['typ'] = opts.pop('type', None)
            try:
                sources += analize(**opts)
            except importers.ProcessException as e:
                msg = "Unable to analize '{origin_name}': {error}"
                _logger.error(msg.format(origin_name=origin_name, error=e))

        # Get existing sources before doing any insert or update
        # FIXME: Avoid using app.db.session directly, build an appropiate API
        sources = {x['id']: x for x in sources}

        query = app.db.session.query(models.Source)
        query = query.filter(models.Source.id.in_(sources.keys()))

        existing = {x.id: x for x in query}

        ret = {
            'added-sources': [],
            'updated-sources': [],
        }

        for (id_, src) in sources.items():
            obj = existing.get(id_, None)

            if not obj:
                obj = models.Source(**src)
                app.db.session.add(obj)
                ret['added-sources'].append(obj)
            else:
                for key in src:
                    setattr(obj, key, src[key])
                ret['updated-sources'].append(obj)

            signal_name = 'source-updated' if obj else 'source-added'
            signals.SIGNALS[signal_name].send(source=obj)

        app.db.session.commit()

        signals.SIGNALS['sources-added-batch'].send(
            sources=ret['added-sources'])
        signals.SIGNALS['sources-updated-batch'].send(
            sources=ret['updated-sources'])

        return ret


def analize(analizer_name,
            seed_url=None, iterations=1, typ=None, language=None):
    # Build real objects
    analizer_mod = utils.ModuleFactory('arroyo.importers')(analizer_name)

    iterations = max(1, iterations)

    url_generator = analizer_mod.url_generator(seed_url)
    fetcher = fetchers.UrllibFetcher(
        cache=True, cache_delta=60 * 20, headers={'User-Agent': _UA})
    overrides = {
        'type': typ,
        'language': language,
        'provider': analizer_mod.__name__.split('.')[-1]
    }
    overrides = {k: v for (k, v) in overrides.items() if v is not None}

    sources = []
    for itr in range(0, iterations):
        url = next(url_generator)

        msg = "{analizer_name}: iteration {iteration}/{iterations}: {url}"
        _logger.debug(msg.format(
            analizer_name=analizer_name,
            iteration=(itr + 1),
            iterations=(iterations),
            url=url))

        # Fetch its contents
        buff = fetcher.fetch(url)

        # Pass buffer over analizer funcion and fix some fields
        srcs = analizer_mod.process(buff)
        for src in srcs:
            src['id'] = parse.parse_qs(
                parse.urlparse(src['uri']).query)['xt'][-1]
            src.update(overrides)

        sources += srcs

    return sources


class QueryCommand:
    name = 'query'
    help = 'Advanced search'
    arguments = (
        plugins.argument(
            '-f', '--filter',
            dest='filters',
            type=str,
            action=utils.DictAction,
            help='Filters to apply in key_mod=value form'),
        plugins.argument(
            '-a', '--all',
            dest='all_states',
            action='store_true',
            help='Include all results ' +
                 '(by default only sources with NONE state are displayed)'),
        plugins.argument(
            '-p', '--push',
            dest='push',
            action='store_true',
            help='Push found sources to downloader.')
    )

    def run(self):
        filters = app.arguments.filters
        all_states = app.arguments.all_states
        push = app.arguments.push

        queries = {}
        if filters:
            queries['command line'] = filters
        else:
            queries = _sub_config_dict('query')

        if not queries:
            raise plugins.ArgumentError("No query specified")

        sync()

        matches = []
        for (query_name, filters) in queries.items():
            filters = _query_params_glob_to_like(filters)
            matches = query(filters, all_states=all_states).all()

            print("Query '{query_name}': found {n_results} results".format(
                query_name=query_name, n_results=len(matches)
            ))
            for src in matches:
                print(_source_repr(src))

                if not push:
                    continue

                app.downloader.add(src)

        sync()


def query(filters, all_states=False):
    if not filters:
        raise plugins.ArgumentError('Al least one filter is needed')

    if not isinstance(filters, dict):
        raise plugins.ArgumentError('Filters must be a dictionary')

    if not isinstance(all_states, bool):
        raise plugins.ArgumentError('all_states parameter must be a bool')

    # FIXME: Use 'filter' plugins here
    query = ldotsa.query_from_params(app.db.session, models.Source, **filters)
    if not all_states:
        query = query.filter(models.Source.state == models.Source.State.NONE)

    return query


class DbCommand:
    name = 'db'
    help = 'Database commands'
    arguments = (
        plugins.argument(
            '--shell',
            dest='shell',
            action='store_true',
            help='Start a interactive python interpreter in the db ' +
                 'environment'),

        plugins.argument(
            '--reset-db',
            dest='reset',
            action='store_true',
            help='Empty db'),

        plugins.argument(
            '--reset-states',
            dest='reset_states',
            action='store_true',
            help='Sets state to NONE on all sources'),

        plugins.argument(
            '--archive-all',
            dest='archive_all',
            action='store_true',
            help='Sets state to ARCHIVED on all sources'),

        plugins.argument(
            '--reset',
            dest='reset_source_id',
            help='Reset state of a source'),

        plugins.argument(
            '--archive',
            dest='archive_source_id',
            help='Archive a source')
        )

    def run(self):
        var_args = vars(app.arguments)
        keys = ('shell reset_db reset_states archive_all ' +
                'reset_source_id archive_source_id').split()
        opts = {k: var_args.get(k, None) for k in keys}
        opts = {k: v for (k, v) in opts.items() if v is not None}

        db_command(**opts)


def db_command(reset=False, shell=False, reset_states=False, archive_all=False,
               reset_source_id=None, archive_source_id=None):
    test = [1 for x in (reset, shell, reset_states, archive_all,
                        reset_source_id, archive_source_id) if x]

    if sum(test) == 0:
        raise plugins.ArgumentError('No action specified')

    elif sum(test) > 1:
        msg = 'Just one option can be specified at one time'
        raise plugins.ArgumentError(msg)

    if reset:
        app.db.reset()

    if reset_states:
        app.db.update_all_states(models.Source.State.NONE)

    if archive_all:
        app.db.update_all_states(models.Source.State.ARCHIVED)

    if shell:
        app.db.shell()

    if reset_source_id or archive_source_id:
        if reset_source_id:
            state = models.Source.State.NONE
        else:
            state = models.Source.State.ARCHIVED

        app.db.update_source_state(
            reset_source_id or archive_source_id,
            state)


class SyncCommand:
    name = 'sync'
    help = 'Sync database information with downloader'
    arguments = ()

    def run(self):
        sync()


def sync():
    ret = {'sources-state-change': []}

    downloads = set(app.downloader.list())
    actives = set(app.db.get_active())

    for source in actives - downloads:
        source.state = models.Source.State.ARCHIVED
        ret['sources-state-change'].append(source)
        signals.SIGNALS['source-state-change'].send(source=source)

    app.db.session.commit()
    return ret


class DownloadsCommand:
    name = 'downloads'
    help = 'Show and manage downloads'
    arguments = (
        plugins.argument(
            '-l', '--list',
            dest='show',
            action='store_true',
            help='Show current downloads'),

        plugins.argument(
            '-a', '--add',
            dest='add',
            help='Download a source ID'),

        plugins.argument(
            '-r', '--remove',
            dest='remove',
            help='Cancel (and/or remove) a source ID')
    )

    def run(self):

        show = app.arguments.show
        add, remove = False, False
        source_id = None

        source_id_add = app.arguments.add
        if source_id_add:
            add, source_id = True, source_id_add

        source_id_remove = app.arguments.remove
        if source_id_remove:
            remove, source_id = True, source_id_remove

        if not add and not remove:
            show = True

        sync()
        downloads(
            show=show,
            add=add,
            remove=remove,
            source_id=source_id)


def downloads(show=False, add=False, remove=False, source_id=None):
    if sum([1 if x else 0 for x in [show, add, remove]]) != 1:
        msg = 'Only one option from show/add/remove is allowed'
        raise plugins.ArgumentError(msg)

    need_source_id = (add or remove)
    valid_source_id = isinstance(source_id, str) and source_id != ''

    if need_source_id and not valid_source_id:
        raise plugins.ArgumentError('Invalid source id')

    if show:
        for src in app.db.get_active():
            print(_source_repr(src))

    elif add:
        try:
            source = app.db.get_source_by_id(source_id)

        except SourceNotFound:
            _logger.error("No source {source_id}".format(source_id=source_id))
            return

        app.downloader.add(source)

    elif remove:
        try:
            source = app.db.get_source_by_id(source_id)
            if source not in app.db.get_active():
                msg = 'Source {source.name} {source.id} is not active'
                _logger.warn(msg.format(source=source))

        except SourceNotFound:
            _logger.error("No source {source_id}".format(source_id=source_id))
            return

        app.downloader.remove(source)


app.register_command(AnalizeCommand)
app.register_command(QueryCommand)
app.register_command(DbCommand)
app.register_command(SyncCommand)
app.register_command(DownloadsCommand)
