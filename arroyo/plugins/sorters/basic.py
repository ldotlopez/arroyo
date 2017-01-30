# -*- coding: utf-8 -*-

from arroyo import plugin


import functools
import itertools


class Sorter(plugin.Sorter):
    __extension_name__ = 'basic'

    def cmp_source_health(self, a, b):
        # print("==========")
        # print("'{}' <-> '{}'".format(a.name, b.name))

        def _filter_mediainfo_tags(d):
            return {k[10:]: v for (k, v) in d.items()
                    if k.startswith('mediainfo.')}

        a_info = _filter_mediainfo_tags(a.tag_dict)
        b_info = _filter_mediainfo_tags(b.tag_dict)

        def is_proper(info):
            return "Proper" in info.get('other', [])

        def has_release_group(info):
            return info.get('releaseGroup')

        def seeds_are_relevant(src):
            return (src.seeds or 0) > 10

        # proper over non-proper
        a_is_proper = is_proper(a_info)
        b_is_proper = is_proper(b_info)

        if a_is_proper and not b_is_proper:
            # print("  '{}' by proper".format(a.name))
            return -1

        if b_is_proper and not a_is_proper:
            # print("  '{}' by proper".format(b.name))
            return 1

        #
        # Priorize s/l info over others
        #
        if seeds_are_relevant(a) and not seeds_are_relevant(b):
            # print("  '{}' by valid seeds".format(a.name))
            return -1

        if seeds_are_relevant(b) and not seeds_are_relevant(a):
            # print("  '{}' by valid seeds".format(b.name))
            return 1

        #
        # Order by seed ratio
        #
        if (a.leechers and b.leechers):
            # print(a.share_ratio, b.share_ratio)
            try:
                balance = (max(a.share_ratio, b.share_ratio) /
                           min(a.share_ratio, b.share_ratio))
                if balance > 1.2:
                    # print("  By share ratio (with balance)".format())
                    return -1 if a.share_ratio > b.share_ratio else 1

            except ZeroDivisionError:
                return -1 if int(a.share_ratio) else 1

            # print("  By seeds (without balance)".format())
            return -1 if a.seeds > b.seeds else 1

        #
        # Put releases from a team over others
        #
        a_has_release_team = has_release_group(a_info)
        b_has_release_team = has_release_group(b_info)

        if a_has_release_team and not b_has_release_team:
            # print("  '{}' by release team ".format(a.name))
            return -1
        if b_has_release_team and a_has_release_team:
            # print("  '{}' by release team ".format(b.name))
            return 1

        # print('  Too bad')
        # Nothing makes one source better that the other
        # Fallback to default sort
        if a == b:
            return 0

        return -1 if a < b else 1

    def sort(self, items):
        m = {}

        for item in items:
            if item.entity not in m:
                m[item.entity] = []

            m[item.entity].append(item)

        for entity in m:
            if entity is None:
                continue

            m[entity] = sorted(
                m[entity],
                key=functools.cmp_to_key(self.cmp_source_health))

        return itertools.chain.from_iterable((m[k] for k in m))


__arroyo_extensions__ = [
    Sorter
]
