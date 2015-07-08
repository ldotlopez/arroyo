import unittest

import os

import bs4

from arroyo import core, exts, models
from pprint import pprint as pp


def src(name, **kwsrc):
    return models.Source.from_data(name, **kwsrc)


class ImdbListFilter(exts.Filter):
    def __init__(self, app, key, value):
        super().__init__(app, key, value)

        buff = self.app.fetcher.fetch(self.value)
        soup = bs4.BeautifulSoup(buff, "html.parser")

        self._titles = [x.text for x in soup.select('h3.lister-item-header a')]

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
        import ipdb; ipdb.set_trace(); pass


class ImdbTest(unittest.TestCase):
    def setUp(self):
        basedir = os.path.dirname(__file__)
        mock_fetcher_basedir = os.path.join(basedir, 'www-samples')

        settings = core.build_basic_settings()
        settings.delete('fetcher')
        settings.set('fetcher', 'mock')
        settings.set('fetcher.mock.basedir', mock_fetcher_basedir)
        settings.set('db-uri', 'sqlite:///:memory:')

        self.app = core.Arroyo(settings)

    def test_parsing(self):
        expected = ['Serenity',
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
        x = src('Serenity')

        imdb_list_filter = ImdbListFilter(
            self.app,
            'list',
            'http://www.imdb.com/user/ur00000000/watchlist')

        self.assertTrue(imdb_list_filter.filter(x))

if __name__ == '__main__':
    unittest.main()
