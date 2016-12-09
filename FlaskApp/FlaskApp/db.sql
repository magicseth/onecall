drop table if exists call; 
-- call must come first because of foreign key dependency!
drop table if exists campaign;
drop table if exists caller;
drop table if exists login;
drop table if exists call_old; 
drop table if exists campaign_old;
drop table if exists caller_old;
drop table if exists login_old;

CREATE TABLE caller (
  id integer PRIMARY KEY AUTOINCREMENT NOT NULL,
  phone text UNIQUE NOT NULL,
  zipcode text,
  calltime text,
  active integer,
  preference integer
) ;

CREATE TABLE campaign (
  id integer PRIMARY KEY AUTOINCREMENT NOT NULL,
  message text,
  startdate int,
  enddate int,
  callobjective integer,
  offices text,
  targetparties text,
  targetname text,
  targetphone text
) ;

CREATE TABLE call (
  id integer PRIMARY KEY AUTOINCREMENT NOT NULL,
  tstamp timestamp NOT NULL,
  callerid integer NOT NULL REFERENCES caller(id),
  campaignid integer NOT NULL REFERENCES campaign(id),
  targetphone text,
  targetname text,
  targetoffice text,
  status text,
  duration text,
  recording text
) ;

CREATE TABLE login (
  id integer PRIMARY KEY AUTOINCREMENT NOT NULL,
  username text UNIQUE NOT NULL,
  passhash integer NOT NULL
) ;