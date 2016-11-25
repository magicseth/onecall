drop table if exists caller;
drop table if exists campaign;
drop table if exists target;
drop table if exists region;
drop table if exists call;

CREATE TABLE caller (
  id integer PRIMARY KEY AUTOINCREMENT NOT NULL,
  phone varchar(25) UNIQUE,
  zipcode varchar(25),
  calltime datetime,
  active integer
) ;

CREATE TABLE campaign (
  id integer PRIMARY KEY AUTOINCREMENT NOT NULL,
  message text,
  startdate date,
  enddate date,
  calltarget integer,
  arenas text
) ;

CREATE TABLE target (
  id integer PRIMARY KEY AUTOINCREMENT NOT NULL,
  name varchar(255),
  phone varchar(25),
  bio text,
  arena varchar(50)
) ;

CREATE TABLE region (
  id integer PRIMARY KEY AUTOINCREMENT NOT NULL,
  zipcode varchar(25),
  targetid integer NOT NULL REFERENCES target(id)
) ;

CREATE TABLE call (
  id integer PRIMARY KEY AUTOINCREMENT NOT NULL,
  timestamp timestamp NOT NULL,
  callerid integer NOT NULL REFERENCES caller(id),
  campaignid integer NOT NULL REFERENCES campaign(id),
  targetid integer NOT NULL REFERENCES target(id)
) ;