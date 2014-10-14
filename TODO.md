- Standarize type, language & co on arroyo.models.Source

- Write arroyo.app, move Arroyo class in and rebuild as Singleton

- Split filter handling into plugins (module-based commands?)
  filter.register('tag', function)

- Expand signal usage

- Split commands into plugins (class-based commands?)
  command.handle_command_line
  command.execture

- arroyo.plugin support module
  arroyo.plugin.Plugin.configure
