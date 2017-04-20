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


from appkit import application


class _BaseException(Exception):
    def __init__(self, msg, **kwargs):
        super().__init__(msg)
        for (k, v) in kwargs.items():
            setattr(self, k, v)


class SettingError(_BaseException):
    def __init__(self, key, value, original=None):
        msg = "Invalid setting '{key}': '{value}'"
        msg = msg.format(key=key, value=value)

        super().__init__(msg, key=key, value=value, original=original)


# Origin related
class OriginParseError(_BaseException):
    pass


class SourceResolveError(_BaseException):
    pass


class ArgumentsError(application.ArgumentsError, _BaseException):
    pass


# Other

class FatalError(_BaseException):
    """
    Used to stop arroyo
    """
    pass


#
# The following exceptions aren't reviewed
#


class NoMatchingState(Exception):
    pass


class NoMatchingItem(Exception):
    pass


class BackendError(Exception):
    def __init__(self, message, original=None):
        self.message = message
        self.original = original
        super().__init__(message)

    def __unicode__(self):
        return self.message

    def __str__(self):
        return self.__unicode__()


class SourceNotFound(Exception):
    pass


class ReadOnlyProperty(Exception):
    pass


class InvalidInstanceType(Exception):
    pass


class InvalidBackend(Exception):
    pass


class UrlGeneratorException(Exception):
    pass


class ProcessException(Exception):
    def __init__(self, *args, **kwargs):
        super(ProcessException, self).__init__()
        self.args = args
        self.kwargs = kwargs


class NoImplementationError(Exception):
    def __init__(self, extension_point, name):
        msg = "No such implementation {name} for {extension_point}"
        msg = msg.format(name=name, extension_point=extension_point)
        super(NoImplementationError, self).__init__(msg)
