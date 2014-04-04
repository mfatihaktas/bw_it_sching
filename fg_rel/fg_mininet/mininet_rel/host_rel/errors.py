class Error(Exception):
  '''
  Base class for exceptions in the project.
  Attributes:
      msg  -- explanation of the error
  '''
  def __init__(self, msg):
    self.msg = msg
  def __str__(self):
    return repr(self.msg)

#########################  Command Line Option Errors  ####################
class CommandLineOptionError(Error):
  '''
  Exception raised for errors occurred in command line option parsing.
  '''
  def __init__(self, msg, data):
    self.data = data
    self.msg = msg
  def __str__(self):
    return repr(self.msg)
#######################
class CorruptMsgError(Error):
  '''
  Exception raised for errors during protocol checking.
  '''
  def __init__(self, msg, data):
    self.data = data
    self.msg = msg
  def __str__(self):
    return repr(self.msg)
#######################
class TransitNodeOpError(Error):
  '''
  Exception raised for errors during the intransit operation done by a transit node.
  '''
  def __init__(self, msg, data):
    self.data = data
    self.msg = msg
  def __str__(self):
    return repr(self.msg)

class UnknownClientError(TransitNodeOpError):
  '''
  Exception raised when sching_job_rule is rxed from an unknown client.
  '''
  pass

class NoItruleMatchError(TransitNodeOpError):
  '''
  Exception raised when data exchanged between Scher and Acter is corrupt.
  e.g. KeyError while getting 'type' or 'data'
  '''
  pass

########################

