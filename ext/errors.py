"""
def dummy_func():
  print 'dummy_func is called !'
"""
  
class Error(Exception):
  '''
  Base class for exceptions in the project.
  Attributes:
      msg  -- explanation of the error
  '''
  def __init__(self, msg, data):
    self.msg = msg
    self.data = data
  def __str__(self):
    return repr(self.msg)
#########################  Ruleparser Errors ###################################
class ParseError(Error):
  '''
  Exception raised for errors while parsing walkrule or itjobrule xmlfiles.
  (due to unexpected json format; basically due to dict or list transfers btw objects)
  '''
  pass
#######################  Errors in control_comm_intf ###############################
class UnknownCommPairError(Error):
  '''
  Exception raised when an unexpected comm_pair is registered to control_comm_intf.
  '''
  pass
  
class UnrecogedCommPairError(Error):
  '''
  Exception raised when an unreged comm_pair is tried to be unreged.
  '''
  pass
  
###################  Comm Errors btw Scher - Acter #############################
class ScherActer_CommError(Error):
  '''
  Exception raised for errors in the communication messages between Scher and Acter.
  (due to protocol violation)
  #Communication protocol is simply defined as;
  msg = {'type':... , 'data':...}
    type -- type of msg
    data -- actual content of the msg
  '''
  pass
  
class CorruptMsgError(ScherActer_CommError):
  '''
  Exception raised when data exchanged between Scher and Acter is corrupt.
  e.g. KeyError while getting 'type' or 'data'
  '''
  pass

class MsgTypeError(ScherActer_CommError):
  '''
  Exception raised when msg_type exchanged between Scher and Acter is not recognized.
  #Possible msg_types:
   - s_sching_dec
   - ... 
  '''
  pass
  
class MsgDataError(ScherActer_CommError):
  '''
  Exception raised when msg_data exchanged between Scher and Acter is not valid.
  '''
  pass
  
class UnexpectedClientError(ScherActer_CommError):
  '''
  Exception raised when a msg is rxed over the assigned port by either Scher or 
  Acter from an unexpected client.
  '''
  pass
###############################  OOO  ##########################################

