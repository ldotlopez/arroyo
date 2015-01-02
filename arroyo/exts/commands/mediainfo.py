from arroyo import (
    exc,
    exts,
    models
)


class MediainfoCommand(exts.Command):
    help = 'Guess mediainfo from sources'
    arguments = (
        exts.argument(
            '-i', '--item',
            dest='item',
            help='Run mediainfo process on selected item'
        ),
        exts.argument(
            '-a', '--all',
            action='store_true',
            dest='all',
            help='Run mediainfo process on all items'
        ),
    )

    def run(self):
        item = self.app.arguments.item
        all_ = self.app.arguments.all

        if not any([item, all_]):
            msg = 'One of item or all options must be used'
            raise exc.ArgumentError(msg)

        if item:
            srcs = [self.app.db.get(models.Source, id=item)]
        else:
            srcs = self.app.db.session.query(models.Source)

        self.app.mediainfo.process(*srcs)


__arroyo_extensions__ = [
    ('command', 'mediainfo', MediainfoCommand)
]
