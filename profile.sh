#!/bin/bash

if [ "${D:0:1}" != "/" ]; then
		D="$PWD/$D"
fi

if [ -z "$VIRTUAL_ENV" ]; then 
	source "$D/env/bin/activate" 2>/dev/null || {
		echo "expected virtual environment in '$D/env' not found"
		exit 1
	}
fi

PYTHONPATH="$D" python3 -m profile -o profile.pstats "$D/arroyo/__main__.py" \
	--db-uri sqlite:///"$D/arroyo.db" \
	--config-file "$D/arroyo.yml" \
	"$@"

PYTHONPATH="$D" gprof2dot -f pstats profile.pstats | dot -Tpng -o profile.png
rm profile.pstats
