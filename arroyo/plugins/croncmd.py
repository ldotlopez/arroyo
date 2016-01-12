# -*- coding: utf-8 -*-

from arroyo import plugin


from ldotcommons import utils


class CronCommand(plugin.Command):
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
        _list = arguments.list
        _all = arguments.all
        tasks = arguments.tasks

        test = sum([1 for x in [_list, _all, tasks] if x])

        if test == 0:
            msg = ("Al least one of '--list', '--all' or '--task' options "
                   "must be specified")
            raise plugin.exc.PluginArgumentError(msg)

        if test > 1:
            msg = ("Only one of '--list', '--all' and '--task' options must "
                   "be specified")
            raise plugin.exc.PluginArgumentError(msg)

        if arguments.list:
            impls = self.app.get_implementations(plugin.CronTask)

            for (name, impl) in sorted(impls.items(), key=lambda x: x[0]):
                msg = "{name} – interval: {interval} ({secs} seconds)"
                msg = msg.format(
                    name=name,
                    interval=impl.INTERVAL,
                    secs=utils.parse_interval(impl.INTERVAL))

                print(msg)

        elif arguments.all:
            self.app.cron.run_all(force=arguments.force)

        elif arguments.tasks:
            for name in arguments.tasks:
                self.app.cron.run(name, arguments.force)

        msg = "Incorrect usage"
        raise plugin.exc.PluginArgumentError(msg)

__arroyo_extensions__ = [
    ('cron', CronCommand),
]
