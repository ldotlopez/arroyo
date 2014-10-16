class ArgumentError(Exception):
    def __init__(self, msg, *args, tip=True, **kwargs):
        if not msg.endswith('.'):
            msg += "."
        msg += " Try -h/--help switch for more information"
        super(ArgumentError, self).__init__(msg, *args, **kwargs)


class SourceNotFound(Exception):
    pass


class ReadOnlyProperty(Exception):
    pass