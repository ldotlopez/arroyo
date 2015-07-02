import functools
import itertools


import guessit


from arroyo import exts, models


class Sorter(exts.Filter):
    APPLIES_TO = models.Source
    HANDLES = ('share-ratio-sort',)

    def cmp_source_health(self, a, b):
        if a.episode or b.movie:
            a_info = guessit.guess_video_info(a.name)
            b_info = guessit.guess_video_info(b.name)
        else:
            a_info = {}
            b_info = {}

        def is_proper(info):
            return "Proper" in info.get('other', [])

        def has_release_group(info):
            return info.get('releaseGroup')

        # proper over non-proper
        a_is_proper = is_proper(a_info)
        b_is_proper = is_proper(b_info)

        if a_is_proper and not b_is_proper:
            return -1

        if b_is_proper and not a_is_proper:
            return 1

        #
        # Put releases from a team over others
        #
        a_has_release_team = has_release_group(a_info)
        b_has_release_team = has_release_group(b_info)

        if a_has_release_team and not b_has_release_team:
            return -1
        if b_has_release_team and a_has_release_team:
            return 1

        # Nothing makes one source better that the other
        # Fallback to default sort
        if a == b:
            return 0

        return -1 if a < b else 1

    def apply(self, items):
        m = {}

        for item in items:
            if item.superitem not in m:
                m[item.superitem] = []

            m[item.superitem].append(item)

        for superitem in m:
            if superitem is None:
                continue

            m[superitem] = sorted(
                m[superitem],
                key=functools.cmp_to_key(self.cmp_source_health))

        return itertools.chain.from_iterable((m[k] for k in m))

__arroyo_extensions__ = [
    ('filter', 'share-ratio-sort', Sorter),
]
