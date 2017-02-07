# -*- coding: utf-8 -*-

from arroyo import pluginlib


from appkit.application import cron


class Command(cron.Command, pluginlib.Command):
    def execute(self, arguments):
        """
        Override execute method.

        Signatures:
        pluginlib.Command.execute(arguments)
        appkit.cron.Command.execute(application, arguments)

        We need to pass correct arguments to base class in order to adapt it to
        our application model
        """
        return super().execute(self.app, arguments)

__arroyo_extensions__ = [
    Command
]
