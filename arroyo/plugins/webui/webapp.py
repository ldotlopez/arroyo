# -*- coding: utf-8 -*-

import os


from flask import redirect, url_for
from flask.ext.api import FlaskAPI
# from werkzeug.contrib.fixers import ProxyFix


from . import blueprints


class WebApp(FlaskAPI):
    def __init__(self):
        super().__init__(__name__)

        self.static_folder = os.path.join(os.path.dirname(__file__), 'statics')
        self.route('/')(
            lambda: redirect(url_for('static', filename='index.html'))
        )
        self.register_blueprint(blueprints.search,
                                url_prefix='/api/search')

        # self.wsgi_app = ProxyFix(self.wsgi_app)
