# -*- coding: utf-8 -*-

from arroyo import plugin


class ImportCommand(plugin.Command):
    help = 'Import an origin.'

    arguments = (
        plugin.argument(
            '--backend',
            dest='backend',
            type=str,
            help='backend to use'),
        plugin.argument(
            '-u', '--url',
            dest='url',
            type=str,
            default=None,
            help='Seed URL'),
        plugin.argument(
            '-i', '--iterations',
            dest='iterations',
            type=int,
            help='iterations to run',
            default=1),
        plugin.argument(
            '-t', '--type',
            dest='type',
            type=str,
            help='force type of found sources'),
        plugin.argument(
            '-l', '--language',
            dest='language',
            type=str,
            help='force language of found sources'),
        plugin.argument(
            '--from-config',
            dest='from_config',
            action='store_true',
            default=False,
            help='Use origin definitions from configuration')
    )

    def run(self, arguments):
        if arguments.from_config and arguments.backend:
            msg = ("Only one of --from-config or --backend options can be "
                   "specified. They are mutually exclusive.")
            raise plugin.exc.PluginArgumentError(msg)

        if not arguments.from_config and not arguments.backend:
            msg = ("One of --from-config or --backend options must "
                   "be specified")
            raise plugin.exc.PluginArgumentError(msg)

        if arguments.backend:
            # d = dict(name='command-line')
            # d.update({k: getattr(arguments, k)
            #           for k in ['backend', 'url', 'iterations', 'type',
            #                     'language']})

            # spec = plugin.OriginSpec(**d)
            # self.app.importer.process_spec(spec)

            if self.app.settings.has_namespace_('origin'):
                self.app.settings.delete_('origin')

            # Rebuild origin
            keys = [
                ('backend', str),
                ('url', str),
                ('iterations', int),
                ('type', str),
                ('language', str)
            ]
            for (k, t) in keys:
                v = getattr(arguments, k, None)

                if v is not None:
                    try:
                        v = t(v)
                    except ValueError:
                        msg = 'Invalid argument {key}'
                        msg = msg.format(key=k)
                        self.app.logger.error(msg)
                        continue

                    self.app.settings.set_('origin.command-line.' + k, v)

            self.app.importer.run()

        elif arguments.from_config:
            self.app.importer.run()

        else:
            # This code should never be reached but keeping it here we will
            # prevent future mistakes
            msg = "Incorrect usage"
            raise plugin.exc.PluginArgumentError(msg)


__arroyo_extensions__ = [
    ('import', ImportCommand)
]
