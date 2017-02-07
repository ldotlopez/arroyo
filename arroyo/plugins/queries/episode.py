# -*- coding: utf-8 -*-

from arroyo import pluginlib
from arroyo.pluginlib import query
models = pluginlib.models


class EpisodeQuery(query.HighLevelQuery):
    __extension_name__ = 'episode'

    KIND = 'episode'

    ENTITY_MODEL = models.Episode
    ENTITY_ATTR = 'episode'
    SELECTION_MODEL = models.EpisodeSelection

    @property
    def base_string(self):
        ret = self._get_base_string('series')
        if not ret:
            return super().base_string

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
                ret += 'E{:02d}'.format(params['episode'])

        return ret

__arroyo_extensions__ = [
    EpisodeQuery
]
