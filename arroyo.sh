#!/bin/bash

# Copyright (C) 2015 Luis López <luis@cuarentaydos.com>
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301,
# USA.



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
	--config-file "$D/arroyo.yml" \
	"$@" 
