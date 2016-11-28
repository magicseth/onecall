drop table if exists call; 
-- call must come first because of foreign key dependency!
drop table if exists campaign;
drop table if exists caller;

CREATE TABLE caller (
  id integer PRIMARY KEY AUTOINCREMENT NOT NULL,
  phone text UNIQUE NOT NULL,
  zipcode text,
  calltime text,
  active integer
) ;

CREATE TABLE campaign (
  id integer PRIMARY KEY AUTOINCREMENT NOT NULL,
  message text,
  startdate int,
  enddate int,
  callobjective integer,
  offices text,
  targetparties text
) ;

CREATE TABLE call (
  id integer PRIMARY KEY AUTOINCREMENT NOT NULL,
  tstamp text NOT NULL,
  callerid integer NOT NULL REFERENCES caller(id),
  campaignid integer NOT NULL REFERENCES campaign(id),
  targetphone text,
  targetname text,
  targetoffice text
) ;