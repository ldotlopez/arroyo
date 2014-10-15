#!/bin/bash

D="$(dirname -- "$0")"

source "$D/env/bin/activate"
PYTHONPATH="$D" python3 "$D/test-ng.py" \
	--db-uri "$D/arroyo.db" \
	--config "$D/arroyo.ini" \
	"$@" 
