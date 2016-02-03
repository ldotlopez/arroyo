# -*- coding: utf-8 -*-


class SettingError(Exception):
    def __init__(self, key, value, original=None):
        msg = "Invalid setting '{key}': '{value}'"
        msg = msg.format(key=key, value=value)
        super().__init__(msg)

        self.key = key
        self.value = value
        self.original = original


class PluginArgumentError(Exception):
    pass


class NetworkError(IOError):
    def __init__(self, msg, e=None, *args, **kwargs):
        self.msg = msg
        self.e = e
        self.args = args
        self.kwargs = kwargs

    def __str__(self):
        return self.__unicode__()

    def __unicode__(self):
        return self.msg


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
