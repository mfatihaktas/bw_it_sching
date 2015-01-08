# cvxpy related imports
import cvxpy as cp
import cvxopt
import numpy as np
import sys,pprint,time,logging
#
from collections import namedtuple
import __builtin__
#
from expr_matrix import Expr as expr

BWREGCONST = 1 #0.9 #0.95
BWREGCONST_INGRAB = 1 #0.9 #0.95
SLACKFEASIBILITYCONST = 1 #1.1
IT_HOPE_OVERHEAD = 1 #1.1

'''
class SchingOptimizer:
def __init__(self, sessions_beingserved_dict, actual_res_dict, sid_res_dict):
def r_bw__s_bw_map(self):
def s_procdur__r_procdur_map(self):
def fill__s_txprocdurtranst(self):
def fill__r_hardsoft__s_penutil_vectors(self):
######################################  Modeling functions  ########################################
def txprocdurtrans_time_model(self, s_id, datasize, comp_list, num_itres):
def R_hard(self, s_id):
def R_soft(self, s_id):
def P(self, s_id, expr_):
def U(self, s_id, expr_):
def F0(self):
def F1(self):
def F(self):
#####################################  Constraint functions  #######################################
def tt_epigraph_form_constraint(self):
def constraint0(self):
def res_cap_constraint(self):
def r_bwprocdur_sparsity_constraint(self):
def s_n_sparsity_constraint(self):
#######################################  Support functions  ########################################
def get_var_val(self, name, (i,j) ):
def grab_sching_result(self):
def get_session_itwalk_dict__walk_list(self, s_id):
def it_time__basedon_itwalk_dict(self, itwalk_dict):
def print_sching_optimizer(self):
def feasibilize_sessions_reqs(self):
def get_sching_result(self):
def add_sessionpathlinks_with_ids(self):
def add_sessionpathitrs_with_ids(self):
def add_path_sharing_info(self):
def solve(self):
'''

