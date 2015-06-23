class CronManager:
    def __init__(self, app):
        self._app = app

    def run_all_tasks(self):
        for impl in self._app.get_implementations('crontask'):
            self.run_task(impl)

    def run_task(self, task_name, force=False):
        task = self._app.get_extension('crontask', task_name)

        if force or task.should_run:
            task.run()
