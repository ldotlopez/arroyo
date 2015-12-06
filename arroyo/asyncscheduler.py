import asyncio
import queue

from ldotcommons import utils


class AsyncScheduler:
    def __init__(self, *coros,
                 maxtasks=5, timeout=0, loop=None,
                 logger=None, asyncio_debug=False):
        if loop is None:
            loop = asyncio.get_event_loop()

        if logger is None:
            logger = utils.NullSingleton()

        self._logger = logger

        self._loop = loop
        self._maxtasks = maxtasks
        self._timeout = timeout

        self._q = queue.Queue()

        self.results = []

        self._loop.set_debug(asyncio_debug)

        self._loop.set_exception_handler(self.exception_handler)

    def sched(self, *coros):
        for coro in coros:
            if not asyncio.iscoroutine(coro):
                msg = "sched got a non coroutine"
                raise SystemExit(msg)

            self._q.put_nowait(coro)

    def task_done_handler(self, handler):
        """
        All tasks (done, cancelled, exception) end here
        """

        # If handler (future wrapper coroutine) was cancelled or raised an
        # exception will scalate from here. exception_handler will catch it.
        res = handler.result()

        self.result_handler(res)
        self.feed()

    def cancel_task(self, handler):
        """
        This method is called for all coroutines via the call_later method even
        if the coroutine is done without errors.

        It's easier to check for 'done' state on initial handler (or coro) that
        cancel this cancel_task call
        """
        if not handler.done():
            handler.cancel()

    def exception_handler(self, loop, context):
        """
        Override this method for handle exceptions with custom code
        See:
        - asyncio.BaseEventLoop.set_exception_handler
        - asyncio.BaseEventLoop.call_exception_handler
        """
        self.feed()

    def result_handler(self, result):
        """
        Override this method for handle coroutine results with custom code
        """
        self.results.append(result)

    def feed_one(self):
        coro = self._q.get_nowait()

        task = self._loop.create_task(coro)
        task.add_done_callback(self.task_done_handler)
        if self._timeout > 0:
            self._loop.call_later(self._timeout, self.cancel_task, task)

    def feed(self):
        while not self._q.empty() and self._have_slots():
            self.feed_one()

        if not self._pending_tasks() and self._q.empty():
            self._loop.stop()

    def stop(self):
        """
        Stop execution of AsyncScheduler.
        This doesn't cancel running tasks
        """
        self._loop.stop()

    def run(self):
        """
        Starts execution of scheduled tasks
        """
        self._loop.call_soon(self.feed)
        self._loop.run_forever()

    def _have_slots(self):
        return len(self._pending_tasks()) < self._maxtasks

    def _pending_tasks(self):
        return [
            x for x in asyncio.Task.all_tasks(loop=self._loop)
            if not x.done() and not x.cancelled()
        ]


class TestException(Exception):
    pass


@asyncio.coroutine
def test_coro(name, secs=0.1, ret=None, fail_before=False, fail_after=False):
    if fail_before:
        raise TestException(name + "::before")

    print("sleep", name)
    yield from asyncio.sleep(secs)
    print("wake", name)

    if fail_after:
        raise TestException(name + "::fail_after")

    return ret

if __name__ == '__main__':
    # schedule = AsyncScheduler(timeout=0.3, maxtasks=2)
    # schedule.sched(test_coro('a'))
    # schedule.sched(test_coro('b', secs=0.4))
    # schedule.sched(test_coro('c'))
    # schedule.sched(test_coro('d'))
    # schedule.run()

    schedule = AsyncScheduler(timeout=0.2, maxtasks=1)
    schedule.sched(test_coro('fail', fail_after=True))
    schedule.sched(test_coro('c'))
    schedule.sched(test_coro('d'))
    schedule.run()

    # schedule = AsyncScheduler(timeout=0.3, maxtasks=2)
    # schedule.sched(test_coro('fail', secs=1))
    # schedule.run()

    # schedule = AsyncScheduler(timeout=0.3, maxtasks=2)
    # schedule.sched(test_coro('timeout', secs=1))
    # schedule.run()

    pass
