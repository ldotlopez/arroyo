# -*- coding: utf-8 -*-

# Copyright (C) 2015 Luis López <luis@cuarentaydos.com>
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301,
# USA.


from arroyo import pluginlib
from arroyo import models


import os
import subprocess


from appkit import (
    logging,
    store
)


SETTINGS_NS = 'plugins.misc.externalhooks'
STATES = {
    models.State.NONE: 'none',
    models.State.INITIALIZING: 'initialize',
    models.State.QUEUED: 'queue',
    models.State.PAUSED: 'pause',
    models.State.DOWNLOADING: 'download',
    models.State.SHARING: 'share',
    models.State.DONE: 'done',
    models.State.ARCHIVED: 'archive'
}


class ExternalHooks(pluginlib.Service):
    __extension_name__ = 'externalhooks'

    def __init__(self, app, *args, **kwargs):
        super().__init__(app, *args, **kwargs)
        signals = app.signals
        settings = app.settings

        self.logger = logging.getLogger('externalhooks')
        self.settings = settings

        signals.connect('source-state-change', self.on_source_state_change)

    def hooks_for_state(self, name):
        assert isinstance(name, str)
        assert name in STATES.values()

        key = SETTINGS_NS + '.on-' + name
        hooks = self.settings.get(key, [])

        if not isinstance(hooks, list):
            hooks = [hooks]

        return hooks

    def on_source_state_change(self, *args, **kwargs):
        source = kwargs.pop('source')
        state_name = STATES[source.state]

        data = {
            'source': source.asdict(),
            'info': self.app.downloads.get_info(source)
        }
        data['source']['state'] = state_name

        env = os.environ.copy()
        for (k, v) in sorted(store.flatten_dict(data).items()):
            env_key = 'ARROYO_{}'.format(k.upper().replace('.', '_'))
            env_value = str(v) if v else ''
            env[env_key] = env_value

        for hook in self.hooks_for_state(state_name):
            proc = subprocess.Popen(
                hook, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
            out, err = proc.communicate()

            lines = (
                [(self.logger.info, x)
                 for x in out.decode('utf-8').split('\n')] +
                [(self.logger.error, x)
                 for x in err.decode('utf-8').split('\n')])

            lines = [(f, line.strip()) for (f, line) in lines if line]
            for (f, line) in lines:
                msg = "on-{} {}: {}".format(state_name, hook, line)
                f(msg)

__arroyo_extensions__ = [
    ExternalHooks
]
