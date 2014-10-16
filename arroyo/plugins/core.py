from urllib import parse

from ldotcommons import fetchers, logging, sqlalchemy as ldotsa, utils

from arroyo import models, signals
from arroyo.app import app
from arroyo.plugins import argument, ArgumentError

_logger = logging.get_logger('arroyo.plugins.core')

_UA = 'Mozilla/5.0 (X11; Linux x86) Home software (KHTML, like Gecko)'


def analize(analizer_name, seed_url=None, iterations=1, typ=None, language=None):
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

class AnalizeCommand:
    name = 'analize'
    help = 'Analize an origin merging discovered sources into the database'

    arguments = (
        argument(
            '-a', '--analizer',
            dest='analizer',
            type=str,
            help='analizer to run'),
        argument(
            '-u', '--url',
            dest='url',
            type=str,
            default=None,
            help='Seed URL'),
        argument(
            '-i', '--iterations',
            dest='iterations',
            type=int,
            help='iterations to run',
            default=1),
        argument(
            '-t', '--type',
            dest='type',
            type=str,
            help='force type of found sources'),
        argument(
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

        # Safety checks
        if analizer_name is None:
            raise ArgumentError('analizer name is required')

        if not isinstance(seed_url, (str, type(None))):
            raise ArgumentError('seed_url must be an string or None')

        if not isinstance(iterations, int) or iterations < 1:
            raise ArgumentError('iterations must be an integer greater than 1')

        if not isinstance(typ, (str, type(None))):
            raise ArgumentError('type must be an string or None')

        if not isinstance(language, (str, type(None))):
            raise ArgumentError('languge must be an string or None')

        sources = analize(analizer_name, seed_url, iterations, typ, language)

        # Get existing sources before doing any insert or update
        # FIXME: Avoid using app.db.session directly, build an appropiate API
        sources = {x['id']: x for x in sources}
        query = app.db.session.query(models.Source).filter(
            models.Source.id.in_(sources.keys()))
        existing = {x.id: x for x in query.all()}

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
                signals.SIGNALS['source-added'].send(source=obj)
            else:
                for key in src:
                    setattr(obj, key, src[key])
                ret['updated-sources'].append(obj)
                signals.SIGNALS['source-updated'].send(source=obj)

        app.db.session.commit()
        signals.SIGNALS['sources-added-batch'].send(sources=ret['added-sources'])
        signals.SIGNALS['sources-updated-batch'].send(sources=ret['updated-sources'])

        return ret

class QueryCommand:
    name = 'query'
    help = 'Advanced search'
    arguments = (
        argument(
            '-f', '--filter',
            dest='filters',
            type=str,
            action=utils.DictAction,
            help='Filters to apply in key_mod=value form'),
        argument(
            '-a', '--all',
            dest='all_states',
            action='store_true',
            help='Include all results (by default only sources with NONE state are displayed)'),
        argument(
            '-p', '--push',
            dest='push',
            action='store_true',
            help='Push found sources to downloader.')
    )

    @staticmethod
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

    def run(self):
        filters = app.arguments.filters
        all_states = app.arguments.all_states
        push = app.arguments.push

        queries = {}
        if filters:
            queries['command line'] = filters
        else:
            cfg_dict = utils.configparser_to_dict(app.config)
            multi_depth_cfg = utils.MultiDepthDict(cfg_dict)
            queries = multi_depth_cfg.subdict('query')

        for (query_name, filters) in queries.items():
            filters = self.query_params_glob_to_like(filters)
            print(query_name, repr(filters))
        else:
            _logger.error("No query specified")
            return

        print(filters, all_states, push)
    # core.sync()

    # for (search, opts) in queries.items():
    #     _logger.info("{search}: Search started".format(search=search))

    #     # Convert glob filters to db (sqlite basically) 'like' format
    #     opts = query_params_glob_to_like(opts)

    #     try:
    #         sources = core.search(all_states=all_states, **opts)

    #         for src in sources:
    #             print(source_repr(src))
    #             if push:
    #                 core.downloader.add(src)

    #     except arroyo.ArgumentError as e:
    #         _logger.error(e)

    # if push:
    #     core.sync()

app.register_command(AnalizeCommand)
app.register_command(QueryCommand)
