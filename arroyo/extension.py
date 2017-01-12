from appkit import application


class Extension(application.Extension):
    def __init__(self, app, *args, **kwargs):
        super().__init__()
        self.app = app
