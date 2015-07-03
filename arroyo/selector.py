import sys


from arroyo import exts


class Selector:
    def __init__(self, app):
        self.app = app

    def get_queries_specs(self):
        return [exts.QuerySpec(x, **params) for (x, params) in
                self.app.settings.get_tree('query', {}).items()]

    def get_queries(self):
        return list(map(self.get_query_for_spec, self.get_queries_specs()))

    def get_query_for_spec(self, spec):
        return self.app.get_extension('query', spec.get('as'), spec=spec)

    def _auto_import(self, query):
        if self.app.settings.get('auto-import'):
            self.app.importer.import_query_spec(query.spec)

    def matches(self, spec, everything=False):
        query = self.get_query_for_spec(spec)
        self._auto_import(query)
        ret = query.matches(everything)
 
        return sorted(ret,
            key=lambda x: -sys.maxsize if x.superitem is None else hash(x))

        # Alternative sorting method for reference
        # t = {None: []}
        # for (superitem, item) in ((x.superitem, x) for x in ret):
        #    if superitem not in t:
        #         t[superitem] = []
        #    t[superitem].append(item)
        # 
        # keys = [None] + list([x for x in t if x is not None])
        # return list(chain.from_iterable([t[k] for k in keys]))

    def select(self, spec):
        query = self.get_query_for_spec(spec)
        self._auto_import(query)
        return query.selection()
