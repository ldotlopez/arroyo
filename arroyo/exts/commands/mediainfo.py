from arroyo import (
    exc,
    exts,
    models
)


class MediainfoCommand(exts.Command):
    help = 'guess mediainfo for sources.'

    arguments = (
        exts.argument(
            '-i', '--item',
            dest='item',
            help='run mediainfo process on selected item'
        ),
        exts.argument(
            '-a', '--all',
            action='store_true',
            dest='all',
            help='run mediainfo process on all items'
        ),
    )

    def run(self):
        item = self.app.settings.get('command.item')
        all_ = self.app.settings.get('command.all')

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
