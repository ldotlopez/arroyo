from arroyo import pluginlib
from arroyo import models


import os
import subprocess


from appkit import store


SETTINGS_NS = 'plugins.misc.externalhooks'
STATES = {
    models.Source.State.NONE: 'none',
    models.Source.State.INITIALIZING: 'initialize',
    models.Source.State.QUEUED: 'queue',
    models.Source.State.PAUSED: 'pause',
    models.Source.State.DOWNLOADING: 'download',
    models.Source.State.SHARING: 'share',
    models.Source.State.DONE: 'done',
    models.Source.State.ARCHIVED: 'archive'
}


class ExternalHooks(pluginlib.Service):
    __extension_name__ = 'externalhooks'

    def __init__(self, app):
        app.signals.connect('source-state-change', self.on_source_state_change)
        super().__init__(app)

    def on_source_state_change(self, *args, **kwargs):
        source = kwargs.pop('source')
        state = source.state
        state_name = STATES[state]

        data = {
            'source': source.as_dict(),
            'info': self.app.downloads.get_info(source)
        }
        data['source']['state'] = state_name

        env = os.environ.copy()
        for (k, v) in sorted(store.flatten_dict(data).items()):
            env_key = 'ARROYO_{}'.format(k.upper().replace('.', '_'))
            env_value = str(v) if v else ''
            env[env_key] = env_value

        hooks = self.app.settings.get(SETTINGS_NS + '.on-' + state_name, [])
        if not isinstance(hooks, list):
            hooks = [hooks]

        for hook in hooks:
            proc = subprocess.Popen(
                hook, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
            out, err = proc.communicate()

            lines = (
                [(self.app.logger.info, x)
                 for x in out.decode('utf-8').split('\n')] +
                [(self.app.logger.error, x)
                 for x in err.decode('utf-8').split('\n')])

            lines = [(f, line.strip()) for (f, line) in lines if line]
            for (f, line) in lines:
                msg = "on-{} {}: {}".format(STATES[state], hook, line)
                f(msg)

__arroyo_extensions__ = [
    ExternalHooks
]
