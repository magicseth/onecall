# # encoding: utf-8

# from string import Formatter, join

# from datetime import datetime, date
import sqlite3
import os
from oct_constants import FINDERR, NULLNONE, ONEORNONE, ONLYONE
from oct_jsonextended import JSONtoSqlText
from oct_local import dir_path

# import cherrypy
# from strings import AppStringsLANG, permStringsLANG, permStringsVerboseLANG
# from conf import settings
# import smtplib
# from email.mime.text import MIMEText
# from constants import DEBUGSQL
# import time         # For  sleep

# import logging
# logger = logging.getLogger('lumeter')



def getOrInsert(table, name, contactinfo, tags):
    """
    Create a new manufacturer unless name already present
    Return newly created or existing object
    """
    # Err 63 (too many) should never occur since field is unique
    o = cls.find(ONEORNONE, name=name )
    if o is None:
        o = cls.iinsert( name, contactinfo, tags)
    return o
        
def sqlpair(key,val):
    """
    Return a pair of key and value that depends on the type of val and key,
    parmfields should be specified if its possible the key could be in parmfields (e.g. in Record.find)
    """
    # Note this next one is problematic since sqlite3 bug with list as a parameter and cant pass as string or tuple either
    if isinstance(val,(tuple,list,set)):
        return key+" IN ("+','.join(['?']*len(val))+")",  [ v.id() if isinstance(v,Record) else v for v in val ]
    if val is None:                     return key+" IS NULL", [ ]
    if isinstance(val,basestring) and len(val) >= 3 and val[0]=='%' and val[-1] == '%':
        return key+" LIKE ?", [ val ]
    if isinstance(val,basestring):
        (w1,w2) = splitw(val)
        if w1 in ('>','<','>=','<=','!=','<>') and w2 is not None:
            return key+" "+w1+" ?", [ w2 ]
    return  key+" = ?", [ val ]

# This function is to allow quick filtering of lists e.g.  newlist = filter(isNotNone, oldlist)
def isNotNone(foo):
    return foo is not None

def flatten2d(rr):
    return [ leaf for tree in rr for leaf in tree ]  # Super obscure but works and fast
    # See  http://stackoverflow.com/questions/952914/making-a-flat-list-out-of-list-of-lists-in-python/952952#952952

def checkNull(rr, where, nullbehavior):
    """
    Return appropriately based on nullbehavior and size of rr
    where is the inner part of an error message
    lamb is a function that can be applied to anything returned
    nullbehavior controls behavior if field doesn't point to anything
    NULLERR Err 52; NULLNONE - return [ ]  -
    ONLYONE says only ok if exactly one found, and return err 63 if >1 or 52 if none
    ONEORNONE says return obj if found, or None if not, err 63 if >1
    FINDERR - Err 51 if found
    All of these errors should be caught before the user sees them - 51 is (except in createNewAgent),
    52 and 63 still need tracing
    ERR 51,52,63
    """
    if nullbehavior == FINDERR:
        if len(rr) > 0:
                raise UserWarning
        else:
            return None
    if (len(rr) == 0) and (nullbehavior != NULLNONE):
        if nullbehavior == ONEORNONE:
            return None
        else:
            # i.e.. nullbehavior == NULLERR|ONLYONE)
            raise UserWarning
    # Either have >0 objects or 0 objects and NULLNONE
    # Cases where return an object,
    if nullbehavior == ONLYONE or nullbehavior == ONEORNONE:
        if len(rr) == 1:
            return rr[0]
        else:
            raise UserWarning
    # Cases where return an array
    return rr



def splitw(string):
    """
    Utility function to split a string, allowing for it to be None, or just one word
    Always returns a 2-element array, although both, or last element may be None
    """
    if string is None:
        return None,None
    ww = string.rstrip().lstrip().split(None,1)   # This was ' ', changed to None to treat multiple spaces as a word delimiter same as single
    if len(ww) == 0:
        return "",None
    if len(ww) == 1:
        return ww[0],None
    return ww[0],ww[1]



# # ******** GENERIC ROUTINES NOT IN CLASSES ****************
# ## string.Formatter needs to be instanciated once
# F = Formatter()

# def lprint(*params):
#     """
#     Print either to terminal or to log
#     """
#     s = " ".join([unicode(p) for p in params])
#     if testing():
#         try:
#             print s.encode('utf-8')     # Use encode to handle non-ascii characters
#         except UnicodeEncodeError as e:  # persistent annoying Unicode errors 
#             print unicode(e.msg).encode('utf-8')
#     else:
#         logger.info(s)

# def debug(f, *params):
#     """
#     Log if the flag f is True-ish
#     Goes to console if testing(TRUE) has been called
#     often replaced with something like if self.debug: lprint(xyz)   to make sure xyz is only executed if debug is on
#     """
#     if f:
#         # lprint(" ".join([ unicode(i) for i in params]))  # Works fine
#         lprint(*params)

