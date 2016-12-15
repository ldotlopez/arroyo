# -*- coding: utf-8 -*-

from ldotcommons import utils


from appkit import app


class CronManager:
    def __init__(self, app):
        self._app = app
        self._app.register_extension_point(CronTask)

    def run_all(self, force=False):
        for impl in self._app.get_implementations(CronTask):
            self.run(impl, force)

    def run(self, name, force=False):
        task = self._app.get_extension(CronTask, name)

        if force or task.should_run:
            task.run()


class CronTask(app.Extension):
    def __init__(self, app):
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

        if not hasattr(self, 'NAME') or \
           not isinstance(self.NAME, str) or \
           self.NAME == "":
            msg = "{class_name} doesn't have a valid NAME attribute"
            msg = msg.format(class_name=self.__class__.__name__)
            raise TypeError(msg)

        super().__init__(app)

        self.name = self.__class__.__name__.lower()
        self.app = app
        self.keys = {
            'registered': 'crontask.%s.registered' % self.NAME,
            'last-run': 'crontask.%s.last-run' % self.NAME
        }

    @property
    def last_run(self):
        return self.app.variables.get(self.keys['last-run'], 0)

    @property
    def should_run(self):
        return utils.now_timestamp() - self.last_run >= self.INTERVAL

    def run(self):
        self.app.variables.set(
            self.keys['last-run'],
            utils.now_timestamp())
