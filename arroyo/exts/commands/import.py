from arroyo import (
    importer,
    exc,
    exts
)


class ImportCron(exts.Cron):
    interval = '1h'

    def run(self):
        print("hi!")


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

    def run(self):
        backend = self.app.arguments.backend
        seed_url = self.app.arguments.url
        iterations = self.app.arguments.iterations
        typ = self.app.arguments.type
        language = self.app.arguments.language

        if backend and isinstance(backend, str):
            if not isinstance(seed_url, (str, type(None))):
                raise exc.ArgumentError(
                    'seed_url must be an string or None')

            if not isinstance(iterations, int) or iterations < 1:
                raise exc.ArgumentError(
                    'iterations must be an integer greater than 1')

            if not isinstance(typ, (str, type(None))):
                raise exc.ArgumentError(
                    'type must be an string or None')

            if not isinstance(language, (str, type(None))):
                raise exc.ArgumentError(
                    'languge must be an string or None')

            origin_defs = [importer.OriginDefinition(
                name='Command line',
                backend=backend,
                url=seed_url,
                iterations=int(iterations),
                type=typ,
                language=language)]

        else:
            origin_defs = self.app.importer.get_origin_defs()

        for origin_def in origin_defs:
            try:
                self.app.importer.import_origin(origin_def)
            except exc.NoImplementationError as e:
                msg = "Invalid origin {name}: {msg}"
                msg = msg.format(name=origin_def.name, msg=str(e))
                print(msg)


__arroyo_extensions__ = [
    ('command', 'import', ImportCommand),
    ('cron', 'import', ImportCron)
]
