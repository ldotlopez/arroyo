from blinker import signal

SIGNALS = {
    'source-added': signal('source-added'),
    'source-updated': signal('source-updated'),
    'sources-added-batch': signal('sources-added-batch'),
    'sources-updated-batch': signal('sources-updated-batch'),

    'source-state-change': signal('source-state-change')
}