# def debugerr(errno, *params):
#     """
#     Report more detail about an error message for helping debugging
#     This isn't widely used yet. 
#     Note Could make it catch certain errors and treat differently here
#     First parameter should be errno, and 2nd function name
#     """
#     lprint(*("ERROR",errno)+params)

# def trace(a, b, c):
#     """
#     Print out a Log message
#     Convert to unicode as have been passed some things to trace which only cause a bug when the trace happens
#     """
#     lprint(unicode(a) + " " + unicode(b) + " " + unicode(c).replace('\n', '\\n'))


# def assertinstance(obj, cls):
#     assert isinstance(obj, cls), "Expected " + cls.typetable + ", but got " + type(obj).__name__

# # ========= TIME AND DATE MANIPULATION ========

# # These time routines have to be here as called under variety of scenarios - cherry, cgi etc
# # Time is a concept that is set for an input, and the same timestamp used for all processing of that input independent of how long it takes
# def timestamp_set():
#     cherrypy.thread_data.time = getcurrenttime()

# def timestamp():
#     return cherrypy.thread_data.time

# def timestampYMD():
#     return timestamp().strftime('%Y-%m-%d')

# def timestampYMDHM():
#     return timestamp().strftime('%Y-%m-%d %H:%M')

# # Do this before a set of transactions you want to use the same time
# def getcurrenttime() :
#     # cherrypy.thread_data.curs.execute('select current_date as "d [date]", current_timestamp as "ts [timestamp]"')
#     # row = cherrypy.thread_data.curs.fetchone()
#     # return row[1]    # Currenttime
#     # print "date = ", date, " time=", currenttime
#     return datetime.utcnow()

# def sunday(dt) :
#     return datetime.strptime(dt.strftime('%Y-%U-0'), '%Y-%U-%w')  # Convert to string for first day of week, then back to datetime

# def month(dt) :
#     return date(dt.year, dt.month, 1)
#     #print "XXX92",dt.strftime('%Y-%m-0'),datetime.strptime(dt.strftime('%Y-%m-0'), '%Y-%m-%d')
#     #return datetime.strptime(dt.strftime('%Y-%m-0'), '%Y-%m-%d')  # Convert to string for first day of week, then back to datetime

# # ========= UNSORTED ==============



# # Three handy shortcuts to merge a dic and a string
# def FF(string, dd):  # FF("hello {name}",{"name":"John"}
#     """
#     Format the string using the dd parameters (dict)
#     """
#     #return F.vformat(string, [], dd)
#     if dd:
#         return string.format(**dd)
#     else:
#         return string


# ## TODO: refactor: do not use capital letters for functions
# def S(key, kargs, langhint=None):  # S("hellowworldprompt",{"name":"John"}, contact)
#     """
#     Format the string [key] using the dd parameters (dict) according the language
#     langhint can be a integer language number; phone number; or anything with language() method (e.g. Entity or Contact or CherryRun).
#     """
#     # Avoid cyclic dependencies: hint2lang
#     from models.record import hint2lang
#     # Return a string, filled in
#     #print "langhint=",langhint,"h2l=",hint2lang(langhint)
#     #return F.vformat(AppStringsLANG[hint2lang(langhint)][key], [], kargs)
#     if kargs:
#         return AppStringsLANG[hint2lang(langhint)][key].format(**kargs)
#     else:
#         return AppStringsLANG[hint2lang(langhint)][key]

# def permString(permid, verbose, langhint=None):
#     # Avoid cyclic dependencies: hint2lang
#     from models.record import hint2lang
#     if isinstance(permid, (list, tuple)):
#         return " or ".join([permString(p, verbose, langhint) for p in permid ])
#     if verbose:
#         return permStringsVerboseLANG[hint2lang(langhint)][permid]
#     else:
#         return permStringsLANG[hint2lang(langhint)][permid]

# def testing(flag=None):
#     if flag is not None:
#         settings.TESTING = flag
#     return settings.TESTING


# def rows2unicode(r):
#     return " ".join([("%s:%s" % (i, unicode(r[i]).replace('\n', '\\n'))) for i in r.keys()])


# def saferconnect_db():
#     """
#     Encapsulate connection to DB through a process that can delay if locked.
#     """
#     retrytime = 0.001       # Start with 1mS, might be far too short
#     while retrytime < 60: # Allows up to about 60 seconds of delay - enough for a long OVP generation
#         try:
#             connect_db()
#         except sqlite3.OperationalError as e:
#             if 'database is locked' not in str(e):
#                 break   # Drop out of loop and raise error
#             debug(True, "Waiting for lock", retrytime)
#             time.sleep(retrytime)
#             retrytime *= 2          # Try twice as long each iteration
#         except Exception as e:
#             break   # Drop out of loop and raise error
#         else: # No exception
#             return
#     raise e



