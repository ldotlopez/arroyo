# -*- coding: utf-8 -*-

import os


from flask import redirect, url_for, g
from flask.ext.api import FlaskAPI
# from werkzeug.contrib.fixers import ProxyFix


from . import blueprints


class WebApp(FlaskAPI):
    def __init__(self, app):
        super().__init__(__name__)

        self.static_folder = os.path.join(os.path.dirname(__file__), 'statics')
        self.route('/')(
            lambda: redirect(url_for('static', filename='webui/index.html'))
        )
        self.register_blueprint(blueprints.search,
                                url_prefix='/api/search/')
        self.register_blueprint(blueprints.settings,
                                url_prefix='/api/settings/')

        @self.before_request
        def before_request():
            g.app = app

        # @server.after_request
        # def shutdown_session(response):
        #     g.app.db.remove()
        #     return response

        # self.wsgi_app = ProxyFix(self.wsgi_app)
