from arroyo.app import app, argument


@app.register('command', 'test')
class Dummy:
    name = 'test'
    help = 'Nothing useful'

    arguments = (
        argument(
            '-a', '--foo',
            dest='foo',
            type=str,
            help='foo var'),
    )

    def run(self):
        print("Hi!")
