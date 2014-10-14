#!/bin/bash

D="$(dirname -- "$0")"

source "$D/env/bin/activate"
PYTHONPATH="$D" python3 "$D/arroyo/__main__.py" "$@"
