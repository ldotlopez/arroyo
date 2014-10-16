class ArgumentError(Exception):
    def __init__(self, msg, *args, tip=True, **kwargs):
        if not msg.endswith('.'):
            msg += "."
        msg += " Try -h/--help switch for more information"
        super(ArgumentError, self).__init__(msg, *args, **kwargs)

def argument(*args, **kwargs):
    """argparse argument wrapper to ease the command argument definitions"""
    def wrapped_arguments():
        return args, kwargs

    return wrapped_arguments
