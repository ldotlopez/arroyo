# -*- coding: utf-8 -*-

from arroyo import plugin


from . import webapp


class Command(plugin.Command):
    help = "Launch web interface"

    arguments = (
        plugin.argument(
            '-i', '--interface',
            dest='iface',
            default='127.0.0.1',
            help=('Interface to use (by default: 127.0.0.1)')
        ),
        plugin.argument(
            '-p', '--port',
            dest='port',
            default=5000,
            help=('Port to use (by default: 5000)')
        ),
        plugin.argument(
            '--debug',
            dest='debug',
            action='store_true',
            default=None,
            help=('Enable debug (by default: False)')
        )
    )

    def run(self, arguments):
        # Should we patch app's sqlalchemy session?
        # Session is located at self.app.db._sess
        # URL is at self.app.db._sess.connection().engine.url
        # Patch will add the check_same_thread=False parameter to the URL and
        # replace Arroyo.db._sess object

        p = {}

        p['host'] = arguments.iface or \
            self.app.settings.get('plugin.webui.interface',
                                  default='127.0.0.1')

        p['port'] = arguments.port or \
            self.app.settings.get('plugin.webui.port',
                                  default=5000)

        p['debug'] = arguments.debug
        if p['debug'] is None:
            p['debug'] = self.app.settings.get(
                'plugin.webui.debug',
                default=False)

        checks = {
            'host': str,
            'port': int,
            'debug': bool
        }
        for (k, typ) in checks.items():
            if not isinstance(p[k], typ):
                try:
                    iface = typ(p[k])
                except ValueError:
                    msg = "'{key}' must be a {type}"
                    msg = msg.format(key=k, type=str(typ.__name__))
                    raise plugin.exc.PluginArgumentError(msg)

        server = webapp.WebApp(self.app)
        server.run(**p)
