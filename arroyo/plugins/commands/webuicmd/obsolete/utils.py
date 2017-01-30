import datetime
import time

from path import path


def now_timestamp():
    return int(time.mktime(datetime.datetime.now().timetuple()))


def backend_root():
    return path(__file__).realpath().dirname()
