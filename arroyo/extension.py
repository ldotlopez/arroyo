from appkit import app


class Extension(app.Extension):
    def __init__(self, app, *args, **kwargs):
        super().__init__()
        self.app = app


class Command(app.Command, Extension):
    pass
