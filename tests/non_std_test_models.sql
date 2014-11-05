pragma foreign_keys='on';

CREATE TABLE source (
	id INTEGER NOT NULL,
    name VARCHAR NOT NULL,
	episode_id INTEGER,
	PRIMARY KEY (id),
	FOREIGN KEY(episode_id) REFERENCES episode (id) ON DELETE SET NULL
);

CREATE TABLE episode (
	id INTEGER NOT NULL,
    name VARCHAR NOT NULL,
	PRIMARY KEY (id)
);

CREATE TABLE selection (
	id INTEGER NOT NULL,
	source_id INTEGER NOT NULL,
	episode_id INTEGER NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(source_id) REFERENCES source (id) ON DELETE cascade,
	FOREIGN KEY(episode_id) REFERENCES episode (id) ON DELETE cascade
);

insert into episode (id, name) values(1, 'Episode A');
insert into episode (id, name) values(2, 'Episode B');
insert into source (id, episode_id, name) values(1, 1, 'Source A');
insert into source (id, episode_id, name) values(2, 2, 'Source A');
insert into selection (episode_id, source_id) values(1, 1);
insert into selection (episode_id, source_id) values(2, 2);


select "-";
select * from source;
select "-";
delete from episode where id=1;
select "-";
select * from source;
select "-";
insert into episode (id, name) values(1, 'Episode A');

select count(*) from selection;
delete from source where id=1;
select count(*) from selection;


select count(*) from selection;
delete from episode where id=2;
select count(*) from selection;
