from ldotcommons import utils

from arroyo import exts


class CronCommand(exts.Command):
    help = 'Run cron tasks'

    arguments = (
        exts.argument(
            '--action',
            dest='actions',
            action='append',
            default=[],
            help=('Run specific action')
        ),
    )

    def run(self):
        impls = self.app.get_implementations('cron')

        actions = self.app.arguments.actions
        if not actions:
            actions = list(impls.keys())

        impls = dict(filter(lambda x: x[0] in actions, impls.items()))
        # print(actions)

        # now = utils.utcnow_timestamp()
        for (action, impl) in impls.items():
            # print(action, impl.interval)
            action = self.app.get_extension('cron', action)
            action.run()

__arroyo_extensions__ = (
    ('command', 'cron', CronCommand),
)
