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


# Reviewed with git grep

# Other

class FatalError(Exception):
    """
    Used to stop arroyo
    """
    pass


class SelfCheckError(Exception):
    """Assert-like error"""
    pass


class PluginError(Exception):
    """Delegated plugin had unexpected error"""
    def __init__(self, msg, original_exception=None):
        super().__init__(msg)
        self.msg = msg
        self.original_exception = original_exception

    def __unicode__(self):
        return self.msg

    __str__ = __unicode__


# /End reviewd exceptions


class ArgumentsError(Exception):
    pass


class ConfigurationError(Exception):
    pass


class SettingError(ValueError):
    MSG = "Invalid setting for '{key}': '{value}'"

    def __init__(self, key, value):
        super().__init__(
            self.MSG.format(key=key, value=repr(value))
        )

        self.key = key
        self.value = value
