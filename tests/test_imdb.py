# -*- coding: utf-8 -*-

# Copyright (C) 2015 Luis López <luis@cuarentaydos.com>
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301,
# USA.


import unittest


from arroyo import exts, models


import bs4


import testapp


class ImdbListFilter(exts.Filter):
    def __init__(self, app, key, value):
        super().__init__(app, key, value)
        self._api = '938e3793eeac93b5eb314bc31f5ff172'

        buff = self.app.fetcher.fetch(self.value)
        soup = bs4.BeautifulSoup(buff, "html.parser")

        self._titles = [x.text for x in soup.select('h3.lister-item-header a')]
        imdb_ids = (x.attrs.get('href', '') for x in
                    soup.select('h3.lister-item-header a'))
        imdb_ids = (x for x in imdb_ids if x)
        self._imdb_ids = (x.split('/')[2] for x in imdb_ids)

        # Get imdb IDs for titles using imdbpie API
        # tts = (x.attrs.get('href', '') for x in
        #        soup.select('h3.lister-item-header a'))
        # tts = (x for x in tts if x)
        # tts = (x.split('/')[2] for x in tts)
        # tts = list(tts)
        # pp (tts)
        # api = Imdb(cache=True)
        # pp(api.get_title_by_id(tts[0]))
        # pp(titles)

    @property
    def titles(self):
        return self._titles

    def filter(self, src):
        try:
            return src.movie.title in self.titles
        except AttributeError:
            return False


class ImdbTest(unittest.TestCase):
    def setUp(self):
        self.app = testapp.TestApp({})

    def test_parsing(self):
        expected = [
            'Serenity',
            'Super 8',
            'Dune',
            'Firefly',
            'El precio del poder',
            'Don Jon',
            'Riddick',
            'The Bling Ring',
            'Sólo los amantes sobreviven',
            'Todas las cheerleaders muertas',
            'Nymphomaniac. Volumen 1',
            '¡Rompe Ralph!',
            'Plan en Las Vegas',
            'El Hobbit: La batalla de los cinco ejércitos',
            'Zombis nazis 2: Rojos vs Muertos',
            'Sin City: Una dama por la que matar',
            'Kill Bill: Vol. 3',
            'Reservoir Dogs',
            'Kill Bill. Volume 2',
            'American Beauty',
            'El árbol de la vida',
            "À l'intérieur",
            'Solaris',
            'Monstruoso',
            'El amanecer del planeta de los simios',
            'Napoleon Dynamite',
            'Silent Hill 2: Revelación 3D',
            'Infiltrados',
            'Juegos sucios',
            'Orígenes',
            'The Artist',
            'Melancolía',
            'La conspiración de noviembre',
            'A Girl Walks Home Alone at Night',
            'Lo que hacemos en las sombras']

        imdb_list_filter = ImdbListFilter(
            self.app,
            'list',
            'http://www.imdb.com/user/ur00000000/watchlist')

        self.assertEqual(set(expected), set(imdb_list_filter.titles))

    def test_filter(self):
        x = models.Source.from_data('Serenity XviD.avi', type='movie')
        self.app.insert_sources(x)

        imdb_list_filter = ImdbListFilter(
            self.app,
            'list',
            'http://www.imdb.com/user/ur00000000/watchlist')

        self.assertTrue(imdb_list_filter.filter(x))

if __name__ == '__main__':
    unittest.main()
