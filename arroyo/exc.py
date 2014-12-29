class SourceNotFound(Exception):
    pass


class ReadOnlyProperty(Exception):
    pass


class InvalidInstanceType(Exception):
    pass


class InvalidBackend(Exception):
    pass


class ArgumentError(Exception):
    def __init__(self, msg, *args, tip=True, **kwargs):
        if not msg.endswith('.'):
            msg += "."
        msg += " Try -h/--help switch for more information"
        super(ArgumentError, self).__init__(msg, *args, **kwargs)


class NoImplementationError(Exception):
    def __init__(self, extension_point, name):
        msg = "No such implementation {name} for {extension_point}"
        msg = msg.format(name=name, extension_point=extension_point)
        super(NoImplementationError, self).__init__(msg)


class UrlGeneratorException(Exception):
    pass


class ProcessException(Exception):
    pass


class NoMatchingState(Exception):

    def __init__(self, state, *args, **kwargs):
        self.state = state
        super(NoMatchingState, self).__init__(*args, **kwargs)


class NoMatchingItem(Exception):

    def __init__(self, item, *args, **kwargs):
        self.item = item
        super(NoMatchingItem, self).__init__(*args, **kwargs)


class BackendError(Exception):

    def __init__(self, e, *args, **kwargs):
        self.exception = e
        super(BackendError, self).__init__(*args, **kwargs)
