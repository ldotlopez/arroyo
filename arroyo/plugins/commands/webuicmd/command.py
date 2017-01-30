# -*- coding: utf-8 -*-

from arroyo import pluginlib


from . import webapp


class Command(pluginlib.Command):
    arguments = (
        pluginlib.cliargument(
            '-i', '--interface',
            dest='host',
            default='127.0.0.1',
            help=('App host')
        ),
        pluginlib.cliargument(
            '-p', '--port',
            dest='port',
            default=5000,
            help=('App port')
        ),
        pluginlib.cliargument(
            '--debug',
            dest='debug',
            action='store_true',
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

        server = webapp.WebApp(self.app)
        server.run(host=arguments.host,
                   port=arguments.port,
                   debug=arguments.debug)
