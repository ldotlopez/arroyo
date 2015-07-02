import functools
import itertools


import guessit


from arroyo import exts, models


class Sorter(exts.Filter):
    APPLIES_TO = models.Source
    HANDLES = ('share-ratio-sort',)

    def cmp_source_health(self, a, b):
        def is_proper(x):
            return "Proper" in \
                   guessit.guess_video_info(x.name).get('other', [])

        # Only applied to episode or movie
        # A proper match is top priority
        if a.episode or b.movie:
            proper_a = is_proper(a)
            proper_b = is_proper(b)

            if proper_a and not proper_b:
                return -1

            if proper_b and not proper_a:
                return 1

        # Nothings make one source better that the other.
        # Fallback to default sort
        if a == b:
            return 0

        return -1 if a < b else 1

    def apply(self, items):
        ret = []
        for (hl, group) in itertools.groupby(items, lambda x: x.superitem):
            if hl:
                group = sorted(
                    group,
                    key=functools.cmp_to_key(self.cmp_source_health))

            ret.append(group)

        return itertools.chain.from_iterable(ret)

__arroyo_extensions__ = [
    ('filter', 'share-ratio-sort', Sorter),
]
