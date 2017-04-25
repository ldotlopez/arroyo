#!/bin/sh

D="/app"
APPDIR="$D/arroyo"
ENVDIR="$D/env"
DATADIR="$D/data"

if [ ! -f "$DATADIR/arroyo.yml" ]; then
	cat > "$DATADIR/arroyo.yml" <<-EOF
	downloader: directory
	db-uri: sqlite://///app/data/arroyo.db
	plugins:
	  downloaders.directory:
	    enabled: True
	    storage-path: "$DATADIR/downloads"
	EOF
fi

export LANG="C.UTF-8"
export LC_ALL="C.UTF-8"
export PYTHONPATH="$APPDIR"

exec "$ENVDIR/bin/python" "$APPDIR/arroyo" -c "$DATADIR/arroyo.yml" "$@"
