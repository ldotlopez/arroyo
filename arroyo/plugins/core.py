from urllib import parse


from ldotcommons import fetchers, logging, sqlalchemy as ldotsa, utils
import sqlalchemy


import arroyo
from arroyo import importers, models, plugins
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


def source_repr(source):
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


def sub_config_dict(ns):
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


@app.register('command')
class AnalyzeCommand:
    name = 'analyze'
    help = 'Analyze an origin merging discovered sources into the database'

    arguments = (
        plugins.argument(
            '-a', '--analyzer',
            dest='analyzer',
            type=str,
            help='analyzer to run'),
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

    def __init__(self):
        app.signals.register('source-added')
        app.signals.register('source-updated')
        app.signals.register('sources-added-batch')
        app.signals.register('sources-updated-batch')

    def run(self):
        analyzer_name = app.arguments.analyzer
        seed_url = app.arguments.url
        iterations = app.arguments.iterations
        typ = app.arguments.type
        language = app.arguments.language

        if analyzer_name and isinstance(analyzer_name, str):
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
                    'analyzer_name': analyzer_name,
                    'seed_url': seed_url,
                    'iterations': iterations,
                    'type': typ,
                    'language': language
                }
            }

        else:
            origins = sub_config_dict('origin')

        if not origins:
            raise plugins.ArgumentError("No origins specified")

        sources = []
        for (origin_name, opts) in origins.items():
            opts['typ'] = opts.pop('type', None)
            try:
                opts['iterations'] = int(opts['iterations'])
            except (ValueError, KeyError):
                opts['iterations'] = 1

            try:
                sources += analyze(**opts)
            except importers.ProcessException as e:
                msg = "Unable to analyze '{origin_name}': {error}"
                _logger.error(msg.format(origin_name=origin_name, error=e))

        ret = {
            'added-sources': [],
            'updated-sources': [],
        }

        for src in sources:
            obj, created = app.db.get_or_create(models.Source, id=src['id'])
            for key in src:
                setattr(obj, key, src[key])

            if created:
                app.db.session.add(obj)

            signal_name = 'source-added' if created else 'source-updated'
            app.signals.send(signal_name, source=obj)

            batch_key = 'added-sources' if created else 'updated-sources'
            ret[batch_key].append(obj)

        app.signals.send('sources-added-batch',
                         sources=ret['added-sources'])
        app.signals.send('sources-updated-batch',
                         sources=ret['updated-sources'])

        app.db.session.commit()

        return ret


def analyze(analyzer_name,
            seed_url=None, iterations=1, typ=None, language=None):
    # Build real objects
    analyzer_mod = utils.ModuleFactory('arroyo.importers')(analyzer_name)

    iterations = max(1, int(iterations))

    url_generator = analyzer_mod.url_generator(seed_url)
    fetcher = fetchers.UrllibFetcher(
        cache=True, cache_delta=60 * 20, headers={'User-Agent': _UA})
    overrides = {
        'type': typ,
        'language': language,
        'provider': analyzer_mod.__name__.split('.')[-1]
    }
    overrides = {k: v for (k, v) in overrides.items() if v is not None}

    sources = []
    for itr in range(0, iterations):
        url = next(url_generator)

        msg = "{analyzer_name}: iteration {iteration}/{iterations}: {url}"
        _logger.debug(msg.format(
            analyzer_name=analyzer_name,
            iteration=(itr + 1),
            iterations=(iterations),
            url=url))

        # Fetch its contents
        buff = fetcher.fetch(url)

        # Pass buffer over analyzer funcion and fix some fields
        srcs = analyzer_mod.process(buff)
        for src in srcs:
            src['id'] = parse.parse_qs(
                parse.urlparse(src['uri']).query)['xt'][-1]
            src.update(overrides)

        sources += srcs

    return sources


