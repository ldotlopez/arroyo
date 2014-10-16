import configparser

from ldotcommons import logging
from ldotcommons import utils


_logger = logging.get_logger('settings')

# FIXME:
# - AttribDict shoud support __setitem__ functions for this:
#   return class_type({k: v for (k, v) in cp[section].items()})
# - Use 'private' methods for setters/getters? (ex. _set_enabled)
# - RO attributes should be writeable within __init__


class GlobalSection(utils.AttribDict):
    SETTERS = ['logging_level']

    def set_logging_level(self, value):
        self._setter('logging_level', value)
        _logger.info('Logging level: {level}'.format(level=value))
        logging.set_level(value)


class EnabableSection(utils.AttribDict):
    SETTERS = ['enabled']

    def set_enabled(self, value):
        if value.lower() in ('true', '1', 'yes'):
            self._setter('enabled', True)

        elif value.lower() in ('false', '0', 'no'):
            self._setter('enabled', False)

        else:
            raise ValueError(value)


class WebuiSection(EnabableSection):
    pass


class Settings(GlobalSection, metaclass=utils.SingletonMetaclass):
    MULTISECTION_SEP = '.'

    def __init__(self, config_path):
        def parse_generic_section(section, class_type=GlobalSection):
            g = class_type()
            for (k, v) in cp[section].items():
                setattr(g,
                        k.replace('-', '_').replace(' ', '_'),
                        v)
            return g

        def parse_generic_multisection(section_prefix,
                                       container_class_type=GlobalSection,
                                       section_class_type=GlobalSection):
            if section_prefix.endswith(Settings.MULTISECTION_SEP):
                raise ValueError("Section mustn't end with '{}'".format(Settings.MULTISECTION_SEP))

            section_prefix = section_prefix + Settings.MULTISECTION_SEP

            g = container_class_type()
            sections = [x for x in cp.sections() if x.startswith(section_prefix)]
            for section in sections:
                subname = section[len(section_prefix):].replace('-', '_').replace(' ', '_')
                subv = parse_generic_section(section, section_class_type)
                setattr(g, subname, subv)
                print("Set {} to {}".format(subname, repr(subv)))
            return g

        cp = configparser.ConfigParser()
        cp.read(config_path)

        # g = parse_generic_section('main')
        self.notifiers = parse_generic_multisection(
            'notifier',
            container_class_type=utils.AttribDict,
            section_class_type=EnabableSection)
        self.origins = parse_generic_multisection('origin')
        self.queries = parse_generic_multisection('query')
        self.webui = parse_generic_section('webui', WebuiSection)

if __name__ == '__main__':
    import sys

    global g
    g = Settings(sys.argv[1])
