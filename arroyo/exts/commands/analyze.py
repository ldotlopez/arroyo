from arroyo import (
    analyzer,
    exc,
    exts
)


class AnalyzeCommand(exts.Command):
    help = 'Analyze an origin merging discovered sources into the database'

    arguments = (
        exts.argument(
            '--importer',
            dest='importer',
            type=str,
            help='importer to use'),
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
        importer = self.app.arguments.importer
        seed_url = self.app.arguments.url
        iterations = self.app.arguments.iterations
        typ = self.app.arguments.type
        language = self.app.arguments.language

        if importer and isinstance(importer, str):
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

            origins = [analyzer.Origin(
                name='Command line',
                importer=importer,
                url=seed_url,
                iterations=int(iterations),
                type=typ,
                language=language)]

        else:
            origins = self.app.analyzer.get_origins()

        for origin in origins:
            try:
                self.app.analyzer.analyze(origin)
            except exc.NoImplementationError as e:
                msg = "Invalid origin {name}: {msg}"
                msg = msg.format(name=origin.name, msg=str(e))
                print(msg)


__arroyo_extensions__ = [
    ('command', 'analyze', AnalyzeCommand)
]