@app.register('command')
class SearchCommand:
    name = 'search'
    help = 'Simple search'
    arguments = (
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
            help='Push found sources to downloader.'),
        plugins.argument(
            'keywords',
            action='append',
            help='Keywords.')
    )

    def run(self):
        f = {
            'name_like': '%' + '%'.join(app.arguments.keywords) + '%'
        }

        sync()

        matches = query(f, all_states=app.arguments.all_states).all()

        print("Query '{query_name}': found {n_results} results".format(
            query_name=' '.join(app.arguments.keywords), n_results=len(matches)
        ))

        for src in matches:
            print(source_repr(src))

            if not app.arguments.push:
                continue

        if app.arguments.push:
            app.downloader.add(*matches)

        sync()


@app.register('command')
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
            queries = sub_config_dict('query')

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
                print(source_repr(src))

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

    filter_impls = app.get_all('filter')
    query = app.db.session.query(models.Source)

    for (key, value) in filters.items():
        filter_impl = None
        for f_i in filter_impls:
            if key in f_i.handles:
                filter_impl = f_i
                break

        if filter_impl is None:
            msg = "filter {filter} is not recognized"
            _logger.warning(msg.format(filter=key))
            continue

        query = filter_impl.filter(query, key, value)

    if not all_states:
        query = query.filter(models.Source.state == models.Source.State.NONE)

    return query


@app.register('command')
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


@app.register('command')
class SyncCommand:
    name = 'sync'
    help = 'Sync database information with downloader'
    arguments = ()

    def __init__(self):
        app.signals.register('source-state-change')

    def run(self):
        sync()


def sync():
    ret = {'sources-state-change': []}

    downloads = set(app.downloader.list())
    actives = set(app.db.get_active())

    for source in actives - downloads:
        source.state = models.Source.State.ARCHIVED
        ret['sources-state-change'].append(source)
        app.signals.send('source-state-change', source=source)

    app.db.session.commit()

    return ret


@app.register('command')
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
            print(source_repr(src))

    elif add:
        try:
            source = app.db.get_source_by_id(source_id)

        except arroyo.SourceNotFound:
            _logger.error("No source {source_id}".format(source_id=source_id))
            return

        app.downloader.add(source)

    elif remove:
        try:
            source = app.db.get_source_by_id(source_id)
            if source not in app.db.get_active():
                msg = 'Source {source.name} {source.id} is not active'
                _logger.warn(msg.format(source=source))

        except arroyo.SourceNotFound:
            _logger.error("No source {source_id}".format(source_id=source_id))
            return

        app.downloader.remove(source)


@app.register('filter')
class CoreFilters:
    name = 'core'
    handles = []

    model = models.Source

    def __init__(self):
        for (colname, column) in self.model.__table__.columns.items():
            coltype = column.type

            if isinstance(coltype, sqlalchemy.String):
                self.handles.append(colname)
                self.handles.append(colname + '_like')
                self.handles.append(colname + '_regexp')

            if isinstance(coltype, sqlalchemy.Integer):
                self.handles.append(colname)
                self.handles.append(colname + '_min')
                self.handles.append(colname + '_max')

    def filter(self, query, key, value):
        if '_' in key:
            mod = key.split('_')[-1]
            key = '_'.join(key.split('_')[:-1])
        else:
            key = key
            mod = None

        attr = getattr(self.model, key, None)

        if mod == 'like':
            query = query.filter(attr.like(value))

        elif mod == 'regexp':
            query = query.filter(attr.op('regexp')(value))

        elif mod == 'min':
            value = utils.parse_size(value)
            query = query.filter(attr >= value)

        elif mod == 'max':
            value = utils.parse_size(value)
            query = query.filter(attr <= value)

        else:
            query = query.filter(attr == value)

        return query


@app.register('filter')
class EpisodeFilters:
    name = 'episodes'
    handles = ['series', 'series_in']

    model = models.Episode

    def filter(self, query, key, value):
        query = query.join(models.Episode)

        if key == 'series':
            query = query.join(self.model)
            return query.filter(self.model.series.like(value))

        if key == 'series_in':
            value = [x.strip().lower() for x in value.split(',')]
            query = query.join(models.Episode)
            return query.filter(
                sqlalchemy.func.lower(models.Episode.series).in_(value))
