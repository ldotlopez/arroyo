#!/bin/bash

D="$(dirname "$(realpath "$0")")"
source "$D/env/bin/activate"
export PYTHONPATH="$PWD"

python3 -c 'import arroyo' || exit 1
[ ! -z "$(which sqlite3)" ] || exit 1

cp "$D/arroyo.db" "$D/arroyo.db.bak"

(
cat << EOF
ALTER TABLE source RENAME TO sourceold;
CREATE TABLE "source" (
	id INTEGER NOT NULL,
	provider VARCHAR NOT NULL,
	name VARCHAR NOT NULL,
	created INTEGER NOT NULL,
	last_seen INTEGER NOT NULL,
	urn VARCHAR,
	uri VARCHAR,
	size INTEGER,
	seeds INTEGER,
	leechers INTEGER,
	type VARCHAR,
	language VARCHAR,
	episode_id INTEGER,
	movie_id INTEGER,
	CONSTRAINT pk_source PRIMARY KEY (id),
	CONSTRAINT fk_source_episode_id_episode FOREIGN KEY(episode_id) REFERENCES episode (id) ON DELETE SET NULL,
	CONSTRAINT fk_source_movie_id_movie FOREIGN KEY(movie_id) REFERENCES movie (id) ON DELETE SET NULL
);
CREATE TABLE download (
	source_id INTEGER NOT NULL, 
	foreign_id VARCHAR NOT NULL, 
	state INTEGER NOT NULL, 
	CONSTRAINT pk_download PRIMARY KEY (source_id), 
	CONSTRAINT fk_download_source_id_source FOREIGN KEY(source_id) REFERENCES source (id) ON DELETE CASCADE, 
	CONSTRAINT uq_download_foreign_id UNIQUE (foreign_id)
);

INSERT INTO source SELECT id,provider,name,created,last_seen,urn,uri,size,seeds,leechers,type,language,episode_id,movie_id
FROM sourceold;

INSERT INTO download select id,'transmission:' || urn, state
FROM sourceold
WHERE state IS NOT NULL AND state > 0;

DROP TABLE sourceold;
.dump
EOF
) | sqlite3 "$D/arroyo.db" > "$D/arroyo-dbdata.sql"
rm "$D/arroyo.db"

alembic upgrade head
sqlite3 "$D/arroyo.db" < "$D/arroyo-dbdata.sql"
rm "$D/arroyo-dbdata.sql"
