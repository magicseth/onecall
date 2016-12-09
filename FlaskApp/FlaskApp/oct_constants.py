########### CONSTANTS #######################
# Parameters passed to things that do finds
# Look at the documentation on checkNull in utils
NULLERR = 0 # Error  if no object is found
NULLNONE = 1  # Return empty array if expecting array - if singular, use ONEORNONE for that

ONLYONE = 2  # Return a single value not an array else error if not found, err if >1
FINDERR = 3  # Error 51 if match is found
ONEORNONE = 4 # Return a single value or None, Err if >1

INACTIVE = 0
WEEKDAY = 1
MONDAY = 2

# From https://www.twilio.com/docs/api/twiml/dial
CALLSETUP = 'setup' # INTERNAL
CALLCOMPLETED = 'completed'
CALLANSWERED = 'answered'
CALLBUSY = 'busy'
CALLNOANSWER = 'no-answer'
CALLFAILED = 'failed'
CALLCANCELED = 'canceled'
