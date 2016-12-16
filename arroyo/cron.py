# -*- coding: utf-8 -*-

from arroyo import extension
from appkit import utils


class CronManager:
    def __init__(self, app):
        self._app = app
        self._app.register_extension_point(CronTask)

    def run_all(self, force=False):
        for name in self._app.get_implementations(CronTask):
            self.run_by_name(name, force)

    def run(self, task, force=False):
        if force or task.should_run():
            task.run()

    def run_by_name(self, name, force=False):
        task = self._app.get_extension(CronTask, name)
        self.run(task, force)


class CronTask(extension.Extension):
    def __init__(self, app, *args, **kwargs):
        if not hasattr(self, 'INTERVAL'):
            msg = "{class_name} doesn't have a valid INTERVAL attribute"
            msg = msg.format(class_name=self.__class__.__name__)
            raise TypeError(msg)

        try:
            self.INTERVAL = utils.parse_interval(self.INTERVAL)
        except ValueError as e:
            msg = "Invalid interval value '{interval}', check docs"
            msg = msg.format(interval=self.INTERVAL)
            raise TypeError(msg) from e

        super().__init__(app, *args, **kwargs)

        self.name = self.__class__.__extension_name__.lower()
        self.app = app
        self.keys = {
            'registered': 'crontask.{name}.registered'.format(name=self.name),
            'last-run': 'crontask.{name}.last-run'.format(name=self.name)
        }

    @property
    def last_run(self):
        return self.app.variables.get(self.keys['last-run'], 0)

    def should_run(self):
        return utils.now_timestamp() - self.last_run >= self.INTERVAL

    def run(self):
        self.app.variables.set(
            self.keys['last-run'],
            utils.now_timestamp())
