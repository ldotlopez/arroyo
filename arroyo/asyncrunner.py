import asyncio
import random


class AsyncRunner:
    def __init__(self, coros, timeout=-1, n_tasks=5, loop=None):
        if loop is None:
            loop = asyncio.get_event_loop()

        self._timeout = timeout
        self._coros = coros
        self._n_tasks = n_tasks
        self._loop = loop
        self._running = 0
        self._results = []
        self._exhausted = False
        self._loop.set_exception_handler(self.exception_handler)

    @property
    def results(self):
        return self._results

    def exception_handler(self, loop, context):
        e = context['exception']
        print(" ! Got exception:", type(e), e)
        self._running -= 1
        self._feeder()

    # Overridable by subclasses
    def handle_result(self, result):
        print(" < Got result:", result)
        self._results.append(result)

    @asyncio.coroutine
    def _coro_wrapper(self, coro):
        # # With an exception handler installed use this:
        res = yield from coro
        self.handle_result(res)
        self._running -= 1
        self._feeder()

    def _cancel_future(self, future):
        if not future.done():
            print(" ! Cancel")
            future.cancel()
            self._running -= 1
            self._feeder()

    def _feeder(self):
        print(" = ", self._running, self._exhausted)
        while not self._exhausted and (self._running < self._n_tasks):
            try:
                coro = next(self._coros)
                self._running += 1
                wrapped_coro = self._coro_wrapper(coro)
                future = self._loop.create_task(wrapped_coro)

                print(" . Feeding another task")

                if self._timeout:
                    self._loop.call_later(self._timeout,
                                          self._cancel_future,
                                          future)

            except StopIteration:
                print(" . Task generator is exahusted")
                self._exhausted = True

        if not self._running and self._exhausted:
            self._loop.stop()

    def run(self):
        self._loop.call_soon(self._feeder)
        self._loop.run_forever()

if __name__ == '__main__':
    class W:
        def __init__(self, name, fail_prob=0.0):
            self.name = name
            self.fail_prob = fail_prob

        @asyncio.coroutine
        def foo(self):
            sleep = random.randint(1, 10) / 10
            fail = self.fail_prob > (random.randint(1, 10) / 10)
            ret = random.randint(1, 10)

            msg = " > Async task {} return={}:{}, sleep={} will_fail={}"
            msg = msg.format(self.name, self.name, ret, sleep, fail)
            print(msg)

            yield from asyncio.sleep(sleep)

            if fail:
                raise Exception(self.name)
            else:
                return '{}:{}'.format(self.name, ret)

    coros = (W(n, fail_prob=0.5).foo() for n in ['A', 'B', 'C', 'D', 'E'])
    runner = AsyncRunner(coros, n_tasks=3, timeout=0.6)
    runner.run()
    print(runner.results)
