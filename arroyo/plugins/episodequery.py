# -*- coding: utf-8 -*-

from arroyo import plugin
from arroyo.plugin.tools import query


class EpisodeQuery(query.HighLevelQuery):
    KIND = 'episode'

    ENTITY_MODEL = plugin.models.Episode
    ENTITY_ATTR = 'episode'
    SELECTION_MODEL = plugin.models.EpisodeSelection

    @property
    def base_string(self):
        ret = self._get_base_string('series')

        params = {}
        for key in ['year', 'season', 'episode']:
            try:
                params[key] = int(self.params[key])
            except (KeyError, ValueError):
                pass

        if 'year' in params:
            ret += ' {}'.format(params['year'])

        if 'season' in params:
            ret += ' S{:02d}'.format(params['season'])

        if 'episode' in params:
            ret += ' E{:02d}'.format(params['episode'])

        return ret

__arroyo_extensions__ = [
    ('episode', EpisodeQuery)
]
