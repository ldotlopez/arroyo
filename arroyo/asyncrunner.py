import asyncio
import random
from ldotcommons import logging


class AsyncRunner:
    def __init__(self, coros,
                 maxtasks=5, timeout=-1,  loop=None,
                 log_name='async-runner', log_level=logging.logging.CRITICAL):

        self._logger = logging.get_logger(log_name)
        self._logger.setLevel(log_level)

        self._coros = coros
        self._maxtasks = maxtasks

        if loop is None:
            loop = asyncio.get_event_loop()
        self._loop = loop
        self._loop.set_exception_handler(self.exception_handler)

        self._timeout = timeout

        self._results = []
        self._exhausted = False

    def active_tasks(self):
        def _is_active(x):
            return not x.done() and not x.cancelled()

        return [x for x in asyncio.Task.all_tasks(loop=self._loop)
                if _is_active(x)]

    @property
    def results(self):
        """
        Contains results from coroutines if a subclass overrides the
        handle_result method throws a NotImplementedError exception.
        """
        if self.__class__.handle_result != AsyncRunner.handle_result:
            msg = ("{clsname} is subclassing AsyncRunner. "
                   "{clsname}.result property is disabled")
            msg = msg.format(clsname=self.__class__.__name__)
            raise TypeError(msg)
        return self._results

    # Overridable by subclasses
    def exception_handler(self, loop, context):
        """
        Exception handling.
        AsyncRunner.sched_coros must be called before returning.
        """
        e = context['exception']
        self._logger.debug(" ! Got exception:", type(e), e)
        self.sched_coros()

    # Overridable by subclasses
    def handle_result(self, result):
        """
        Handle results from coroutines. If it is overided the results property
        is disabled.
        """
        self._logger.debug(
            " < Got result: {}".format(result)
        )
        self._results.append(result)

    def sched_coros(self):
        """
        Schedules coroutines to be run in loop
        """
        self._loop.call_soon(self._sched_coros)

    @asyncio.coroutine
    def _coro_wrapper(self, coro):
        res = yield from coro
        self.handle_result(res)
        self._feeder()

    def _cancel_future(self, future):
        if not future.done():
            self._logger.debug(
                " ! Cancel task, running: {}".format(len(self.active_tasks()))
            )
            future.cancel()
            self._break = True
            self._feeder()

    def _sched_coros(self):
        self._logger.debug(
            " = {} {} ".format(len(self.active_tasks()), self._exhausted)
        )

        while (not self._exhausted and
               (len(self.active_tasks()) < self._maxtasks)):
            try:
                coro = next(self._coros)
            except StopIteration:
                self._logger.debug(
                    " . Task generator is exahusted"
                )
                self._exhausted = True
                break

            wrapped_coro = self._coro_wrapper(coro)
            future = self._loop.create_task(wrapped_coro)

            self._logger.debug(
                " . Feeding another task"
            )

            if self._timeout:
                self._loop.call_later(self._timeout,
                                      self._cancel_future,
                                      future)

        if not self.active_tasks() and self._exhausted:
            self._loop.stop()

    def run(self):
        self._loop.call_soon(self._sched_coros)
        self._loop.run_forever()

    def stop(self):
        self._loop.stop()


class CustomAsyncRunner(AsyncRunner):
    def handle_result(self, x):
        print(x)


if __name__ == '__main__':
    class W:
        def __init__(self, name, fail_prob=0.0, sleep=None):
            self.name = name
            self.fail_prob = fail_prob
            self.sleep = sleep or random.randint(1, 10) / 10

        @asyncio.coroutine
        def foo(self, sleep=None):

            fail = self.fail_prob > (random.randint(1, 10) / 10)
            ret = random.randint(1, 10)

            msg = " > Async task {} return={}:{}, sleep={} will_fail={}"
            msg = msg.format(self.name, self.name, ret, self.sleep, fail)
            print(msg)

            yield from asyncio.sleep(self.sleep)

            if fail:
                raise Exception(self.name)
            else:
                return '{}:{}'.format(self.name, ret)

    coros = (W(n, fail_prob=0.6).foo() for n in ['A', 'B', 'C', 'D', 'E'])
    # coros = iter([W('A', sleep=0.8).foo()])
    runner = AsyncRunner(coros, maxtasks=3, timeout=0.7)
    runner.run()
    print(runner.results)
