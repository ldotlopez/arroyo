import builtins
import math
import multiprocessing
from itertools import chain


def cpu_map(fn, items, n_cpus=None, bulk=False):
    if n_cpus is None:
        n_cpus = multiprocessing.cpu_count()

    if n_cpus == 1:
        if bulk:
            results = fn(*items)
        else:
            results = [fn(item) for item in items]

    else:
        with multiprocessing.Pool(n_cpus) as p:
            if bulk:
                items = chunkify(items, n_chunks=n_cpus)
                results = p.starmap(fn, items)
                results = list(chain.from_iterable(results))
            else:
                results = p.map(fn, items)

    return results


def bulk_helper(fn, *args):
    """
    Allows fn to run with star arguments
    """
    ret = []

    for arg in args:
        ret.append(fn(arg))

    return ret


def exception_catcher_helper(fn, *args, **kwargs):
    """
    Safe execution of fn.

    Return whatever fn returns or, in case of Exception, the exception itself.
    SyntaxError it's a special case and is not catched
    """
    try:
        return fn(*args, **kwargs)

    except SyntaxError:
        raise

    except Exception as e:
        return e


def check_result(x):
    if isinstance(x, Exception):
        raise x

    return x


def chunkify(list_, n_chunks):
    """
    Split into chunks
    """
    if not isinstance(n_chunks, int) or n_chunks < 1:
        raise ValueError(n_chunks)

    chunks = []
    chunk_size = math.ceil(len(list_) / n_chunks)

    for i in range(n_chunks):
        start = i * chunk_size
        end = (i + 1) * chunk_size
        chunks.append(list_[start:end])

    return chunks
