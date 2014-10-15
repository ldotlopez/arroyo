from arroyo.app import app
from arroyo.plugins import argument


class TestCmd:
    name = 'test'
    arguments = (
        argument(
            '-a', '--foo',
            dest='foo'
        ),
        argument(
            '-b', '--bar',
            dest='bar'
        )
    )

    def __init__(self):
        pass

app.register_command(TestCmd)
