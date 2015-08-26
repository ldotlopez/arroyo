from ldotcommons import utils

from arroyo import plugin


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
        if arguments.list:
            impls = self.app.get_implementations(plugin.CronTask)

            for (name, impl) in sorted(impls.items(), key=lambda x: x[0]):
                msg = "{name} – interval: {interval} ({secs} seconds)"
                msg = msg.format(
                    name=name,
                    interval=impl.INTERVAL,
                    secs=utils.parse_interval(impl.INTERVAL))

                print(msg)

            return

        if arguments.all:
            self.app.cron.run_all(force=arguments.force)
            return

        if arguments.tasks:
            for name in arguments.tasks:
                self.app.cron.run(name, arguments.force)


__arroyo_extensions__ = [
    ('cron', CronCommand),
]
