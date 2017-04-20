# -*- coding: utf-8 -*-

# Copyright (C) 2015 Luis López <luis@cuarentaydos.com>
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301,
# USA.


# FIXME:
# Keep in sync with method Selector._query_params_from_keyword

import re
from appkit import logging
from arroyo import (
    mediainfo,
    pluginlib
)

models = pluginlib.models


class CodecFilter(pluginlib.IterableFilter):
    __extension_name__ = 'codec'

    APPLIES_TO = models.Source
    HANDLES = ['codec']

    def filter(self, key, value, item):
        item_video_codec = item.tag_dict.get(mediainfo.Tags.VIDEO_CODEC, '')
        return (value.lower() == item_video_codec.lower())


class Container(pluginlib.IterableFilter):
    """
    Note: Container is the first extension found in item.name.
    Ex:
    - Foo.S01.E01.720p.HDTV.X264-DIMENSION.mkv -> mkv
    - Foo.S01.E01.720p.HDTV.X264-DIMENSION.mkv[foo].avi -> mkv

    Use mimetype or name-glob='*.ext' if you want to filter by "extension"
    """
    __extension_name__ = 'container'

    APPLIES_TO = models.Source
    HANDLES = ['container', 'container-in', 'mimetype', 'mimetype-in']

    def filter(self, key, value, item):
        if key.endswith('-in'):
            if not isinstance(value, list):
                value = [x.strip() for x in value.split(',')]

            key = key[:-3]  # Strip -in suffix

        else:
            value = [value]

        container = item.tag_dict.get(
            mediainfo.Tags.MEDIA_CONTAINER, '').lower()
        mimetype = item.tag_dict.get(
            mediainfo.Tags.MIMETYPE, '').lower()

        # Container can be a list for some broken sources like:
        # Foo.S01.E01.720p.HDTV.X264-DIMENSION.mkv[eztv].avi

        # For this reason we are going to convert container and mimetypes
        # into lists in order to "simplify" codepaths
        if not isinstance(container, list):
            containers = [container]
        containers = [x.lower() for x in containers]
        mimetypes = [mimetype.lower()]

        stack = containers if key == 'container' else mimetypes
        needles = [x.lower() for x in value]

        return any([x in stack for x in needles])


class QualityFilter(pluginlib.IterableFilter):
    __extension_name__ = 'quality'

    APPLIES_TO = models.Source
    HANDLES = ['quality']
    _SUPPORTED = ['1080p', '720p', '480p', 'hdtv']

    def filter(self, key, value, item):
        value = value.lower()

        if value not in self._SUPPORTED:
            msg = ("Quality '{quality}' not supported, "
                   "only {supported_qualities} are supported")

            supported = ", ".join("'{}'".format(x)
                                  for x in self._SUPPORTED)
            msg = msg.format(
                quality=value,
                supported_qualities=supported)

            raise ValueError(msg)

        screen_size = item.tag_dict.get(
            mediainfo.Tags.VIDEO_SCREEN_SIZE, '').lower()
        fmt = item.tag_dict.get(
            mediainfo.Tags.VIDEO_FORMAT, '').lower()

        # Check for plain HDTV (in fact it means no 720p or anything else)
        if value == 'hdtv':
            is_match = not screen_size and fmt == 'hdtv'

        else:
            is_match = value == screen_size

        return is_match


class ReleaseGroupFilter(pluginlib.IterableFilter):
    __extension_name__ = 'release-group'

    APPLIES_TO = models.Source
    HANDLES = ['release-group', 'release-group-in']

    def filter(self, key, value, item):
        if key == 'release-group':
            if not isinstance(value, str):
                raise ValueError(value)
            value = [value]

        if key == 'release-group-in':
            if not isinstance(value, list):
                value = [x.strip() for x in value.split(',')]

        item_rg = item.tag_dict.get(mediainfo.Tags.RELEASE_GROUP, '').lower()
        if not item_rg:
            return False

        groups = [x.lower() for x in value]
        if not groups:
            return False

        return item_rg in groups


class RipFormatFilter(pluginlib.IterableFilter):
    __extension_name__ = 'ripformat'

    APPLIES_TO = models.Source
    HANDLES = ['rip-format']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.logger = logging.getLogger('kickass')

    def filter(self, key, value, item):
        if not isinstance(value, str):
            raise TypeError(value)

        if not value or not re.match(r'^[0-9a-z\-]+$', value, re.IGNORECASE):
            raise ValueError(value)

        itemformat = item.tag_dict.get(
            mediainfo.Tags.VIDEO_FORMAT, '')

        if not isinstance(itemformat, str):
            msg = "Item {item} has multiple formats ({formats}). Not supported"
            msg = msg.format(item=item, formats=repr(itemformat))
            self.logger.error(msg)
            return False

        return itemformat.lower() == value.lower()

__arroyo_extensions__ = [
    Container,
    CodecFilter,
    QualityFilter,
    ReleaseGroupFilter,
    RipFormatFilter
]