class SchingOptimizer:
  def __init__(self, sessions_beingserved_dict, actual_res_dict, sid_res_dict):
    # logging.basicConfig(filename='logs/schinglog',filemode='w',level=logging.DEBUG)
    logging.basicConfig(level=logging.INFO)
    self.logger = logging.getLogger('SchingOptimizer')
    #
    self.sessions_beingserved_dict = sessions_beingserved_dict
    self.actual_res_dict = actual_res_dict
    self.sid_res_dict = sid_res_dict
    self.N = len(sessions_beingserved_dict) # num of active transport sessions
    self.k = len(actual_res_dict['id_info_map']) # num of actual resources
    #
    self.ll_index = self.actual_res_dict['overview']['last_link_index']
    self.num_link = self.ll_index + 1
    self.num_itr = self.k - self.num_link
    # func_compconstant_dict; key:function, val:comp_constant (2-8)
    self.func_compconstant_dict = {
      'fft': 5,
      'upsampleplot': 75
    }
    #
    self.add_sessionpathlinks_with_ids()
    self.add_sessionpathitrs_with_ids()
    # To deal with FEASIBILITY (due to small slackmetric) problems
    self.feasibilize_sessions_reqs()
    self.print_sching_optimizer()
    # scalarization factor
    self.scal_var = cp.Parameter(name='scal_var', sign='positive')
    # optimization variable vector: tt_epigraph_form_tracer
    self.tt = cp.Variable(self.N, 1, name='tt')
    self.s_bw = cp.Variable(self.N, 1, name='s_bw')
    self.s_proc = expr((self.N, 1))
    # self.s_dur = expr((self.N, 1))
    self.r_soft_grain = 100
    
    # RESOURCE ALLOC for each session; modeling parameter
    self.max_numitfuncs = 2
    self.s_n = cp.Variable(self.N, self.max_numitfuncs, name='s_n')
    self.r_bw = expr((self.N, self.num_link))
    self.r_bw__s_bw_map()
    #
    self.r_proc = cp.Variable(self.N,self.num_itr, name='r_proc')
    # self.r_dur = cp.Variable(self.N,self.num_itr, name='r_dur')
    #
    self.s_procdur__r_procdur_map()
    # to check min storage requirement for staging
    # self.r_stor = expr((1, self.num_itr))
    # self.r_stor__r_durXs_bw_map()
    # to find out actual stor used by <bw_vector, dur_vector>
    # self.r_stor_actual = [0]*self.num_itr #list index: res_id
    self.s_txt = expr((self.N, 1))
    self.s_proct = expr((self.N, 1))
    # self.s_durt = expr((self.N, 1))
    self.s_transt = expr((self.N, 1))
    self.fill__s_txprocdurtranst()
    # To avoid re-run of r_hard&soft stuff
    self.r_hard_vector = expr((self.N, 1))
    self.r_soft_vector = expr((self.N, 1))
    self.s_pen_vector = expr((self.N, 1))
    self.s_util_vector = expr((self.N, 1))
    self.fill__r_hardsoft__s_penutil_vectors()
    # self.print_sching_optimizer()
    # To keep SCHING DECISION in a dict
    self.session_res_alloc_dict = {'general':{},'s-wise': {}, 'res-wise': {}}

  def r_bw__s_bw_map(self):
    par_ =  expr((self.N, self.num_link))
    
    for s_id in self.sid_res_dict:
      path_info = self.sid_res_dict[s_id]['path_info']
      for l_id in path_info['linkid_list']:
        if par_.is_none((s_id, l_id)): #not touched yet
          par_.set_((s_id, l_id), self.s_bw[s_id, 0])
        else:
          par_.add_to((s_id, l_id), self.s_bw[s_id, 0])
    #
    self.r_bw = par_
    self.logger.debug('r_bw__s_bw_map:: self.r_bw=\n%s', self.r_bw)
  
  def s_procdur__r_procdur_map(self):
    for s_id in self.sid_res_dict:
      path_info_dict = self.sid_res_dict[s_id]['path_info']
      for itr_id in path_info_dict['itrid_list']:
        itr_id_ = itr_id - self.ll_index - 1
        try:
          if self.s_proc.is_none((s_id, 0)): # and self.s_dur.is_none((s_id, 0)): #not touched yet
            self.s_proc.set_((s_id, 0), self.r_proc[s_id, itr_id_])
          else:
            self.s_proc.add_to((s_id, 0), self.r_proc[s_id, itr_id_])
            # self.s_dur.add_to((s_id, 0), self.r_dur[s_id, itr_id_])
        except:
          self.s_proc.add_to((s_id, 0), self.r_proc[s_id, itr_id_])
          # self.s_dur.add_to((s_id, 0), self.r_dur[s_id, itr_id_])
    #
    self.logger.debug('s_procdur__r_procdur_map::')
    self.logger.debug('self.s_proc=\n%s', self.s_proc)
    # self.logger.debug('self.s_dur=\n%s', self.s_dur)
  
  def fill__s_txprocdurtranst(self):
    for s_id in range(0, self.N):
      s_req_dict = self.sessions_beingserved_dict[s_id]['req_dict']
      l_ = self.txprocdurtrans_time_model(s_id = s_id,
                                          datasize = s_req_dict['datasize'],
                                          comp_list = [self.func_compconstant_dict[func] for func in s_req_dict['func_list']],
                                          num_itres = len(self.sid_res_dict[s_id]['path_info']['itr_on_path_list']) )
      self.s_txt.set_((s_id, 0), l_[0])
      self.s_proct.set_((s_id, 0), l_[1])
      #self.s_durt.set_((s_id, 0), l_[2])
      self.s_transt.set_((s_id, 0), l_[3])
    #
    self.logger.debug('fill__s_txprocdurtranst::')
    self.logger.debug('self.s_txt=\n%s', self.s_txt)
    self.logger.debug('self.s_proct=\n%s', self.s_proct)
    #self.logger.debug('self.s_durt=\n%s', self.s_durt)
    self.logger.debug('self.s_transt=\n%s', self.s_transt)
  
  def fill__r_hardsoft__s_penutil_vectors(self):
    for s_id in range(self.N):
      self.r_hard_vector.set_((s_id, 0), self.R_hard(s_id))
      self.r_soft_vector.set_((s_id, 0), self.R_soft(s_id))
      s_st = self.sessions_beingserved_dict[s_id]['req_dict']['slack_metric']
      self.s_pen_vector.set_((s_id, 0), self.P(s_id, cp.square(self.tt[s_id, 0] - s_st)) )
      self.s_util_vector.set_((s_id, 0), self.U(s_id, self.r_soft_vector.get((s_id, 0)) ) )
    #
    self.logger.debug('fill__r_hardsoft__s_penutil_vectors::')
    self.logger.debug('self.r_hard_vector=\n%s', self.r_hard_vector)
    self.logger.debug('self.r_soft_vector=\n%s', self.r_soft_vector)
    self.logger.debug('self.s_pen_vector=\n%s', self.s_pen_vector)
    self.logger.debug('self.s_util_vector=\n%s', self.s_util_vector)
  ######################################  Modeling functions  ########################################
  def txprocdurtrans_time_model(self, s_id, datasize, comp_list, num_itres):
    #datasize: MB, bw: Mbps, proc: Mbps
    tx_t = (8*datasize)*cp.inv_pos(BWREGCONST*self.s_bw[s_id, 0]) # sec
    numitfuncs = len(comp_list)
    quadoverlin_vector = expr((numitfuncs, 1))
    for i, comp in enumerate(comp_list):
      quadoverlin = comp*cp.quad_over_lin(self.s_n[s_id, i], self.s_proc.get((s_id, 0)) )
      quadoverlin_vector.set_((i, 0), quadoverlin)
    #
    quadoverlin_ = (quadoverlin_vector.agg_to_row()).get((0,0))
    
    proc_t = num_itres* (8*datasize)*(quadoverlin_) # sec
    stage_t = 0 #self.s_dur.get((s_id, 0))
    #trans_t = cp.max(tx_t, proc_t)
    trans_t = tx_t + proc_t #+ stage_t
    
    return [tx_t, proc_t, stage_t, trans_t]
  
  def R_hard(self, s_id):
    return self.s_transt.get((s_id, 0))
  
  def R_soft(self, s_id):
    tempexpr = expr((self.max_numitfuncs, 1))
    for i in range(self.max_numitfuncs):
      tempexpr.set_((i, 0), self.s_n[s_id, i])
    #
    totaln = sum(tempexpr.get_column(0))
    return totaln
    #TODO: next line is causing s_n.value to be None after solution. Report as bug !
    #return sum(self.s_n[s_id, :])*self.r_soft_grain

  # modeling penalty and utility functions
  """
    Assumptions for simplicity of the initial modeling attempts;
    * Penalty and utility functions are linear functions passing through
    origin and can be defined by only its 'slope'
    p_s: penalty func slope
    u_s: utility func slope
    --
    App requirements will be reflected to the optimization problem by
    auto-tune of penalty and utility functions (look at report for more)
    In this case, three coupling types will tune 'function slopes' as;
    Tight Coupling: p_s >> u_s
    Loose Coupling: p_s ~ u_s
    Dataflow Coupling: p_s << u_s
  """
  def P(self, s_id, expr_):
    m_p = self.sessions_beingserved_dict[s_id]['app_pref_dict']['m_p']
    x_p = self.sessions_beingserved_dict[s_id]['app_pref_dict']['x_p']
    # return m_p*(expr_-x_p)
    # return cp.max_elemwise( *(m_p*(expr_-x_p), 0) )
    return expr_
    
  def U(self, s_id, expr_):
    m_u = self.sessions_beingserved_dict[s_id]['app_pref_dict']['m_u']
    x_u = self.sessions_beingserved_dict[s_id]['app_pref_dict']['x_u']
    # return max( vstack(( m_u*(expr_-x_u),0 )) )
    # return min( vstack(( -1*m_u*(expr_-x_u),0 )) )
    # return m_u*(expr_-x_u)
    return expr_

  # objective functions
  def F0(self):
    if self.N > 1:
      return cp.max_elemwise( *(self.s_pen_vector.get_column(0)) )
    elif self.N == 1:
      return self.s_pen_vector.get((0, 0))
    else:
      self.logger.error('F0:: erronous N = %s', self.N)
    
  def F1(self):
    if self.N > 1:
      return cp.min_elemwise( *(self.s_util_vector.get_column(0)) )
    elif self.N == 1:
      return self.s_util_vector.get((0, 0))
    else:
      self.logger.error('F1:: erronous N = %s', self.N)
    
  def F(self):
    return self.F0() - self.scal_var*self.F1()
  ###
  '''
  def r_stor__r_durXs_bw_map(self):
    def norm2_square(l):
      #l: python list
      size = len(l)
      if size == 0:
        self.logger.error('r_stor__r_durXs_bw_map:: list is empty')
        sys.exit(0)
      #
      l_ = [None]*size
      for i in range(size):
        l_[i] = cp.square(l[i])
      return self.sumlist(l_)
    # itr_storage requirement modeling for self.r_storstaging
    for i in range(0, self.num_itr):
      #dur_vector = self.r_dur2.get_column(i) #list, 1xN
      bw_vector = self.a.get_row(0) #list, 1xN
      #(|x|^2+|y|^2)/2 >= |x|.|y| >= <x,y>: actual_dur
      upper_bound = (float)(0.001/2)*( norm2_square(bw_vector)+norm2_square(dur_vector) )
      self.r_stor.set_((0,i), upper_bound)
      
      #(0.001/2)*( square(norm2(bw_vector))+square(norm2(dur_vector)) )
      #(0.001/2)*( power_pos(norm2(bw_vector), 2)+power_pos(norm2(dur_vector), 2) )
    self.logger.debug('r_stor__r_durXs_bw_map:: r_stor=\n%s', self.r_stor)
  '''
  #####################################  Constraint functions  #######################################
  def tt_epigraph_form_constraint(self):
    # trans_time_i <= tt_i ; i=0,1,2,3,...,N-1
    return [cp.vstack(*self.r_hard_vector.get_column(0)) <= self.tt]
  
  def constraint0(self):
    s_n_consts = []
    for i in range(self.max_numitfuncs-1):
      s_n_consts += [self.s_n[:, i] >= self.s_n[:, i+1]]
    #
    
    return [self.s_bw >= 0] + \
           [self.r_proc >= 0] + \
           [self.s_n >= 0] + \
           [self.s_n <= 1] + \
           [self.tt >= 0] + \
           s_n_consts
           #[self.r_dur >= 0] + \
  
  def res_cap_constraint(self):
    res_id_info_map = self.actual_res_dict['id_info_map']
    # for resource bw
    r_bw_agged_row = self.r_bw.agg_to_row()
    r_bw_cap_list = []
    for i in range(self.num_link):
      r_bw_cap_list.append(float(res_id_info_map[i]['bw_cap']) )
    # for resource proc and stor
    r_proc_agged_row = []
    for itr_id in range(self.num_itr):
      colsum = 0
      for s_id in range(self.N):
        colsum += self.r_proc[s_id, itr_id]
      r_proc_agged_row.append(colsum)
      
    r_proc_cap_list = []
    # r_stor_cap_list = []
    for i in range(self.num_itr):
      i_ = i + self.num_link
      r_proc_cap_list.append(float(res_id_info_map[i_]['proc_cap']) )
      # r_stor_cap_list.append(float(res_id_info_map[i_]['stor_cap']) )
    
    #self.logger.debug('res_cap_constraint:: r_bw_agged_row=%s', r_bw_agged_row)
    #self.logger.debug('res_cap_constraint:: r_bw_agged_row.get_row(0)=%s', r_bw_agged_row.get_row(0))
    return  [cp.vstack(*r_bw_agged_row.get_row(0)) <= cp.vstack(*r_bw_cap_list) ] + \
            [cp.vstack(*r_proc_agged_row) <= cp.vstack(*r_proc_cap_list) ] # + \
            #[cp.vstack(*self.r_stor.get_row(0)) <= cp.vstack(*r_stor_cap_list) ]
  
  def r_bwprocdur_sparsity_constraint(self):
    sparsity_list = []
    for s_id in range(0, self.N):
      path_info_dict = self.sid_res_dict[s_id]['path_info']
      # for l_id in range(0, self.num_link):
      #   if not (l_id in path_info_dict['linkid_list']):
      #     sparsity_list.append(self.r_bw.get((s_id, l_id)) )
      for itr_id in range(self.num_itr):
        itr_id_ = itr_id + self.ll_index + 1
        if not (itr_id_ in path_info_dict['itrid_list']):
          sparsity_list.append(self.r_proc[s_id, itr_id])
          # sparsity_list.append(self.r_dur[s_id, itr_id])
    #
    if not sparsity_list:
      return [];
    else:
      return  [cp.vstack(*sparsity_list) == 0]
  
  def s_n_sparsity_constraint(self):
    sparsity_list = []
    for s_id in range(self.N):
      funclist_len = len(self.sessions_beingserved_dict[s_id]['req_dict']['func_list'])
      for k in range(funclist_len, self.max_numitfuncs):
        sparsity_list.append(self.s_n[s_id, k])
      #
    #
    if len(sparsity_list) == 0:
      return []
    else:
      return [cp.vstack(*sparsity_list) == 0]
  
  #######################################  Support functions  ########################################
  def get_var_val(self, name, (i,j) ):
    if self.N == 1:
      return eval('self.%s.value' % name)
    else:
      return eval('self.%s[%s,%s].value' % (name,i,j) )

  def grab_sching_result(self):
    ### S-WISE
    for s_id in range(self.N):
      s_req_dict = self.sessions_beingserved_dict[s_id]['req_dict']
      (s_datasize, s_slack) = (
        s_req_dict['datasize'],
        s_req_dict['slack_metric'] )
      s_app_pref_dict = self.sessions_beingserved_dict[s_id]['app_pref_dict']
      (s_m_u, s_m_p, s_x_u, s_x_p) = (s_app_pref_dict['m_u'],
                                      s_app_pref_dict['m_p'],
                                      s_app_pref_dict['x_u'],
                                      s_app_pref_dict['x_p'])
      (bw, proc, dur) = (self.s_bw[s_id, 0].value,
                         self.s_proc.get((s_id, 0)).value,
                         0 ) #self.s_dur.get((s_id,0)).value )
      '''
      print '~~~~~~~~~~~~~~~~~~~~~~~~~~~~'
      print 'self.s_n[s_id, :].value=%s' % self.s_n[s_id, :].value
      #print 'sn_list=%s' % [n.value for n in self.s_n[s_id, :]]
      print 'bw=%s, proc=%s, dur=%s' % (bw, proc, dur)
      print 'trans_t=%s' % self.r_hard_vector.get((s_id, 0)).value
      print 'tt=%s' % self.get_var_val('tt', (s_id, 0))
      print '~~~~~~~~~~~~~~~~~~~~~~~~~~~~'
      '''
      #
      sn_list = [float(self.s_n[s_id, k].value)**2 for k in range(len(s_req_dict['func_list']) ) ]
      
      trans_t = self.r_hard_vector.get((s_id, 0)).value
      tt = self.get_var_val('tt', (s_id, 0))
      [s_itwalk_dict, s_walk_list] = self.get_session_itwalk_dict__walk_list(s_id)
      # ittime = self.it_time__basedon_itwalk_dict(s_itwalk_dict)
      
      s_path_info = self.sid_res_dict[s_id]['path_info']
      tobeproced_datasize = s_datasize*max(sn_list) #MB
      tobeproced_data_transt = tobeproced_datasize*8/(BWREGCONST_INGRAB*bw) + self.s_proct.get((s_id, 0)).value #sec
      #
      self.session_res_alloc_dict['s-wise'][s_id] = {
        'bw':bw, 'proc':proc, 'dur':dur,
        'required_stor':0.001*(bw*dur),
        'tt': tt,
        'trans_time': trans_t,
        'r_soft_perf': self.r_soft_vector.get((s_id, 0)).value,
        'm_u': s_m_u,
        'm_p': s_m_p,
        'x_u': s_x_u,
        'x_p': s_x_p,
        'sn_list': sn_list,
        'slack-tt': abs(s_slack - tt),
        'tt-transt': abs(tt - trans_t),
        'itwalk_dict': s_itwalk_dict,
        'walk_list': s_walk_list,
        's_txt': self.s_txt.get((s_id, 0)).value,
        's_proct': self.s_proct.get((s_id, 0)).value,
        's_durt': 0, #self.s_durt.get((s_id, 0)).value,
        's_transt': self.s_transt.get((s_id, 0)).value,
        'tobeproced_datasize': tobeproced_datasize,
        'tobeproced_data_transt': tobeproced_data_transt 
      }
    
    ### RES-WISE
    r_bw_in_row = self.r_bw.agg_to_row()
    # For network links
    for l_id in range(self.num_link):
      # link_cap total usage
      dict_ = {}
      try:
        dict_['bw'] = r_bw_in_row.get((0, l_id)).value
      except AttributeError:
        dict_['bw'] = r_bw_in_row.get((0, l_id))
      # link_cap-session portion alloc
      bw_salloc_dict = {}
      for s_id, e in enumerate(self.r_bw.get_column(s_id)):
        try:
          bw_salloc_dict[s_id] = e.value
        except AttributeError:
          bw_salloc_dict[s_id] = e
        #
      dict_['bw_salloc_dict'] = bw_salloc_dict
      self.session_res_alloc_dict['res-wise'][l_id] = dict_
      #
    # For it-resources
    for itr_id in range(self.num_itr):
      # calculation of actual storage space
      # dur_vector = [e.value for e in self.r_dur[:, itr_id]]
      # bw_vector = [e.value for e in self.s_bw]
      # self.r_stor_actual[itr_id] = np.dot(dur_vector, bw_vector)*0.001
      
      r_proc_itrid_column, proc_salloc_dict = [], {}
      for s_id in range(self.N):
        r_proc_sid_itrid_val = self.r_proc[s_id, itr_id].value
        r_proc_itrid_column.append(r_proc_sid_itrid_val)
        proc_salloc_dict[s_id] = r_proc_sid_itrid_val
      # res_cap total usage and res_cap-session portion alloc
      self.session_res_alloc_dict['res-wise'][itr_id + self.num_link] = {
        # r_dur_itrid_column = [e.value for e in self.r_dur[:, itr_id]]
        'proc': sum(r_proc_itrid_column),
        'proc_salloc_dict': proc_salloc_dict
        # 'dur': sum(r_dur_itrid_column),
        # 'dur_salloc_dict': {s_id:e.value for s_id, e in enumerate(r_dur_itrid_column)}
        # 'stor_actual': float(self.r_stor_actual[itr_id]),
        # 'stor_model': self.r_stor.get((0, itr_id)).value,
      }
    # General info about sching decision
    self.session_res_alloc_dict['general']['ll_index'] = self.ll_index
  
  def get_session_itwalk_dict__walk_list(self, s_id):
    def add_nlisttoitr_list(s_id, proc, n_list, itr_info_dict):
      for itr_tag, info_dict in itr_info_dict.items():
        try:
          itr_proc = info_dict['proc']
        except KeyError: # Resource may only be there for dur
          continue
        
        coeff = itr_proc/proc
        info_dict['itfunc_dict'] = {func_list[i]:coeff*n for i, n in enumerate(n_list)}
      #
    def itr_list__to__walk_list__ordered_itr_list(net_path_list, itr_list):
      # Construct data_walk
      walk_list = net_path_list
      for itr in itr_list:
        itr_id = self.actual_res_dict['res_id_map'][itr]
        conn_sw = self.actual_res_dict['id_info_map'][itr_id]['conn_sw']
        
        lasti_conn_sw = len(walk_list) - walk_list[::-1].index(conn_sw) - 1
        walk_list.insert(lasti_conn_sw + 1, itr)
        walk_list.insert(lasti_conn_sw + 2, conn_sw)
      # Wxtract it_order info from walk_list
      itr_list_, i_list = [], []
      i_itr_dict = {}
      for itr in itr_list:
        itr_i = walk_list.index(itr)
        i_list.append(itr_i)
        i_itr_dict[itr_i] = itr
      i_list.sort()
      itr_list_ = [i_itr_dict[i] for i in i_list]
      #
      return [walk_list, itr_list_]
    #
    req_dict = self.sessions_beingserved_dict[s_id]['req_dict']
    func_list = req_dict['func_list']
    n_list = [(float(self.s_n[s_id, k].value)**2) for k in range(len(req_dict['func_list']))]
    #
    itwalk_dict = {'itr_info_dict':{}, 'info':{}}
    itr_info_dict = itwalk_dict['itr_info_dict']
    info_dict = itwalk_dict['info']
    
    proc, dur = 0, 0
    for itr_id in range(0, self.num_itr):
      itr_proc = float(self.r_proc[s_id, itr_id].value)
      if itr_proc > 0: # Caused problem since session can directly go to c!
        proc += itr_proc
        itr_id_ = itr_id + self.ll_index + 1
        itr_tag = self.actual_res_dict['id_info_map'][itr_id_]['tag']
        try:
          itr_info_dict[itr_tag].update({'proc': itr_proc})
        except KeyError:
          itr_info_dict[itr_tag] = {'proc': itr_proc}
      
      # itr_dur = float(self.r_dur[s_id, t_id].value)
      # if itr_dur > 1:
      #   dur += itr_dur
      #   t_id_ = t_id + self.ll_index + 1
      #   itr_tag = self.actual_res_dict['id_info_map'][t_id_]['tag']
      #   try:
      #     itr_info_dict[itr_tag].update({'dur': itr_dur})
      #   except KeyError:
      #     itr_info_dict[itr_tag] = {'dur': itr_dur}
      #
    info_dict['proc'] = proc
    info_dict['dur'] = dur
    info_dict['datasize'] = float(req_dict['datasize'])
    info_dict['bw'] = self.s_bw[s_id, 0].value
    info_dict['itfunc_dict'] = {func_list[i]:n for i,n in enumerate(n_list)}
    
    add_nlisttoitr_list(s_id = s_id, proc = proc,
                        n_list = n_list,
                        itr_info_dict = itr_info_dict )
    [walk_list, orded_itr_list] = itr_list__to__walk_list__ordered_itr_list(
      net_path_list = self.sid_res_dict[s_id]['path_info']['path'],
      itr_list = [t for t in itr_info_dict] )
    #
    return [itwalk_dict, walk_list]
  
  def it_time__basedon_itwalk_dict(self, itwalk_dict):
    it_time = 0
    #
    ds = itwalk_dict['info']['datasize']
    itr_info_dict = itwalk_dict['itr_info_dict']
    for itres, job in itr_info_dict.items():
      #staging time
      try:
        it_time += job['dur']
      except KeyError:
        pass
      #procing time
      try:
        pc = job['comp'] #pinfo_dict['p_info']['totalcomp']
        it_time += (ds/64)*pc /job['proc'] #sec
      except KeyError:
        pass
    #
    return it_time
  
  # print info about optimization session
  def print_sching_optimizer(self):
    self.logger.info('Optimizer is created with the follows;')
    self.logger.info('sessions_beingserved_dict=\n%s', pprint.pformat(self.sessions_beingserved_dict))
    self.logger.info('actual_res_dict=\n%s', pprint.pformat(self.actual_res_dict))
    self.logger.info('sid_res_dict=\n%s', pprint.pformat(self.sid_res_dict))
  
  def feasibilize_sessions_reqs(self):
    def tx_time_calc(ds, bw):
      return ds*1/(BWREGCONST*bw) # sec
    #
    self.add_path_sharing_info()
    # Find out the min slack metric requirement for the requirements of a session
    # to be feasible for the resource allocation optimization process.
    for s_id in range(self.N):
      s_req_dict = self.sessions_beingserved_dict[s_id]['req_dict']
      bw = self.sid_res_dict[s_id]['path_info']['fair_bw']
      tx_t = tx_time_calc(ds = s_req_dict['datasize'], 
                          bw = bw )
      min_trans_t = tx_t*SLACKFEASIBILITYCONST
      slack = s_req_dict['slack_metric']
      #
      if slack < min_trans_t:
        self.logger.warning('S%s\'s slack_metric is not feasible!\nChanged from:%sms to:%sms', s_id, slack, min_trans_t)
        s_req_dict['slack_metric'] = min_trans_t
  
  def get_sching_result(self):
    return self.session_res_alloc_dict
  
  def add_sessionpathlinks_with_ids(self):
    net_edge = namedtuple("net_edge", ["pre", "post"])
    for s_id in self.sid_res_dict:
      path_info_dict = self.sid_res_dict[s_id]['path_info']
      linkid_list = []
      for ne_tuple in path_info_dict['edge_on_path_list']:
        l_id = self.actual_res_dict['res_id_map'][net_edge(pre=ne_tuple[0], post=ne_tuple[1])]
        linkid_list.append(l_id)
      
      path_info_dict.update({'linkid_list': linkid_list})
    #
  
  def add_sessionpathitrs_with_ids(self):
    for s_id in self.sid_res_dict:
      itrid_list = []
      path_info_dict = self.sid_res_dict[s_id]['path_info']
      for itr in path_info_dict['itr_on_path_list']:
        itr_id = self.actual_res_dict['res_id_map'][itr]
        itrid_list.append(itr_id)
      
      path_info_dict.update({'itrid_list':itrid_list})
    #
  
  def add_path_sharing_info(self):
    id_info_map = self.actual_res_dict['id_info_map']
    res_id_map = self.actual_res_dict['res_id_map']
    for res in res_id_map:
      try:
        link_tuple = (res.pre, res.post)
        link_counter = 0
        # Every session is counted as num_available_paths user for the resource
        for s_id in range(self.N):
          if link_tuple in self.sid_res_dict[s_id]['path_info']['edge_on_path_list']:
            link_counter += 1
        
        id_info_map[res_id_map[res]].update({'num_user':link_counter})
      except AttributeError: #res is not a link
        pass
    # Returning fair bw share for the path
    def give_fair_bw_share(net_edge_list):
      bw_ = float('Inf')
      for net_edge in net_edge_list:
        l_info = id_info_map[res_id_map[net_edge]]
        l_bw = l_info['bw_cap']/l_info['num_user']
        if l_bw < bw_:
          bw_ = l_bw
      
      return bw_
    # 
    # Add fair bw allocation between sessions
    # (Currently) fair_bw of a session: Sum of fair_bw share from each session path
    # TODO: If there is supposed to be superority of a particular session over 
    # the bw, fair_bw of each session can be set to accordingly
    for s_id in range(self.N):
      path_info_dict = self.sid_res_dict[s_id]['path_info']
      s_fair_bw = give_fair_bw_share(path_info_dict['edge_on_path_list'])
      path_info_dict['fair_bw'] = s_fair_bw
  
  def solve(self):
    (self.scal_var).value = 100
    
    # self.logger.debug('------------------------------')
    # self.logger.debug('F0()= %s', self.F0())
    # self.logger.debug('F0().is_convex()= %s', self.F0().is_convex())
    # self.logger.debug('F1()= %s', self.F1())
    # self.logger.debug('F1().is_concave()= %s', self.F1().is_concave())
    # self.logger.debug('F()=%s', self.F())
    # self.logger.debug('F().is_convex()= %s', self.F().is_convex())
    # self.logger.debug('------------------------------')
    
    # self.logger.debug('XXXXXXXXXXXXXXXXXXXXXXXXXXXXXX')
    # constraint0_txt_list = ['%s' % c for c in self.constraint0()]
    # tt_epigraph_form_constraint_txt_list = ['%s' % c for c in self.tt_epigraph_form_constraint()]
    # res_cap_constraint_txt_list = ['%s' % c for c in self.res_cap_constraint()]
    # r_bwprocdur_sparsity_constraint_txt_list = ['%s' % c for c in self.r_bwprocdur_sparsity_constraint()]
    # s_n_sparsity_constraint_txt_list = ['%s' % c for c in self.s_n_sparsity_constraint()]
    
    # self.logger.debug('constraint0=\n%s', pprint.pformat(constraint0_txt_list ) )
    # self.logger.debug('self.tt_epigraph_form_constraint()=\n%s', pprint.pformat(tt_epigraph_form_constraint_txt_list) )
    # self.logger.debug('res_cap_constraint=\n%s', pprint.pformat(res_cap_constraint_txt_list) )
    # self.logger.debug('r_bwprocdur_sparsity_constraint=\n%s', pprint.pformat(r_bwprocdur_sparsity_constraint_txt_list) )
    # self.logger.debug('s_n_sparsity_constraint=\n%s', pprint.pformat(s_n_sparsity_constraint_txt_list) )
    # self.logger.debug('XXXXXXXXXXXXXXXXXXXXXXXXXXXXXX')
    
    p = cp.Problem(cp.Minimize(self.F()),
                   self.constraint0() + \
                   self.tt_epigraph_form_constraint() + \
                   self.res_cap_constraint() + \
                   self.r_bwprocdur_sparsity_constraint()  + \
                   self.s_n_sparsity_constraint() )
    # p = cp.Problem(cp.Minimize(cp.max_entries(self.tt)),
    #               [self.tt >= 0] + \
    #               self.constraint0() + \
    #               self.tt_epigraph_form_constraint() + \
    #               self.res_cap_constraint() + \
    #               self.r_bwprocdur_sparsity_constraint()  + \
    #               self.s_n_sparsity_constraint() )
    # print ">>>>>>>>>>>>>>>>>>>>>>>>>>"
    # print 'p.variables:\n', p.variables
    # print 'p.parameters:\n', p.parameters
    # print 'p.constraints:\n', p.constraints
    # print 'p.is_dcp(): ', p.is_dcp()
    # print ">>>>>>>>>>>>>>>>>>>>>>>>>>"
    
    # p.options['abstol'] = 1e-4
    # p.options['realtol'] = 1e-4
    # p.options['maxiters'] = 200
    # p.options['use_correction'] = False
    # p.options['maxiters'] = 500
    # p.options['feastol'] = 1e-4
    t_s = time.time()
    print 'solving...' 
    # opts = {'maxiters': 500}
    # p.solve(solver=cp.CVXOPT, verbose=True, solver_specific_opts=opts.items())
    # p.solve(solver=cp.CVXOPT, verbose=True)
    p.solve()
    print 'solved.took %s secs' % (time.time() - t_s)
    print 'p.status= %s' % p.status
    print 'p.value= %s' % p.value
    
    self.grab_sching_result()
    #
