# -*- coding: utf-8 -*-
# [SublimeLinter pep8-max-line-length:119]
# vim: set fileencoding=utf-8 :

from arroyo import exts


class MockDownloader(exts.Downloader):
    def __init__(self, db_session, *args, **kwargs):
        self.sources = set()

    def do_add(self, source, **kwargs):
        self.sources.add(source)

    def do_remove(self, source):
        self.sources.remove(source)

    def do_list(self):
        return list(self.sources)

    def translate_item(self, source):
        return source

    def get_state(self, source):
        return source.state


__arroyo_extensions__ = [
    ('downloader', 'mock', MockDownloader)
]
