class CronManager:
    def __init__(self, app):
        self._app = app

    def run_all(self, force=False):
        for impl in self._app.get_implementations('crontask'):
            self.run(impl, force)

    def run(self, name, force=False):
        task = self._app.get_extension('crontask', name)

        if force or task.should_run:
            task.run()
