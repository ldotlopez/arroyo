import re
from appkit import sqlalchemy as ldotsa


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
