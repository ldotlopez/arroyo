from arroyo.app import app
from arroyo.plugins import argument


class AnalizeCommand:
    name = 'analize'
    help = 'Analize origins'
    arguments = (
        argument(
            '-a', '--analizer',
            dest='analizer_name',
            type=str,
            help='analizer to run'),
        argument(
            '-u', '--url',
            dest='seed_url',
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

    def run(*args, **kwargs):
        print("Run analisys")


app.register_command(AnalizeCommand)
