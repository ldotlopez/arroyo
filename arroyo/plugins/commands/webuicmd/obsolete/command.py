import os
from werkzeug.contrib.fixers import ProxyFix

from flask import redirect, url_for, g
from flask.ext.api import FlaskAPI

from arroyo import (
    exts
)

from . import blueprints


def create_app(api, **kwargs):
    app = FlaskAPI(__name__)

    with app.app_context():
        # app.config.update(**_config)
        app.register_blueprint(blueprints.search,
                               url_prefix='/api/search')

        # app.register_blueprint(blueprints.persons,
        #                        url_prefix='/api/persons')
        # app.register_blueprint(blueprints.sections,
        #                        url_prefix='/api/sections')
        # app.register_blueprint(blueprints.activities,
        #                        url_prefix='/api/activities')

    app.wsgi_app = ProxyFix(app.wsgi_app)
    app.static_folder = os.path.join(os.path.dirname(__file__), 'statics')
    app.route('/')(lambda: redirect(url_for('static', filename='index.html')))

    return app


class WebUICommand(exts.Command):
    help = 'WebUI'
    arguments = (
        exts.argument(
            '-i', '--interface',
            dest='host',
            default='127.0.0.1',
            help=('App host')
        ),
        exts.argument(
            '-p', '--port',
            dest='port',
            default=5000,
            help=('App port')
        )
    )

    def run(self):
        server = create_app(self)

        @server.before_request
        def before_request():
            g.app = self.app

        server.run(host=self.app.arguments.host,
                   port=self.app.arguments.port,
                   debug=True)
