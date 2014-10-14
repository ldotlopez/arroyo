# -*- coding: utf-8 -*-
# [SublimeLinter pep8-max-line-length:119]
# vim: set fileencoding=utf-8 :

from path import path

from ldotcommons import sqlalchemy as ldotsa

from arroyo import db

FIXTURES = "fixtures.json"


def fixture_loader(x):
    return db.Source(**db.source_data_builder(**x))


def setup_session():
    conn = ldotsa.create_session('sqlite:///:memory:')
    ldotsa.load_fixtures_file(conn, path(__file__).dirname() / FIXTURES, fixture_loader)

    return conn
