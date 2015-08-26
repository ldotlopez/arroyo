# -*- coding: utf-8 -*-

from arroyo import plugin


class ImportCommand(plugin.Command):
    help = 'Import an origin.'

    arguments = (
        plugin.argument(
            '--backend',
            dest='backend',
            type=str,
            help='backend to use'),
        plugin.argument(
            '-u', '--url',
            dest='url',
            type=str,
            default=None,
            help='Seed URL'),
        plugin.argument(
            '-i', '--iterations',
            dest='iterations',
            type=int,
            help='iterations to run',
            default=1),
        plugin.argument(
            '-t', '--type',
            dest='type',
            type=str,
            help='force type of found sources'),
        plugin.argument(
            '-l', '--language',
            dest='language',
            type=str,
            help='force language of found sources'),
        plugin.argument(
            '--origins',
            dest='from_origins',
            type=bool,
            default=False,
            help='Use origin definitions')
    )

    def run(self, arguments):
        if arguments.from_origins and arguments.backend:
            msg = ("--origins and --backend options are "
                   "mutually exclusive")
            raise plugin.exc.ArgumentError(msg)

        if arguments.backend:
            # Delete previous origins
            if self.app.settings.has_namespace('origin'):
                self.app.settings.delete('origin')

            # Rebuild origin
            keys = 'backend url iterations type language'.split(' ')
            for k in keys:
                self.app.settings.set(
                    'origin.command-line.' + k,
                    getattr(arguments, k))

        self.app.importer.run()


__arroyo_extensions__ = [
    ('import', ImportCommand)
]
