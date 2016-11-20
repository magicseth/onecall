import json

"""
This subclass extends to allow serialization of objects and provides the obvious extension that JSONEncoder lacks

To use it, just implement for_json()  on any class you want to return in JSON.
Note any attributes should match those expected by lumeter.js

"""

class JSONExtended(json.JSONEncoder):

    def default(self,obj):
        """
        Called by the encoder for any unrecognized types, which includes objects
        Will trigger an error if no for_json exists or it generates an error, and then the default JSONEncoder will get a try
        Currently - for_json is defined for Value, Unit,
        """
        try:
            return obj.for_json()
        except Exception as e:
            pass
            #raise e  # Comment out unless debugging
        return json.JSONEncoder.default(self, obj)  # Allow base class to raise TypeError


class JSONtoSqlText(json.JSONEncoder):

    def default(self,obj):
        """
        Called by the encoder for any unrecognized types, which includes objects
        Will trigger an error if no for_json exists or it generates an error, and then the default JSONEncoder will get a try
        Currently - for_json is defined for Value, Unit,
        """
        from models.record import Record
        if isinstance(obj,Record):
            return obj.id()   # Return as an integer
        else:
            try:
                return obj.for_json()
            except Exception as e:
                pass
                #raise e  # Comment out unless debugging
            return json.JSONEncoder.default(self, obj)  # Allow base class to raise TypeError
