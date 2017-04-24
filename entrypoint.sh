#!/bin/bash

D="/app"
APPDIR="$D/arroyo"
ENVDIR="$D/env"
DATADIR="$D/data"

if [ ! -f "$DATADIR/arroyo.yml" ]; then
	cat > "$DATADIR/arroyo.yml" <<-EOF
	downloader: mock 
	db-uri: sqlite:////$DATADIR/arroyo.db
	EOF
fi

export PYTHONPATH="$APPDIR"
exec "$ENVDIR/bin/python" "$APPDIR/arroyo" -c "$DATADIR/arroyo.yml" "$@"
