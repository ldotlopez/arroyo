# -*- coding: utf-8 -*-

from arroyo import plugin


from appkit import utils


class CronCommand(plugin.Command):
    __extension_name__ = 'cron-command'

    help = 'Run cron tasks'

    arguments = (
        plugin.argument(
            '-a', '--all',
            dest='all',
            action='store_true',
            default=[],
            help=('Run all tasks')
        ),
        plugin.argument(
            '-t', '--task',
            dest='tasks',
            action='append',
            default=[],
            help=('Run specifics task')
        ),
        plugin.argument(
            '-f', '--force',
            dest='force',
            action='store_true',
            help=('Force tasks to run omiting intervals')
        ),
        plugin.argument(
            '-l', '--list',
            dest='list',
            action='store_true',
            help=('Show registered tasks')
        ),
    )

    def run(self, arguments):
        list_ = arguments.list
        all_ = arguments.all
        tasks = arguments.tasks
        force = arguments.force

        test = sum([1 for x in [list_, all_, tasks] if x])

        if test == 0:
            msg = ("One of '--list', '--all' or '--task' options must be "
                   "specified")
            raise plugin.exc.PluginArgumentError(msg)

        if test > 1:
            msg = ("Only one of '--list', '--all' and '--task' options can be "
                   "specified. They are mutually exclusive.")
            raise plugin.exc.PluginArgumentError(msg)

        if list_:
            impls = self.app.get_implementations(plugin.CronTask)

            for (name, impl) in sorted(impls.items(), key=lambda x: x[0]):
                msg = "{name} – interval: {interval} ({secs} seconds)"
                msg = msg.format(
                    name=name,
                    interval=impl.INTERVAL,
                    secs=utils.parse_interval(impl.INTERVAL))

                print(msg)

        elif all_:
            self.app.cron.run_all(force=force)

        elif tasks:
            for name in tasks:
                self.app.cron.run(name, force)

        else:
            # This code should never be reached but keeping it here we will
            # prevent future mistakes
            msg = "Incorrect usage"
            raise plugin.exc.PluginArgumentError(msg)

__arroyo_extensions__ = [
    CronCommand
]
