# -*- coding: utf-8 -*-

from arroyo import pluginlib


from appkit import utils


class CronCommand(pluginlib.Command):
    __extension_name__ = 'cron'

    HELP = 'Run cron tasks'
    ARGUMENTS = (
        pluginlib.cliargument(
            '-a', '--all',
            dest='all',
            action='store_true',
            default=[],
            help=('Run all tasks')
        ),
        pluginlib.cliargument(
            '-t', '--task',
            dest='tasks',
            action='append',
            default=[],
            help=('Run specifics task')
        ),
        pluginlib.cliargument(
            '-f', '--force',
            dest='force',
            action='store_true',
            help=('Force tasks to run omiting intervals')
        ),
        pluginlib.cliargument(
            '-l', '--list',
            dest='list',
            action='store_true',
            help=('Show registered tasks')
        ),
    )

    def execute(self, arguments):
        list_ = arguments.list
        all_ = arguments.all
        tasks = arguments.tasks
        force = arguments.force

        test = sum([1 for x in [list_, all_, tasks] if x])

        if test == 0:
            msg = ("One of '--list', '--all' or '--task' options must be "
                   "specified")
            raise pluginlib.exc.ArgumentsError(msg)

        if test > 1:
            msg = ("Only one of '--list', '--all' and '--task' options can be "
                   "specified. They are mutually exclusive.")
            raise pluginlib.exc.ArgumentsError(msg)

        if list_:
            g = sorted(self.app.get_extensions_for(plugin.Task))
            for (name, ext) in g:
                msg = "{name} – interval: {interval} ({secs} seconds)"
                msg = msg.format(
                    name=name,
                    interval=ext.human_interval,
                    secs=ext.INTERVAL)

                print(msg)

        elif all_:
            self.app.cron.execute_all(force=force)

        elif tasks:
            for name in tasks:
                self.app.cron.execute(self.app.cron.get_task(name),
                                      force=force)

        else:
            # This code should never be reached but keeping it here we will
            # prevent future mistakes
            msg = "Incorrect usage"
            raise pluginlib.exc.ArgumentsError(msg)

__arroyo_extensions__ = [
    CronCommand
]
