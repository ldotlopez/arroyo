# -*- coding: utf-8 -*-

"""Watchlist plugin for arroyo.

Implements importing watchlist from imdb (or others) and watch matching source

Configuration example:

plugin.watchlist:
  enabled: True

  query-defaults: {}

  lists:
    imdb: http://www.imdb.com/user/ur12345678/watchlist?view=compact

    alternative_form_imdb:
        url: http://www.imdb.com/user/ur36400746/watchlist?view=compact
        query:
            language: eng-us


"""

from arroyo import (
    models,
    plugin
)

import asyncio
import json
import re

import bs4
from ldotcommons import utils
import sqlalchemy as sa
from sqlalchemy import schema


class Watchitem(models.Base):
    __tablename__ = 'watchitem'
    __table_args__ = (
        schema.PrimaryKeyConstraint('source_uri', 'source_id', name='pk'),
    )

    enabled = sa.Column(sa.Boolean, nullable=False, default=True)
    source_uri = sa.Column(sa.String, nullable=False)
    source_id = sa.Column(sa.String, nullable=False)

    query = sa.Column(sa.String, nullable=True)
    last_search = sa.Column(sa.Integer, nullable=False, default=0)
    data = sa.Column(sa.String, nullable=True)


class Watchlist:
    def __init__(self, app, logger=None):
        self.app = app
        self.logger = logger or app.logger
        self.sess = self.app.db.session

        self.parser_map = {
            'imdb': self.parse_imdb
        }

        self.app.db.install_model(Watchitem)
        self.app.settings.add_validator(
            self.validator,
            revalidate='plugin.watchlist'
        )

    def validator(self, key, value):
        print(key, value)

    def _identify_buffer(self, buff):
        if 'imdb' in buff.lower():
            return 'imdb'

        return None

    def get_configured_watchlists(self):
        lists = self.app.settings.get('plugin.watchlist.lists', {})
        query = self.app.settings.get('plugin.watchlist.query-defaults', {})

        ret = {}
        for (name, desc) in lists.items():
            if isinstance(desc, str):
                desc = dict(uri=desc)

            if 'query' not in desc:
                desc['query'] = {}

            desc['query'].update(query)
            ret[name] = desc

        return ret

    def parse(self, buff):
        typ = self._identify_buffer(buff)
        if typ is None:
            raise ValueError('Unable to parse watchlist')

        return self.parser_map[typ](buff)

    def parse_imdb(self, buff):
        type_map = {
            'feature': 'movie',
            'tv series': 'episode'
        }

        def process_node(x):
            a = x.select_one('td.title a')
            if not a:
                return None

            name = a.text
            href = a.get('href', '')

            m = re.search(r'/(tt\d+)/?', href)
            imdb_id = m.group(1) if m else None

            if not imdb_id:
                return

            typ = x.select_one('.title_type').text
            typ = type_map.get(typ.lower(), None)

            if typ == 'movie':
                query = dict(kind='movie', title=name)

            elif typ == 'episode':
                query = dict(kind='episode', series=name)

            else:
                msg = "Cannot convert imdb type «{type}»"
                msg = msg.format(type=typ)
                self.logger.warning(msg)
                return None

            # Keep in sync with model
            return dict(
                source_id=imdb_id,
                query=query,
                data=dict(imdb_id=imdb_id)
            )

        soup = bs4.BeautifulSoup(buff, 'html.parser')
        nodes = soup.select('.list_item')
        ret = [process_node(x) for x in nodes]
        ret = [x for x in ret if x is not None]

        return ret

    @asyncio.coroutine
    def process(self, uri):
        buff = yield from self.app.fetcher.fetch(uri)
        res = self.parse(buff.decode('utf-8'))

        if not res:
            return

        if not isinstance(res, list):
            msg = "Parser returned invalid data type for '{uri}': '{type}'"
            msg = msg.format(uri=uri, type=type(res))
            return

        # Get items in both sides
        items_in_uri = {x['source_id']: x for x in res}
        items_in_db = {
            x.source_id: x
            for x in self.sess.query(Watchitem).filter(
                Watchitem.source_uri == uri
            ).all()
        }

        # Disable watchitems not in uri
        to_delete = set(items_in_db.keys()) - set(items_in_uri.keys())
        for x in to_delete:
            items_in_db[x].enabled = False
        # if to_delete:
        #     self.sess.delete(*[
        #         items_in_db[x] for x in to_delete
        #     ])

        # Create new queries not in db
        to_create = set(items_in_uri.keys()) - set(items_in_db.keys())
        to_create = [
            Watchitem(
                source_uri=uri, source_id=x,
                query=json.dumps(items_in_uri[x]['query']),
                data=json.dumps(items_in_uri[x].get('data', None)),
            )
            for x in to_create
        ]
        self.sess.add_all(to_create)

    def scan_lists(self):
        items = []

        lists = self.get_configured_watchlists()
        if not lists:
            return

        # Disable items not in lists
        disabled = self.app.db.session.query(Watchitem).filter(
            ~Watchitem.source_uri.in_(list(lists.keys()))
        )
        for x in disabled:
            x.enabled = False

        # Start parsing
        tasks = [self.process(desc['uri']) for desc in lists.values()]

        loop = asyncio.get_event_loop()
        loop.run_until_complete(asyncio.gather(*tasks))

        self.sess.commit()

    def download(self, limit=0):
        lists = self.get_configured_watchlists()
        query_by_uri = {
            desc['uri']: desc['query']
            for desc in lists.values()
        }

        items = self.sess.query(Watchitem).filter(
            Watchitem.enabled == True  # nopep8
        ).order_by(
            sa.asc(Watchitem.last_search)
        )
        if limit:
            items = items.limit(limit)

        for item in items:
            query = json.loads(item.query)
            query.update(query_by_uri.get(item.source_uri, {}))

            query = self.app.selector.get_query_from_params(query)
            matches = self.app.selector.matches(query)

            item.last_search = utils.now_timestamp()

            print(query)
            if matches:
                matches = list(self.app.selector.sort(matches))
                print("-> ", matches)
            else:
                print("-> No matches")

        self.sess.commit()


class WatchlistScanLists(plugin.CronTask):
    NAME = "watchlist-scan"
    INTERVAL = '30H'

    def run(self):
        Watchlist(self.app).scan_lists()
        super().run()


class WatchlistDownload(plugin.CronTask):
    NAME = "watchlist-download"
    INTERVAL = '30H'

    def run(self):
        Watchlist(self.app).download(10)
        super().run()

__arroyo_extensions__ = [
    ('watchlist-scan', WatchlistScanLists),
    ('watchlist-download', WatchlistDownload)
]
