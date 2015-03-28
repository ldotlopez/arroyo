#!/usr/bin/env python3


if __name__ == '__main__':
    from itertools import chain
    import sys

    import arroyo

    # Parse command line
    argparser = arroyo.core.build_argument_parser()
    args, remaining = argparser.parse_known_args()

    if args.help:
        argparser.print_help()
        sys.exit(1)

    config = arroyo.core.build_config_parser(args)

    extensions = {
        'origins': ('eztv', 'kickass', 'spanishtracker'),
        'selectors': ('source', 'episode', 'movie'),
        'commands': ('import', 'db', 'downloads', 'mediainfo', 'search'),
        'downloaders': ('mock', 'transmission')
    }
    extensions = chain.from_iterable([
        [ns+'.'+ext for ext in extensions[ns]]
        for ns in extensions])
    extensions = [x for x in extensions]

    try:
        app = arroyo.Arroyo(extensions=extensions, config=config)
        app.run_from_args()
    except arroyo.exc.ArgumentError as e:
        print(str(e), file=sys.stderr)
        sys.exit(2)
