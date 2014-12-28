from arroyo.app import app, argument
from arroyo import models
import arroyo.exc


@app.register('command', 'mediainfo')
class Mediainfo:
    help = 'Guess mediainfo from sources'
    arguments = (
        argument(
            '-i', '--item',
            dest='item',
            help='Run mediainfo process on selected item'
        ),
        argument(
            '-a', '--all',
            action='store_true',
            dest='all',
            help='Run mediainfo process on all items'
        ),
    )

    def run(self):
        item = app.arguments.item
        all_ = app.arguments.all

        if not any([item, all_]):
            msg = 'One of item or all options must be used'
            raise arroyo.exc.ArgumentError(msg)

        if item:
            srcs = [app.db.get(models.Source, id=item)]
        else:
            srcs = app.db.session.query(models.Source)

        app.mediainfo.process(*srcs)
