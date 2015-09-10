#!/bin/bash

D="$(dirname -- "$0")"
if [ "${D:0:1}" != "/" ]; then
		D="$PWD/$D"
fi

if [ -z "$VIRTUAL_ENV" ]; then 
	source "$D/env/bin/activate" 2>/dev/null || {
		echo "expected virtual environment in '$D/env' not found"
		exit 1
	}
fi
PYTHONPATH="$D" python3 "$D/arroyo" \
	--db-uri sqlite:///"$D/arroyo.db" \
	--config-file "$D/arroyo.ini" \
	"$@" 
