#!/usr/bin/env python3


if __name__ == '__main__':
    from itertools import chain
    import sys

    import arroyo

    # Parse command line in a first phase to allow extensions and config file
    # loading from command line
    argparser = arroyo.core.build_argument_parser()
    args, remaining = argparser.parse_known_args()

    config = arroyo.core.build_config_parser(args)

    extensions = {
        'origins': ('eztv', 'kickass', 'spanishtracker'),
        'selectors': ('source', 'episode', 'movie'),
        'commands': ('cron', 'db', 'downloads', 'import', 'mediainfo',
                     'search'),
        'downloaders': ('mock', 'transmission'),
        'misc': ('importercron',)
    }
    extensions = chain.from_iterable([
        [ns+'.'+ext for ext in extensions[ns]]
        for ns in extensions])
    extensions = [x for x in extensions]

    log_levels = 'CRITICAL ERROR WARNING INFO DEBUG'.split(' ')
    if args.verbose or args.quiet:
        log_level = max(0, min(4, 2 + args.verbose - args.quiet))
        log_level = log_levels[log_level]
    else:
        log_level = None

    try:
        app = arroyo.Arroyo(extensions=extensions, config=config,
                            log_level=log_level)
        app.run_from_args()
    except arroyo.exc.ArgumentError as e:
        print(str(e), file=sys.stderr)
        sys.exit(2)
