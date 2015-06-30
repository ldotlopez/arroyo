# import functools
# from arroyo.exts.filters import sourcefields
# from arroyo import models
#
# _strs = ('series',)
# _nums = ('year', 'season', 'episode')
#
# _strs = [[x, x + '-like', x + '-regexp', x + '-in'] for x in _strs]
# _nums = [[x, x + '-min', x + '-max'] for x in _nums]
#
# _handles = (
#     functools.reduce(lambda x, y: x + y, _strs, []) +
#     functools.reduce(lambda x, y: x + y, _nums, []))
#
#
# class Filter(sourcefields.Filter):
#     APPLIES_TO = models.Episode,
#     HANDLES = _handles
#
#     def __init__(self, app, key, value):
#         # -like modifier allows case-insensitive search
#         if key == 'series':
#             key = 'series-like'
#
#         super().__init__(app, key, value)
#
#
# __arroyo_extensions__ = [
#     ('filter', 'episodefields', Filter)
# ]
