#!/bin/bash

D="$(dirname -- "$0")"
if [ "${D:0:1}" != "/" ]; then
		D="$PWD/$D"
fi

source "$D/env/bin/activate"
PYTHONPATH="$D" python3 "$D/test-ng.py" \
	--db-uri sqlite:///"$D/arroyo.db" \
	--config-file "$D/arroyo.ini" \
	"$@" 
