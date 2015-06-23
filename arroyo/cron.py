from ldotcommons import utils

from arroyo import exts


class CronManager:
    def __init__(self, app):
        self._app = app

    def run(self):
        for impl in self._app.get_implementations('crontask'):
            self.run_task(impl)

    @staticmethod
    def _get_task_keys(task):
        return utils.InmutableDict({
            'last-run': 'crontask.%s.last-run' %
                        task.__class__.__name__.lower()
            })

    def needs_run(self, task):
        if not isinstance(task, exts.CronTask):
            msg = 'task is not a CronTask'
            raise TypeError(msg)

        keys = self._get_task_keys(task)
        last_run = self._app.variables.get(keys['last-run'], -1)
        return utils.now_timestamp() - last_run >= task.INTERVAL

    def run_task(self, task_name, force=False):
        task = self._app.get_extension('crontask', task_name)

        if force or self.needs_run(task):
            task.run()
            keys = self._get_task_keys(task)
            self._app.variables.set(keys['last-run'], utils.now_timestamp())
