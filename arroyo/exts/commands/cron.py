from ldotcommons import keyvaluestore, utils

from arroyo import exts


class CronCommand(exts.Command):
    help = 'Run cron tasks'

    arguments = (
        exts.argument(
            '-t', '--task',
            dest='tasks',
            action='append',
            default=[],
            help=('Run specific task')
        ),
        exts.argument(
            '-f', '--force',
            dest='force',
            action='store_true',
            help=('Force tasks to run omiting intervals')
        )
    )

    def __init__(self, app, *args, **kwargs):
        super(CronCommand, self).__init__(app)
        self._logger = app.logger.getChild('crontasks')
        self._tasks = {}
        self._now = utils.utcnow_timestamp()
        self._kvs = keyvaluestore.KeyValueStore(self.app.db.session)

        impls = self.app.get_implementations('crontask')
        for task in impls:
            try:
                interval = int(utils.parse_interval(impls[task].interval))
            except ValueError:
                msg = 'Cron task {task} doesn\'t define a valid interval: \'{value}\''
                msg = msg.format(task=task, value=impl.interval)
                self._logger.warning(msg)
                continue

            self._tasks[task] = {
                'name': task,
                'cls': impls[task],
                'interval': interval
            }

    def get_tasks(self):
        return list(self._tasks.keys())

    def get_task_info(self, task):
        return self._tasks[task]

    def run_task(self, task, force=False):
        try:
           task_info = self.get_task_info(task)
        except KeyError:
            msg = 'Unknow task \'{task}\''
            msg = msg.format(task=task)
            self._logger.warning(msg)
            return

        kvs_key = 'crontasks.{task}.last-execution'.format(task=task)
        last_exec = self._kvs.get(kvs_key, default=0)

        msg = 'Cron task {task}: since:{last_exec} diff:{diff} interval:{interval} force:{force}'
        msg = msg.format(
            task=task,
            diff=self._now - last_exec,
            last_exec=last_exec,
            interval=task_info['interval'],
            force='yes' if force else 'no'
        )
        self._logger.debug(msg)

        if ((self._now - last_exec) >= task_info['interval']) or force:
            try:
                r = self.app.get_extension('crontask', task).run()
            except Exception as e:
                import ipdb; ipdb.set_trace()
                msg = 'Cron task {task} fatal error: {msg}'
                msg = msg.format(task=task, msg=repr(e))
                self._logger.error(msg)
                return

            self._kvs.set(kvs_key, self._now)
            return r

    def run(self):
        tasks = self.app.arguments.tasks
        if not tasks:
            tasks = self.get_tasks()

        for task in tasks:
            self.run_task(task, self.app.arguments.force)
 
        return

__arroyo_extensions__ = (
    ('command', 'cron', CronCommand),
)
