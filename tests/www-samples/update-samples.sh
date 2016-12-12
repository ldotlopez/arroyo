#!/bin/bash

D="$(cd "$(dirname -- "$0")"; pwd -P)"
COOKIEJAR="$(mktemp)"

function dl {
	local URL=$1
	local DEST=$2

	curl -s -b "$COOKIEJAR" "$URL" | python3 "$D/remove-magnets.py" > "$D/$DEST"
}

curl -s -c "$COOKIEJAR" "http://www.elitetorrent.net/" >/dev/null

dl	\
	"http://www.elitetorrent.net/torrent/34527/mercenario-microhd" \
	"elitetorrent-detail.html"

dl	\
	"http://www.elitetorrent.net/descargas/modo:listado" \
	"elitetorrent-listing.html"

dl	\
	"http://www.elitetorrent.net/resultados/modern+family" \
	"elitetorrent-search-result.html"

dl	\
	"https://eztv.ag/shows/18/battlestar-galactica/" \
	"eztv-bsg.html"

dl	\
	"https://eztv.ag/page_0" \
	"eztv-page-0.html"

dl	\
	"https://eztv.ag/showlist/" \
	"eztv-series-index.html"

dl	\
	"https://kickass.cd/search.php?q=avs" \
	"kat-avs-search.html"

dl	\
	"https://kickass.cd/full/" \
	"kat-full.html"

dl	\
	"https://kickass.cd/new/" \
	"kat-new.html"

dl	\
	"https://kickass.cd/tv/" \
	"kat-tv.html"

rm "$COOKIEJAR"
