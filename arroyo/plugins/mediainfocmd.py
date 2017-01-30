# -*- coding: utf-8 -*-

from arroyo import plugin
models = plugin.models


class MediainfoCommand(plugin.Command):
    __extension_name__ = 'mediainfo'

    HELP = 'guess mediainfo for sources.'
    ARGUMENTS = (
        plugin.cliargument(
            '-i', '--item',
            dest='item',
            help='run mediainfo process on selected item'
        ),
        plugin.cliargument(
            '-a', '--all',
            action='store_true',
            dest='all',
            help='run mediainfo process on all items'
        ),
    )

    def execute(self, args):
        item = args.item
        all_ = args.all

        test = sum([1 for x in [item, all_] if x])
        if test == 0:
            msg = "One of --item or --all options must be used"
            raise plugin.exc.ArgumentsError(msg)

        elif test > 1:
            msg = ("Only one of '--item' or '--all' options can be "
                   "specified. They are mutually exclusive.")
            raise plugin.exc.ArgumentsError(msg)

        if item:
            src = self.app.db.get(models.Source, id=item)
            if not src:
                msg = "No matching source with ID={id}"
                msg = msg.format(id=item)
                raise plugin.exc.ArgumentsError(msg)

            srcs = [src]

        elif all_:
            srcs = self.app.db.session.query(models.Source)

        self.app.mediainfo.process(*srcs)


__arroyo_extensions__ = [
    MediainfoCommand
]
