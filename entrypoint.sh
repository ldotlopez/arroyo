#!/bin/sh

# Configurable stuff
PY3="/usr/bin/python3"
U="arroyo"
G="$U"
APPDIR="/app"
DATADIR="/data"

# Setup permissions
[ -d "$DATADIR" ] || mkdir -p "$DATADIR"

# Setup config
if [ ! -f "$DATADIR/arroyo.yml" ]; then
	cat > "$DATADIR/arroyo.yml" <<-EOF
	downloader: directory
	db-uri: sqlite:////$DATADIR/arroyo.db
	plugins:
	  downloaders.directory:
	    enabled: True
	    storage-path: "$DATADIR/downloads"
	EOF
fi

chown -R "$U":"$G" "$DATADIR"

# Run arroyo
exec sudo \
	-u "$U"              \
	LANG="C.UTF-8"       \
	LC_ALL="C.UTF-8"     \
	PYTHONPATH="$APPDIR" \
	"$PY3" "$APPDIR/arroyo" -c "$DATADIR/arroyo.yml" "$@"
