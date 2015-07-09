import functools
import itertools


from arroyo import exts


class Sorter(exts.Sorter):
    def cmp_source_health(self, a, b):
        def _filter_mediainfo_tags(d):
            return {k[10:]: v for (k, v) in d.items()
                    if k.startswith('mediainfo.')}

        a_info = _filter_mediainfo_tags(a.tag_dict)
        b_info = _filter_mediainfo_tags(b.tag_dict)

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

    def sort(self, items):
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
    ('sorter', 'basic', Sorter),
]
