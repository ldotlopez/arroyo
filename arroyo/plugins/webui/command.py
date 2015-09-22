from arroyo import plugin

from flask import g
from . import webapp


class Command(plugin.Command):
    arguments = (
        plugin.argument(
            '-i', '--interface',
            dest='host',
            default='127.0.0.1',
            help=('App host')
        ),
        plugin.argument(
            '-p', '--port',
            dest='port',
            default=5000,
            help=('App port')
        ),
        plugin.argument(
            '--debug',
            dest='debug',
            default=False,
            help=('Enabled debug')
        )
    )

    def run(self, arguments):
        # Should we patch app's sqlalchemy session?
        # Session is located at self.app.db._sess
        # URL is at self.app.db._sess.connection().engine.url
        # Patch will add the check_same_thread=False parameter to the URL and
        # replace Arroyo.db._sess object

        server = webapp.WebApp()

        @server.before_request
        def before_request():
            g.app = self.app

        # @server.after_request
        # def shutdown_session(response):
        #     g.app.db.remove()
        #     return response

        server.run(host=arguments.host,
                   port=arguments.port,
                   debug=arguments.debug)