# def realipaddr():
#     if "X-Forwarded-For" in cherrypy.request.headers:
#         return cherrypy.request.headers["X-Forwarded-For"]
#     elif "Remote-Addr" in cherrypy.request.headers:
#         return cherrypy.request.headers["Remote-Addr"]
#     else:
#         return "UNKNOWN"

# def mail(to_addrs,subject,content):
#     """
#     Send an email
#     to_addrs is an array or list
#     Currently subject is ignored
#     Usage: mail(["one@one.com","two@two.net"],"Title of Mess","line1\nline2")
#     """
#     from_addr=settings.MAIL_FROM
#     smtp_server=settings.SMTP_SERVER
#     # We must choose the body charset manually
#     for body_charset in 'US-ASCII', 'ISO-8859-1', 'UTF-8':
#         try:
#             content.encode(body_charset)
#         except UnicodeError:
#             pass
#         else:
#             break
#     if smtp_server is None:
#         smtp_server = 'localhost'  # Default to same machine
#     #constructing a RFC 2822 message
#     # Create the message ('plain' stands for Content-Type: text/plain)
#     msg = MIMEText(content.encode(body_charset), 'plain', body_charset)
#     #msg = MIMEText(content)
#     msg['From'] = from_addr
#     msg['To'] = ','.join(to_addrs)
#     msg['Subject'] = subject
#     try:
#         s = smtplib.SMTP_SSL(smtp_server)   # Going to port 465 by default
#         s.sendmail(to_addrs=to_addrs, from_addr=from_addr, msg=msg.as_string())
#         s.quit()
#         return True
#     except Exception:
#         return False


# def alert(subject, message):
#     """
#     XXX probably a better way to do alerts using "logging" but that module has been so confusingly settup not sure to do that ...
#     """
#     mail(["mitra@mitra.biz"],subject,message)  # XXX Configure this better  = e.g. email address






# def sqlFetch1(sql, parms=None, verbose=DEBUGSQL):
#     """
#     Encapsulate most access to the sql server
#     Send a sql string to a server, with parms if supplied

#     sql: sql statement that may contain usual "?" characters
#     verbose: set to true to print or log sql executed
#     parms[]: array or list of parameters to sql

#     returns one row (which behave like a dict) as supplied by fetchone
#     """
#     sqlSend(sql, parms, verbose)  # Will always return -1 on SELECT
#     r = cherrypy.thread_data.curs.fetchone()
#     debug(verbose,
#           "None" if r is None else join([unicode(r[k]) for k in r.keys() ] )
#     )
#     return r

# def rows2array(headers,rr):
#     """
#     Extract items from rr corresponding to headers
#     rr is a collection of sqlite rows
#     Header is an OrderedDict where items are either RowName: field  or RowName: field lambda funct
#     Returns an array of arrays
#     """
#     report_rows = []
#     for raw_row in rr:
#         report_row = []
#         for k, v in headers.items():
#             if isinstance(v, tuple):
#                 if isinstance(v[0], tuple):
#                     report_row.append(v[1]([raw_row[x] for x in v[0]]))
#                 else:
#                     report_row.append(v[1](raw_row[v[0]]))
#             else:
#                 report_row.append(raw_row[v])
#         report_rows.append(report_row)
#     return report_rows

# def rows2res(headers, rr):
#     """
#     Helper function for report generation in cherryRun
#     returns a serialisable "res" either empty or including headers and an array of arrays
#     """
#     if len(rr):
#         ## headers is a (ordered) dict, mapping the headers of the columns to display
#         ## to the DB table column name.
#         ## For values that need to be processed: the value of the dict can be
#         ## a 2-tuple of (<field_name>, <process_function>)
#         res = {
#             "success": True,
#             "results": rows2array(headers, rr),
#             "headers": headers.keys()
#         }
#     else:
#         ## No transactions: empty report
#         res = {
#             "success": True
#         }
#     return res

# def defaults(x, default):
#     """
#     shortcut to return a default value if x is None
#     """
#     return default if x is None else x

# def printArrObj(rr):
#     """
#     For use in debugging
#     """
#     print([r.__unicode__() for r in rr])


# def name(r):
#     if r is None:
#         return "None"
#     else:
#         return r.name()
    
# def sumSimilarForPie(arr):
#     keys = []
#     sums = {}
#     for k,s in arr:
#         if k not in keys:
#             keys.append(k)
#             sums[k] = 0
#         sums[k] += s
#     keys.sort()
#     return [(k,sums[k]) for k in keys]

# def dictdiff(r1, r2):
#     # Utility to (destructivly) compare two dict,
#     # leaves r1 and r2 with just different elements
#     k1 = r1.keys()
#     k2 = r2.keys()
#     k1.sort();
#     k2.sort();
#     for k in k1:
#         f1 = r1[k]
#         f2 = r2.get(k,None)
#         if f1 == f2 or not f2: del r2[k]
#         if f1 == f2 or not f1: del r1[k]

# # ========= OPERATIONS OVER A LIST OF RECORDS =======
# def names(rr):
#     return ", ".join([r.name() for r in rr])

