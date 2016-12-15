# -*- coding: utf-8 -*-

from arroyo import plugin


class FakeOrigin(plugin.Origin):
    BASE_URL = 'http://example.com/?page=1'
    PROVIDER_NAME = 'fake'

    def paginate(self, url):
        yield from self.paginate_by_query_param(url, 'page', default=1)

    def parse(self, buff, parser):
        """
        Finds referentes to sources in buffer.
        Returns a list with source infos
        """

        data = []
        for x in range(0, 5):
            data.append({
                'name': 'Source #{}'.format(x),
                'uri': 'magnet:?xt=urn:btih:{:040d}'.format(x)
                })

        return data

__arroyo_extensions__ = [
    FakeOrigin
]
