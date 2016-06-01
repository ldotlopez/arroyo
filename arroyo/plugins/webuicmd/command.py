# -*- coding: utf-8 -*-

from arroyo import plugin


from . import webapp


class Command(plugin.Command):
    arguments = (
        plugin.argument(
            '-i', '--interface',
            dest='interface',
            default=None,
            help=('Interface to use (by default 127.0.0.1)')
        ),
        plugin.argument(
            '-p', '--port',
            dest='port',
            default=None,
            help=('Port to use (by default 5000)')
        ),
        plugin.argument(
            '--debug',
            dest='debug',
            action='store_true',
            default=None,
            help=('Enable debug (disabled by default)')
        )
    )

    def run(self, arguments):
        # Should we patch app's sqlalchemy session?
        # Session is located at self.app.db._sess
        # URL is at self.app.db._sess.connection().engine.url
        # Patch will add the check_same_thread=False parameter to the URL and
        # replace Arroyo.db._sess object

        p = {}

        p['host'] = \
            arguments.interface or \
            self.app.settings.get('plugin.webui.interface') or \
            '0.0.0.0'

        p['port'] = \
            arguments.port or \
            self.app.settings.get('plugin.webui.port') or \
            5000

        p['debug'] = arguments.debug
        if p['debug'] is None:
            p['debug'] = \
                self.app.settings.get('plugin.webui.debug', default=False)

        checks = {
            'host': str,
            'port': int,
            'debug': bool,
        }

        for (k, typ) in checks.items():
            if not isinstance(p[k], typ):
                try:
                    p[k] = typ(p[k])
                except ValueError:
                    msg = "Invalid '{key}' parameter, must be a {type}"
                    msg = msg.format(key=k, type=typ.__name__)
                    raise plugin.exc.ArgumentError(msg)

        self.app.settings.set('auto-import', False)
        self.app.settings.set('auto-cron', False)
        server = webapp.WebApp(self.app)
        server.run(**p)
