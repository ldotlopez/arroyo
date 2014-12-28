from arroyo.app import app, argument
from arroyo import analyzer

import arroyo.exc


@app.register('command', 'analyze')
class AnalyzeCommand:
    help = 'Analyze an origin merging discovered sources into the database'

    arguments = (
        argument(
            '--importer',
            dest='importer',
            type=str,
            help='importer to use'),
        argument(
            '-u', '--url',
            dest='url',
            type=str,
            default=None,
            help='Seed URL'),
        argument(
            '-i', '--iterations',
            dest='iterations',
            type=int,
            help='iterations to run',
            default=1),
        argument(
            '-t', '--type',
            dest='type',
            type=str,
            help='force type of found sources'),
        argument(
            '-l', '--language',
            dest='language',
            type=str,
            help='force language of found sources')
    )

    def run(self):
        importer = app.arguments.importer
        seed_url = app.arguments.url
        iterations = app.arguments.iterations
        typ = app.arguments.type
        language = app.arguments.language

        if importer and isinstance(importer, str):
            if not isinstance(seed_url, (str, type(None))):
                raise arroyo.exc.ArgumentError(
                    'seed_url must be an string or None')

            if not isinstance(iterations, int) or iterations < 1:
                raise arroyo.exc.ArgumentError(
                    'iterations must be an integer greater than 1')

            if not isinstance(typ, (str, type(None))):
                raise arroyo.exc.ArgumentError(
                    'type must be an string or None')

            if not isinstance(language, (str, type(None))):
                raise arroyo.exc.ArgumentError(
                    'languge must be an string or None')

            origins = [analyzer.Origin(
                name='Command line',
                importer=importer,
                url=seed_url,
                iterations=int(iterations),
                type=typ,
                language=language)]

        else:
            origins = app.analyzer.get_origins()

        for origin in origins:
            try:
                app.analyzer.analyze(origin)
            except arroyo.exc.NoImplementationError:
                print("Invalid origin {name}".format(name=origin.name))
