from appkit import app


class Extension(app.Extension):
    def __init__(self, app):
        self.app = app


class Command(app.Command, Extension):
    def __init__(self, application, *args, **kwargs):
        app.Command.__init__(self, *args, **kwargs)
        Extension.__init__(self, application)
