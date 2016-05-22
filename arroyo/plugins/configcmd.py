# -*- coding: utf-8 -*-

from arroyo import plugin
import yaml


class ConfigCommand(plugin.Command):
    help = 'Configuration management'

    @classmethod
    def setup_argparser(cls, cmdargparser):
        super()

        cls.opparser = cmdargparser.add_subparsers(dest='operation')

        cls.setparser = cls.opparser.add_parser('set')
        cls.setparser.add_argument('-t', '--type', dest='type')
        cls.setparser.add_argument('key', nargs=1)
        cls.setparser.add_argument('value', nargs=1)

        cls.getparser = cls.opparser.add_parser('get')
        cls.getparser.add_argument('key', nargs=1)

        cls.delparser = cls.opparser.add_parser('delete')
        cls.delparser.add_argument('key', nargs=1)

        cls.dumpparser = cls.opparser.add_parser('dump')

    def run(self, args):
        types_map = {
            None: yaml.load,
            'int': int,
            'bool': bool,
            'str': str,
            'float': float,
            'dict': yaml.load,
            'list': yaml.load
        }

        if args.operation == 'dump':
            print(yaml.dump(self.app.settings.get(None)))

        elif args.operation == 'set':
            if args.type not in types_map:
                msg = "Unknow type '{type}'"
                msg = msg.format(type=args.type)
                self.app.logger.error(msg)
                return

            self.app.settings.set(
                args.key[0],
                types_map[args.type](args.value[0]))

            cfgfile = vars(args)['config-files'][-1]
            with open(cfgfile, 'w') as fh:
                self.app.settings.write(fh)

        elif args.operation == 'get':
            print(yaml.dump(self.app.settings.get(args.key[0])))

__arroyo_extensions__ = [
    ('config', ConfigCommand)
]
