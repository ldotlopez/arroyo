# -*- coding: utf-8 -*-
# [SublimeLinter pep8-max-line-length:119]
# vim: set fileencoding=utf-8 :


class Downloader:
    def __init__(self, db_session, *args, **kwargs):
        self.sources = set()

    def do_add(self, source, **kwargs):
        self.sources.add(source)

    def do_remove(self, item):
        pass

    def do_list(self):
        return list(self.sources)
