import re
from ldotcommons import sqlalchemy as ldotsa


def alter_query_for_model_attr(q, model, key, value):
    # Get possible modifier from key
    m = re.search(
        r'(?P<key>(.+?))-(?P<mod>(glob|regexp|in|min|max))$', key)

    if m:
        key = m.group('key')
        mod = m.group('mod')
    else:
        mod = None

    # To access directly to source attributes key must be normalize to model
    # fields standards
    key = key.replace('-', '_')

    # Minor optimizations for glob modifier
    if mod == 'glob':
        value = value.lower()

    # Extract attr
    attr = getattr(model, key)

    if mod is None:
        q = q.filter(attr == value)

    elif mod == 'glob':
        q = q.filter(attr.like(ldotsa.glob_to_like(value)))

    elif mod == 'like':
        q = q.filter(attr.like(value))

    elif mod == 'regexp':
        q = q.filter(attr.op('regexp')(value))

    elif mod == 'min':
        q = q.filter(attr >= value)

    elif mod == 'max':
        q = q.filter(attr <= value)

    else:
        raise TypeError(key)

    return q


# class GenericFields:
#     def __init__(self, app, key, value):

#         # Get possible modifier from key
#         m = re.search(
#             r'(?P<key>(.+?))-(?P<mod>(glob|regexp|in|min|max))$', key)

#         if m:
#             key = m.group('key')
#             mod = m.group('mod')
#         else:
#             mod = None

#         # This filter access directly to source attributes.
#         # key must be normalize to model fields
#         key = key.replace('-', '_')

#         # Minor optimizations for glob modifier
#         if mod == 'glob':
#             value = value.lower()

#         super().__init__(app, key, value)
#         self.mod = mod
#         self._type_check = False

#     def filter(self, x):
#         f = getattr(self, 'check_' + (self.mod or 'raw'))
#         attr = getattr(x, self.key)

#         if attr is not None and not self._type_check:
#             if not isinstance(self.value, type(attr)):
#                 self.value = type(attr)(self.value)
#             self._type_check = True

#         return f(attr)

#     def check_raw(self, x):
#         return x == self.value

#     def check_glob(self, x):
#         return fnmatch.fnmatchcase(x.lower(), self.value)

#     def check_regexp(self, x):
#         return re.match(self.value, x, re.IGNORECASE)

#     def check_in(self, x):
#         raise NotImplementedError()

#     def check_min(self, x):
#         if x is None:
#             return False

#         return x >= self.value

#     def check_max(self, x):
#         if x is None:
#             return False

#         return x <= self.value
