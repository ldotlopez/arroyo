# -*- coding: utf-8 -*-

import os


from flask import redirect, url_for, g, send_from_directory
from flask.ext.api import FlaskAPI
# from werkzeug.contrib.fixers import ProxyFix


from . import blueprints


class WebApp(FlaskAPI):
    def __init__(self, app):
        super().__init__(__name__)

        self.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
        self.static_folder = os.path.join(os.path.dirname(__file__), 'statics')

        self.route('/static/<path:path>')(self.send_static_file)

        self.register_blueprint(blueprints.search,
                                url_prefix='/api/search/')
        self.register_blueprint(blueprints.settings,
                                url_prefix='/api/settings/')

        def serve_index_at_root():
            return send_from_directory(self.static_folder, 'webui/dist/index.html')

        def serve_index_at_path(path):
            return send_from_directory(self.static_folder, 'webui/dist/index.html')

        self.route('/<path:path>')(serve_index_at_path)
        self.route('/')(serve_index_at_root)

        @self.before_request
        def before_request():
            g.app = app

        # @server.after_request
        # def shutdown_session(response):
        #     g.app.db.remove()
        #     return response

        # self.wsgi_app = ProxyFix(self.wsgi_app)
