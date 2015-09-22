from flask.ext.sqlalchemy import SQLAlchemy
import re
from . import utils

db = SQLAlchemy()


def check_str(s):
    return isinstance(s, str)


def check_none(x):
    return x is None


def check_non_empty_str(s):
    return check_str(s) and s != ''


def check_email(e):
    return check_non_empty_str(e)


def check_int(i):
    return isinstance(i, int)


def check_person(p):
    return isinstance(p, Person)


def check_section(p):
    return isinstance(p, Section)


def check_channel(c):
    valids = 'phone email form ticket desk support messages cau mahara'
    valids = valids.split(' ')
    return c in valids


def check_phone(s):
    return re.search(r'^[0-9+]+$', s) is not None


def check_stamp(dt):
    return isinstance(dt, int)


def model_field_safe_update(inst, params, key, check_func, field=None):
    if field is None:
        field = key

    if key not in params:
        return

    value = params[key]
    if check_func(value):
        setattr(inst, field, value)
    else:
        raise ModelException("invalid {}".format(key))


class ModelException(Exception):
    pass


class Section(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(
        db.String(128),
        nullable=False,
        unique=True)

    def __repr__(self):
        return '<Section #%d %r>' % (self.id, self.name)

    def __unicode__(self):
        return self.name

    def __str__(self):
        return self.__unicode__()

    def update(self, **kwargs):
        def _update(key, check_func, field=None):
            return model_field_safe_update(
                self, kwargs, key, check_func, field)

        for param in kwargs:
            if param in ('id',):
                raise ModelException("'ID' can't be modified")

            if param not in ('name',):
                raise ModelException("unknow param {}".format(param))

        _update('name', check_non_empty_str)


class Person(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=True)
    name = db.Column(db.String(80), nullable=True)
    surname = db.Column(db.String(80), nullable=True)
    phone = db.Column(db.String(15), nullable=True)
    notes = db.Column(db.String(1024), nullable=True)
    section_id = db.Column(
        db.Integer,
        db.ForeignKey('section.name'),
        nullable=False)
    section = db.relationship(
        'Section',
        backref=db.backref(
            'persons'))  # no cascade option here, prevents delete sections

    def __init__(self, **kwargs):
        self.update(**kwargs)

    def __repr__(self):
        return '<User %r>' % self.email

    def as_dict(self):
        ret = {key: getattr(self, key)
               for key in ['id', 'email', 'name', 'surname', 'notes', 'phone']}
        ret['activities'] = [x.id for x in self.activities.all()]
        if self.section:
            ret['section'] = self.section.id
        else:
            ret['section'] = None

        return ret

    def update(self, **kwargs):
        def _update(key, check_func, field=None):
            return model_field_safe_update(
                self, kwargs, key, check_func, field)

        for param in kwargs:
            if param in ('id',):
                raise ModelException("ID can't be updated")
            if param not in ('email', 'name', 'surname', 'phone', 'notes',
                             'section'):
                raise ModelException("unknow param {}".format(param))

        _update('email', lambda x: x is None or check_email)
        _update('name', lambda x: x is None or check_non_empty_str)
        _update('surname', lambda x: x is None or check_non_empty_str)
        _update('phone', lambda x: x is None or check_phone(x))
        _update('notes', lambda x: x is None or check_str(x))
        _update('section', lambda x: x is None or check_section)


class Activity(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    person_id = db.Column(
        db.Integer,
        db.ForeignKey('person.id'),
        nullable=False)  # Automagically populated?
    person = db.relationship(
        'Person',
        backref=db.backref(
            'activities',
            lazy='dynamic',
            cascade="all, delete, delete-orphan"))
    stamp = db.Column(
        db.Integer,
        default=utils.now_timestamp,
        nullable=False)
    duration = db.Column(
        db.Integer,
        nullable=False)
    channel = db.Column(
        db.Enum(
            'phone', 'email', 'form', 'ticket', 'desk', 'support', 'messages',
            'cau', 'mahara',
            convert_unicode=True),
        nullable=False)
    description = db.Column(
        db.String(1024))

    def __init__(self, **kwargs):
        self.update(**kwargs)

    def as_dict(self, deep=False):
        ret = {key: getattr(self, key)
               for key in ['id', 'channel', 'description', 'stamp',
                           'duration']}
        ret['person'] = self.person.id
        return ret

    def update(self, **kwargs):
        def _update(key, check_func, field=None):
            return model_field_safe_update(
                self, kwargs, key, check_func, field)

        for param in kwargs:
            if param in ('id',):
                raise ModelException("ID can't be updated")
            if param not in ('person', 'channel', 'description', 'stamp',
                             'duration'):
                raise ModelException("unknow param {}".format(param))

        _update('person', check_person)
        _update('channel', check_channel)
        _update('description', lambda x: x is None or check_str(x))
        _update('stamp', lambda x: x is None or check_stamp(x))
        _update('duration', check_int)
