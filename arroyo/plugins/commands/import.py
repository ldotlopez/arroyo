# -*- coding: utf-8 -*-


from arroyo import pluginlib


class ImportCommand(pluginlib.Command):
    __extension_name__ = 'import'

    HELP = 'Import an origin.'
    ARGUMENTS = (
        pluginlib.cliargument(
            '--provider',
            dest='provider',
            type=str,
            help='provider to use'),
        pluginlib.cliargument(
            '-u', '--uri',
            dest='uri',
            type=str,
            default=None,
            help='Seed URI'),
        pluginlib.cliargument(
            '-i', '--iterations',
            dest='iterations',
            type=int,
            help='iterations to run',
            default=1),
        pluginlib.cliargument(
            '-t', '--type',
            dest='type',
            type=str,
            help='force type of found sources'),
        pluginlib.cliargument(
            '-l', '--language',
            dest='language',
            type=str,
            help='force language of found sources'),
        pluginlib.cliargument(
            '--from-config',
            dest='from_config',
            action='store_true',
            default=False,
            help='Use origin definitions from configuration')
    )

    def execute(self, arguments):
        if arguments.from_config and arguments.provider:
            msg = ("Only one of --from-config or --provider options can be "
                   "specified. They are mutually exclusive.")
            raise pluginlib.exc.ArgumentsError(msg)

        if arguments.provider or arguments.uri:
            # Build origin data
            keys = [
                ('provider', str),
                ('uri', str),
                ('iterations', int),
                ('type', str),
                ('language', str)
            ]

            origin_data = dict(display_name='command line')
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

                    origin_data[k] = v

            origin = self.app.importer.origin_from_params(**origin_data)
            self.app.importer.process(origin)

        elif arguments.from_config:
            self.app.importer.run()

        else:
            # This code should never be reached but keeping it here we will
            # prevent future mistakes
            msg = "Incorrect usage"
            raise pluginlib.exc.ArgumentsError(msg)


__arroyo_extensions__ = [
    ImportCommand
]
