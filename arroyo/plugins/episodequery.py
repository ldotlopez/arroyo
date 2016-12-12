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

        if 'year' in self.params:
            ret += ' {}'.format(self.params['year'])

        if 'season' in self.params:
            ret += ' S{:02d}'.format(self.params['season'])

        if 'episode' in self.params:
            ret += ' E{:02d}'.format(self.params['season'])

        return ret

__arroyo_extensions__ = [
    ('episode', EpisodeQuery)
]
