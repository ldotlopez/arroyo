_UNDEF = object()


class IllegalKeyError(ValueError):
    pass


class KeyNotFoundError(KeyError):
    pass


class ValidationError(ValueError):
    pass


class Store:
    def __init__(self):
        self._d = {}
        self._validators = []

    @staticmethod
    def _process_key(key):
        if not isinstance(key, str):
            raise IllegalKeyError(key)

        parts = key.split('.')
        if not all(parts):
            raise IllegalKeyError(key)

        return parts

    def _process_value(self, key, value):
        for vfunc in self._validators:
            value = vfunc(key, value)

        return value

    def _get_subdict(self, key, create=False):
        d = self._d

        parts = self._process_key(key)
        for idx, p in enumerate(parts[:-1]):
            if p not in d and create:
                d[p] = {}

            # Override existing values with dicts is allowed
            # Subclass Store or use a validator if this behaviour needs to be
            # changed
            if p in d and not isinstance(d[p], dict):
                d[p] = {}

            if p not in d:
                raise KeyNotFoundError('.'.join(parts[:idx]))

            d = d[p]

        return parts[-1], d

    def add_validator(self, fn):
        self._validators.append(fn)

    def set(self, key, value):
        subkey, d = self._get_subdict(key, create=True)
        v = self._process_value(key, value)
        d[subkey] = v

    def get(self, key, default=_UNDEF):
        if key is None:
            return self._d

        try:
            subkey, d = self._get_subdict(key, create=False)
            return d[subkey]

        except (KeyNotFoundError, KeyError):
            if default != _UNDEF:
                return default
            else:
                raise KeyNotFoundError(key)

    def delete(self, key):
        subkey, d = self._get_subdict(key)
        try:
            del(d[subkey])
            return
        except KeyError:
            pass  # Mask real exception

        raise KeyNotFoundError(key)

    def children(self, key=None):
        subkey, d = self._get_subdict(key)
        try:
            return list(d[subkey].keys())
        except KeyError:
            raise KeyNotFoundError(key)
