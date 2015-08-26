# -*- coding: utf-8 -*-

from arroyo import plugin
models = plugin.models


class MediainfoCommand(plugin.Command):
    help = 'guess mediainfo for sources.'

    arguments = (
        plugin.argument(
            '-i', '--item',
            dest='item',
            help='run mediainfo process on selected item'
        ),
        plugin.argument(
            '-a', '--all',
            action='store_true',
            dest='all',
            help='run mediainfo process on all items'
        ),
    )

    def run(self, args):
        item = args.item
        all_ = args.all

        if not any([item, all_]):
            msg = 'One of item or all options must be used'
            raise plugin.ArgumentError(msg)

        if item:
            srcs = [self.app.db.get(models.Source, id=item)]
        else:
            srcs = self.app.db.session.query(models.Source)

        self.app.mediainfo.process(*srcs)


__arroyo_extensions__ = [
    ('mediainfo', MediainfoCommand)
]
