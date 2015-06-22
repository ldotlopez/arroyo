from arroyo import exts


class ImportCommand(exts.Command):
    help = 'Import an origin.'

    arguments = (
        exts.argument(
            '--backend',
            dest='backend',
            type=str,
            help='backend to use'),
        exts.argument(
            '-u', '--url',
            dest='url',
            type=str,
            default=None,
            help='Seed URL'),
        exts.argument(
            '-i', '--iterations',
            dest='iterations',
            type=int,
            help='iterations to run',
            default=1),
        exts.argument(
            '-t', '--type',
            dest='type',
            type=str,
            help='force type of found sources'),
        exts.argument(
            '-l', '--language',
            dest='language',
            type=str,
            help='force language of found sources')
    )

    def run(self, args):
        if args.backend:
            if self.app.settings.has_namespace('origin'):
                self.app.settings.delete('origin')

            keys = 'backend url iterations type language'.split(' ')
            for k in keys:
                self.app.settings.set(
                    'origin.command-line.' + k,
                    getattr(args, k))

        self.app.importer.execute()

__arroyo_extensions__ = [
    ('command', 'import', ImportCommand)
]
