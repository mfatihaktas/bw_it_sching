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
SLACKFEASIBILITYCONST = 1

class SchingOptimizer:
  def __init__(self, sessions_beingserved_dict, actual_res_dict, sid_res_dict):
    logging.basicConfig(filename='logs/schinglog',filemode='w',level=logging.DEBUG)
    #logging.basicConfig(level=logging.INFO)
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
    self.add_proccomp__update_parism_info()
    self.add_sessionpathlinks_with_ids()
    self.add_sessionpathitrs_with_ids()
    #To deal with FEASIBILITY (due to small slackmetric) problems
    self.feasibilize_schinginfo()
    #
    self.print_optimizer()
    # scalarization factor
    self.scal_var = cp.Parameter(name='scal_var', sign='positive')
    # optimization variable vector: tt_epigraph_form_tracer
    self.tt = cp.Variable(1,self.N, name='tt')
    # SESSION ALLOC MATRIX
    self.a = expr((2,self.N))
    self.r_soft_grain = 100
    #RESOURCE ALLOC for each diff path of sessions; modeling parameter
    self.max_numspaths = self.get_max_numspaths()
    self.p_bw = cp.Variable(self.N,self.max_numspaths, name='p_bw')
    self.max_numitfuncs = 2
    self.s_n = cp.Variable(self.N, self.max_numitfuncs, name='s_n')
    self.p_proc = expr((self.N, self.max_numspaths))
    #self.p_dur = expr((self.N, self.max_numspaths))
    #RESOURCE ALLOC for each session; modeling parameter
    self.r_bw = expr((self.N, self.num_link))
    #
    self.r_bw__p_bw_map()
    
    self.r_proc2 = expr((self.N, self.num_itr))
    #self.r_dur2 = expr((self.N, self.num_itr))
    '''
    Problem:
    Intersection of s_path_itres sets become a bug for speculation
    - Especially critical when s_parism_level < num_spaths
    Solution:
    Encode 3-dim matrix (s_id x p_id x r_id) by repeating 2-dim matrix r_(s_id x r_id)
    redundantly as max_parismlevel times.
    '''
    self.max_parismlevel = self.get_max_parismlevel()
    self.r_proc = cp.Variable(self.N*self.max_parismlevel,self.num_itr,name='r_proc')
    #self.r_dur = cp.Variable(self.N*self.max_parismlevel,self.num_itr,name='r_dur')
    #
    self.p_procdur__r_procdur_map()
    self.r_proc2dur2__r_procdur_map()
    self.a__p_bwprocdur_map()
    #to check min storage requirement for staging
    #self.r_stor = expr((1, self.num_itr))
    #self.r_stor__r_durXs_bw_map()
    #to find out actual stor used by <bw_vector, dur_vector>
    #self.r_stor_actual = [0]*self.num_itr #list index: res_id
    #
    self.sp_tx = expr((self.N,self.max_numspaths))
    self.sp_proc = expr((self.N,self.max_numspaths))
    #self.sp_dur = expr((self.N,self.max_numspaths))
    self.sp_trans = expr((self.N,self.max_numspaths))
    self.fill__sp_txprocdurtrans_matrices()
    #To avoid re-run of r_hard&soft stuff
    self.r_hard_vector = expr((1, self.N))
    self.r_soft_vector = expr((1, self.N))
    self.s_pen_vector = expr((1, self.N))
    self.s_util_vector = expr((1,self.N))
    self.fill__r_hardsoft__s_penutil_vectors()
    #
    #self.print_optimizer()
    #To keep SCHING DECISION in a dict
    self.session_res_alloc_dict = {'general':{},'s-wise': {}, 'res-wise': {}}
  ###
  #modeling functions
  def txprocdurtrans_time_model(self,s_id,p_id, datasize,comp_list,num_itres):
    #datasize: MB, bw: Mbps
    tx_t = (8*datasize)*cp.inv_pos(BWREGCONST*self.p_bw[s_id,p_id]) # sec
    #proc: Mbps
    numitfuncs = len(comp_list)
    quadoverlin_vector = expr((1, numitfuncs))
    for i,comp in enumerate(comp_list):
      quadoverlin = comp*cp.quad_over_lin(self.s_n[s_id, i], self.p_proc.get((s_id,p_id)) )
      quadoverlin_vector.set_((0,i), quadoverlin)
    #
    quadoverlin = (quadoverlin_vector.agg_to_column()).get((0,0))
    
    proc_t = num_itres* (8*datasize)*(quadoverlin) # sec
    
    stage_t = 0 #self.p_dur.get((s_id,p_id))
    #
    #trans_t = tx_t + proc_t + stage_t
    #trans_t = cp.max(tx_t, proc_t)
    trans_t = tx_t + proc_t
    
    return [tx_t, proc_t, stage_t, trans_t]
  
  def R_hard(self, s_id):
    '''
    total_trans_time = max{ trans_time over each par_walk}
    '''
    s_pl = self.sessions_beingserved_dict[s_id]['req_dict']['parism_level']
    ptranst_list = []
    for p_id in range(0,s_pl):
      ptranst_list.append(self.sp_trans.get((s_id,p_id)) )
    #
    if s_pl == 1:
      return ptranst_list[0]
    else:
      return cp.max(*ptranst_list)
    '''
    if s_pl == 1:
      return self.sp_trans.get((s_id, 0))
    else:
      return cp.max(*self.sp_trans.get_row(s_id))
    '''
  
  def R_soft(self, s_id):
    tempexpr = expr((1, self.max_numitfuncs))
    for i in range(self.max_numitfuncs):
      tempexpr.set_((0,i), self.s_n[s_id, i])
    #
    totaln = self.sumlist(tempexpr.get_row(0))
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
    #return m_p*(expr_-x_p)
    return cp.max( *(m_p*(expr_-x_p),0) )
    
  def U(self, s_id, expr_):
    m_u = self.sessions_beingserved_dict[s_id]['app_pref_dict']['m_u']
    x_u = self.sessions_beingserved_dict[s_id]['app_pref_dict']['x_u']
    #return max( vstack(( m_u*(expr_-x_u),0 )) )
    #return min( vstack(( -1*m_u*(expr_-x_u),0 )) )
    return m_u*(expr_-x_u)

  # objective functions
  def F0(self):
    return cp.max( *(self.s_pen_vector.get_row(0)) )

  def F1(self):
    return cp.min( *(self.s_util_vector.get_row(0)) )
    
  def F(self):
    return self.F0() - self.scal_var*self.F1()
  ###
  def sumlist(self, l):
    '''
    sum_ = None
    for i,e in enumerate(l):
      if i == 0:
        sum_ = e
      else:
        sum_ += e
    return sum_
    '''
    '''
    len_ = len(l)
    temp = cp.Variable(1,len_, name='temp')
    for i,e in enumerate(l):
      temp[0,i] = e
    #
    return cp.sum_entries(temp)
    '''
    return sum(l)
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
  
  def r_proc2dur2__r_procdur_map(self):
    par_proc2 = expr((self.N,self.num_itr))
    par_dur2 = expr((self.N,self.num_itr))
    #
    for r_id in range(0, self.num_itr):
      for s_id in range(0, self.N):
        for pl in range(0, self.max_parismlevel):
          s_id_ = s_id + pl*self.N
          if par_proc2.is_none((s_id,r_id)): #not touched yet
            par_proc2.set_((s_id,r_id), self.r_proc[s_id_,r_id])
            #par_dur2.set_((s_id,r_id), self.r_dur[s_id_,r_id])
          else:
            par_proc2.add_to((s_id,r_id), self.r_proc[s_id_,r_id])
            #par_dur2.add_to((s_id,r_id), self.r_dur[s_id_,r_id])
    self.r_proc2 = par_proc2
    #self.r_dur2 = par_dur2
    self.logger.debug('r_proc2dur2__r_procdur_map::')
    self.logger.debug('r_proc2=\n%s', self.r_proc2)
    #self.logger.debug('r_dur2=\n%s', self.r_dur2)
  
  def get_max_parismlevel(self):
    #finds and returns maximum level of parism among sessions
    max_ = 0
    for s_id in self.sessions_beingserved_dict:
      pl = len(self.sid_res_dict[s_id]['ps_info'])
      #pl = self.sessions_beingserved_dict[s_id]['req_dict']['parism_level']
      if pl > max_:
        max_ = pl
    return max_
  
  def get_max_numspaths(self):
    #finds and returns maximum # of paths between sessions
    max_ = 0
    for s_id in self.sid_res_dict:
      numspaths = len(self.sid_res_dict[s_id]['ps_info'])
      if numspaths > max_:
        max_ = numspaths
    return max_
  
  def a__p_bwprocdur_map(self):
    for i in range(0,self.N):
      self.a.set_((0,i), cp.sum_entries(self.p_bw[i,:]) )
      self.a.set_((1,i), self.sumlist(self.p_proc.get_row(i)) )
      #self.a.set_((2,i), self.sumlist(self.p_dur.get_row(i)) )
    #
    self.logger.debug('a__p_bwprocdur_map:: a=\n%s', self.a)
  
  def r_bw__p_bw_map(self):
    par_ =  expr((self.N, self.num_link))
    #
    for s_id in self.sid_res_dict:
      ps_info_list = self.sid_res_dict[s_id]['ps_info']
      for i in range(0, len(ps_info_list)):
        for l_id in ps_info_list[i]['p_linkid_list']:
          if par_.is_none((s_id,l_id)): #not touched yet
            par_.set_((s_id,l_id), self.p_bw[s_id,i])
          else:
            par_.add_to((s_id,l_id), self.p_bw[s_id,i])
    #
    self.r_bw = par_
    self.logger.debug('r_bw__p_bw_map:: self.r_bw=\n%s', self.r_bw)
  
  def p_procdur__r_procdur_map(self):
    par_proc = expr((self.N,self.max_numspaths))
    par_dur = expr((self.N,self.max_numspaths))
    #
    for s_id in self.sid_res_dict:
      ps_info_dict = self.sid_res_dict[s_id]['ps_info']
      #s_pl = self.sessions_beingserved_dict[s_id]['req_dict']['parism_level']
      #for p_id in range(0, s_pl):
      for p_id in range(0, len(ps_info_dict)):
        p_info_dict = ps_info_dict[p_id]
        for itr_id in p_info_dict['p_itrid_list']:
          itr_id_ = itr_id - self.ll_index - 1
          s_id_ = s_id+p_id*self.N
          if par_proc.is_none((s_id,p_id)) and par_dur.is_none((s_id,p_id)): #not touched yet
            #print 's_id_:%i, itr_id_:%i' % (s_id_,itr_id_)
            par_proc.set_((s_id,p_id), self.r_proc[s_id_,itr_id_])
            #par_dur.set_((s_id,p_id), self.r_dur[s_id_,itr_id_])
          else:
            par_proc.add_to((s_id,p_id), self.r_proc[s_id_,itr_id_])
            #par_dur.add_to((s_id,p_id), self.r_dur[s_id_,itr_id_])
    #
    self.p_proc = par_proc
    #self.p_dur = par_dur
    self.logger.debug('p_procdur__r_procdur_map::')
    self.logger.debug('self.p_proc=\n%s', self.p_proc)
    #self.logger.debug('self.p_dur=\n%s', self.p_dur)
  
  def p_bwprocdur_sparsity_constraint(self):
    '''
    Not all the sessions have equal number of available transfer paths.
    This constraint will indicate this sparsity of p_bw, p_proc, p_dur.
    '''
    s_sparsity_dict = {}
    total_sparsity = 0
    for s_id in self.sid_res_dict:
      #numspaths = len(self.sid_res_dict[s_id]['ps_info'])
      parism_level = self.sessions_beingserved_dict[s_id]['req_dict']['parism_level']
      num_ssparsity = self.max_numspaths-parism_level
      s_sparsity_dict[s_id] = num_ssparsity
      total_sparsity += num_ssparsity
    #print "s_sparsity_dict: ", s_sparsity_dict
    if total_sparsity == 0:
      return []
    else:
      bw_sparsity_list = [0]*total_sparsity
      proc_sparsity_list = [0]*total_sparsity
      dur_sparsity_list = [0]*total_sparsity
      ti = 0
      for s_id in range(0,self.N):
        num_sparsity = s_sparsity_dict[s_id]
        if num_sparsity == 0:
          continue
        pi = self.max_numspaths-num_sparsity
        for i in range(0, num_sparsity):
          bw_sparsity_list[ti+i] = self.p_bw[s_id,pi+i]
          proc_sparsity_list[ti+i] = self.p_proc.get((s_id,pi+i))
          #dur_sparsity_list[ti+i] = self.p_dur.get((s_id,pi+i))
        ti += num_sparsity
      return [cp.vstack(*bw_sparsity_list) == 0] + \
             [cp.vstack(*proc_sparsity_list) == 0] #+ \
             #[cp.vstack(*dur_sparsity_list) == 0]
  
  def r_bwprocdur_sparsity_constraint(self):
    s_rid_notindomain_list = []
    for s_id in range(0, self.N):
      ps_info_dict = self.sid_res_dict[s_id]['ps_info']
      '''
      #r_bw sparsity is already ensured by par_: zeros matrix (in r_bw__p_bw_map())
      for rbw_id in range(0, self.num_link):
        if not (rbw_id in s_info_map['s_linkid_list']):
          const_bw.append(eq(self.r_bw[s_id, rbw_id], 0))
      '''
      #s_pl = self.sessions_beingserved_dict[s_id]['req_dict']['parism_level']
      #when parism_level<num_paths this method does not give correct output by
      #setting s_pl like the above line shows
      s_pl = len(ps_info_dict)
      for p_id in range(0, s_pl):
        p_info_dict = ps_info_dict[p_id]
        for itr_id in range(0, self.num_itr):
          itr_id_ = itr_id + self.ll_index + 1
          if not (itr_id_ in p_info_dict['p_itrid_list']):
            s_rid_notindomain_list.append((s_id, p_id, itr_id))
    #
    num_ = len(s_rid_notindomain_list)
    if num_ == 0:
      return []
    else:
      proc_sparsity_list = [0]*num_
      dur_sparsity_list = [0]*num_
      
      for i,tup in enumerate(s_rid_notindomain_list):
        s_id_ = tup[0]+tup[1]*self.N
        proc_sparsity_list[i] = self.r_proc.get((s_id_, tup[2]))
        #dur_sparsity_list[i] = self.r_dur.get((s_id_, tup[2]))
      #
      return  [cp.vstack(*proc_sparsity_list) == 0] + \
              [cp.vstack(*dur_sparsity_list) == 0]

  def fill__sp_txprocdurtrans_matrices(self):
    for s_id in range(0, self.N):
      s_req_dict = self.sessions_beingserved_dict[s_id]['req_dict']
      s_ds = s_req_dict['data_size']
      s_par_share = s_req_dict['par_share']
      s_pl = s_req_dict['parism_level']
      ps_info = self.sid_res_dict[s_id]['ps_info']
      for p_id in range(0,s_pl):
        num_itres = len(ps_info[p_id]['itres_list'])
        sp_ds = s_ds*s_par_share[p_id]
        
        l_ = self.txprocdurtrans_time_model(s_id = s_id, p_id = p_id,
                                            datasize = sp_ds,
                                            comp_list = [self.func_compconstant_dict[func] for func in s_req_dict['func_list']],
                                            num_itres = num_itres )
        self.sp_tx.set_((s_id,p_id), l_[0])
        self.sp_proc.set_((s_id,p_id), l_[1])
        #self.sp_dur.set_((s_id,p_id), l_[2])
        self.sp_trans.set_((s_id,p_id), l_[3])
    #
    self.logger.debug('fill__sp_txprocdurtrans_matrices::')
    self.logger.debug('self.sp_tx=\n%s', self.sp_tx)
    self.logger.debug('self.sp_proc=\n%s', self.sp_proc)
    #self.logger.debug('self.sp_dur=\n%s', self.sp_dur)
    self.logger.debug('self.sp_trans=\n%s', self.sp_trans)
  
  def fill__r_hardsoft__s_penutil_vectors(self):
    for s_id in range(self.N):
      self.r_hard_vector.set_((0,s_id), self.R_hard(s_id))
      self.r_soft_vector.set_((0,s_id), self.R_soft(s_id))
      s_st = self.sessions_beingserved_dict[s_id]['req_dict']['slack_metric']
      self.s_pen_vector.set_((0,s_id), self.P(s_id, cp.square(self.tt[0,s_id]-s_st)) )
      self.s_util_vector.set_((0,s_id), self.U(s_id, self.r_soft_vector.get((0,s_id)) ) )
    #
    self.logger.debug('fill__r_hardsoft__s_penutil_vectors::')
    self.logger.debug('self.r_hard_vector=\n%s', self.r_hard_vector)
    self.logger.debug('self.r_soft_vector=\n%s', self.r_soft_vector)
    self.logger.debug('self.s_pen_vector=\n%s', self.s_pen_vector)
    self.logger.debug('self.s_util_vector=\n%s', self.s_util_vector)
  
  # Constraint functions
  def tt_epigraph_form_constraint(self):
    # trans_time_i <= tt_i ; i=0,1,2,3,...,N-1
    return [cp.vstack(*self.r_hard_vector.get_row(0)) <= self.tt.T]
  
  def constraint0(self):
    s_n_consts = []
    for i in range(self.max_numitfuncs-1):
      s_n_consts += [self.s_n[:,i] >= self.s_n[:,i+1]]
    #
    
    return [self.p_bw >= 0] + \
           [self.r_proc >= 0] + \
           [self.tt >= 0] + \
           [self.s_n >= 0] + \
           [self.s_n <= 1] + \
           s_n_consts
           #[self.r_dur >= 0] + \
  
  def new_constraint0(self):
    '''
    consts = []
    for i in range(self.N):
      consts += [cp.vstack(*self.sp_proc.get_row(i)) <= cp.vstack(*self.sp_tx.get_row(i))]
    #
    return consts
    '''
    return [cp.vstack(*self.a.get_row(1)) <= cp.vstack(*self.a.get_row(0))]
  
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
  
  def res_cap_constraint(self):
    # resource capacity constraints
    res_id_info_map = self.actual_res_dict['id_info_map']
    # for resource bw
    r_bw_agged_row = self.r_bw.agg_to_row()
    
    r_bw_cap_list = [0]*self.num_link
    for i in range(0, self.num_link):
      r_bw_cap_list[i] = float(res_id_info_map[i]['bw_cap'])
    # for resource proc and stor
    r_proc_agged_row = self.r_proc2.agg_to_row()
    r_proc_cap_list = [0]*self.num_itr
    r_stor_cap_list = [0]*self.num_itr
    for i in range(0, self.num_itr):
      i_corr = i + self.num_link
      r_proc_cap_list[i] = float(res_id_info_map[i_corr]['proc_cap'])
      r_stor_cap_list[i] = float(res_id_info_map[i_corr]['stor_cap'])
    
    #self.logger.debug('res_cap_constraint:: r_bw_agged_row=%s', r_bw_agged_row)
    #self.logger.debug('res_cap_constraint:: r_bw_agged_row.get_row(0)=%s', r_bw_agged_row.get_row(0))

    return  [cp.vstack(*r_bw_agged_row.get_row(0)) <= cp.vstack(*r_bw_cap_list) ] + \
            [cp.vstack(*r_proc_agged_row.get_row(0)) <= cp.vstack(*r_proc_cap_list) ] # + \
            #[cp.vstack(*self.r_stor.get_row(0)) <= cp.vstack(*r_stor_cap_list) ]
  
  def get_var_val(self, name, (i,j) ):
    if self.N == 1:
      return eval('self.%s.value' % name)
    else:
      return eval('self.%s[%s,%s].value' % (name,i,j) )

  def grab_sching_result(self):
    ###S-WISE
    for i in range(self.N):
      s_req_dict = self.sessions_beingserved_dict[i]['req_dict']
      (s_data_size, s_proc_comp, s_slack, s_parism_level) = (
        s_req_dict['data_size'],
        s_req_dict['proc_comp'],
        s_req_dict['slack_metric'],
        s_req_dict['parism_level'] )
      s_app_pref_dict = self.sessions_beingserved_dict[i]['app_pref_dict']
      (s_m_u, s_m_p, s_x_u, s_x_p) = (s_app_pref_dict['m_u'],
                                      s_app_pref_dict['m_p'],
                                      s_app_pref_dict['x_u'],
                                      s_app_pref_dict['x_p'])
      (bw, proc, dur) = (self.a.get((0,i)).value,
                         self.a.get((1,i)).value,
                         0 ) #self.a.get((2,i)).value )
      '''
      print '~~~~~~~~~~~~~~~~~~~~~~~~~~~~'
      print 'self.s_n[i, :].value=%s' % self.s_n[i, :].value
      #print 'sn_list=%s' % [n.value for n in self.s_n[i, :]]
      print 'bw=%s, proc=%s, dur=%s' % (bw, proc, dur)
      print 'trans_t=%s' % self.r_hard_vector.get((0,i)).value
      print 'tt=%s' % self.get_var_val('tt',(0,i))
      print '~~~~~~~~~~~~~~~~~~~~~~~~~~~~'
      '''
      #
      sn_list = [(float(self.s_n[i, k].value)**2) for k in range(len(s_req_dict['func_list']))]
      #
      trans_t = self.r_hard_vector.get((0,i)).value
      tt = self.get_var_val('tt',(0,i))
      [s_itwalkinfo_dict, s_pwalk_dict] = self.get_session_itbundle_dict__walk(i) #[None, None]
      #ittime = self.it_time__basedon_itwalkinfo_dict(s_itwalkinfo_dict)
      #
      s_ps_info = self.sid_res_dict[0]['ps_info']
      num_ps = len(s_ps_info)
      p_bw,p_proc,p_dur = [],[],[]
      sp_txt,sp_proct,sp_durt,sp_transt = [],[],[],[]
      for k in range(0,num_ps):
        p_bw.append(self.get_var_val('p_bw',(i,k)))
        p_proc.append(self.p_proc.get((i,k)).value)
        #p_dur.append(self.p_dur.get((i,k)).value)
        
        sp_txt.append(self.sp_tx.get((i,k)).value)
        sp_proct.append(self.sp_proc.get((i,k)).value)
        #sp_durt.append(self.sp_dur.get((i,k)).value)
        sp_transt.append(self.sp_trans.get((i,k)).value)
      #
      tobeproceddatasize = s_data_size*max(sn_list) #MB
      tobeproceddata_transt = tobeproceddatasize*8/(BWREGCONST_INGRAB*bw) + sp_proct[0] #sec
      #
      self.session_res_alloc_dict['s-wise'][i] = {
        'p_bw':p_bw, 'p_proc':p_proc, 'p_dur':p_dur,
        'bw':bw, 'proc':proc, 'dur':dur, 
        'required_stor':0.001*(bw*dur),
        'tt': tt,
        'trans_time': trans_t,
        'r_soft_perf': self.r_soft_vector.get((0,i)).value,
        'm_u': s_m_u,
        'm_p': s_m_p,
        'x_u': s_x_u,
        'x_p': s_x_p,
        'sn_list': sn_list,
        'slack-tt': abs(s_slack-tt),
        'parism_level': s_parism_level,
        'itwalkinfo_dict': s_itwalkinfo_dict,
        'pwalk_dict': s_pwalk_dict,
        'sp_txt':sp_txt,
        'sp_proct':sp_proct,
        'sp_durt':sp_durt,
        'sp_transt':sp_transt,
        'tobeproceddatasize': tobeproceddatasize,
        'tobeproceddata_transt': tobeproceddata_transt }
    ###RES-WISE
    r_bw_in_row = self.r_bw.agg_to_row()
    r_proc2_in_row = self.r_proc2.agg_to_row()
    #r_dur2_in_row = self.r_dur2.agg_to_row()
    #FOR network links
    for i in range(self.num_link):
      #link_cap total usage
      self.session_res_alloc_dict['res-wise'][i] = {'bw': r_bw_in_row.get((0,i)).value}
      #link_cap-session portion alloc
      self.session_res_alloc_dict['res-wise'][i].update(
        {'bw_salloc_dict': {s_id:e.value for s_id,e in enumerate(self.r_bw.get_column(i)) } } )
    #FOR it-resources
    for i in range(self.num_itr):
      #calculation of actual storage space
      #dur_vector = [e.value for e in self.r_dur2.get_column(i)]
      bw_vector = [e.value for e in self.a.get_row(0)]
      #self.r_stor_actual[i] = np.dot(dur_vector, bw_vector)*0.001
      #res_cap total usage and res_cap-session portion alloc
      self.session_res_alloc_dict['res-wise'][i+self.num_link] = {
        'proc': r_proc2_in_row.get((0,i)).value,
        'proc_salloc_dict': {s_id:e.value for s_id,e in enumerate(self.r_proc2.get_column(i))}
        #'dur': r_dur2_in_row.get((0,i)).value,
        #'dur_salloc_dict': {s_id:e.value for s_id,e in enumerate(self.r_dur2.get_column(i))}
        #'stor_actual': float(self.r_stor_actual[i]),
        #'stor_model': self.r_stor.get((0,i)).value,
      }
    #general info about sching_decision
    self.session_res_alloc_dict['general']['max_numspaths'] = self.max_numspaths
    self.session_res_alloc_dict['general']['ll_index'] = self.ll_index
    #
    return True
  
  def get_session_itbundle_dict__walk(self, s_id):
    def add_nlisttoitrbundle(s_id, p_proc, n_list, itbundle_dict):
      for t_id,t_info in itbundle_dict.items():
        try:
          t_proc = t_info['proc']
        except KeyError: #res may only be there for dur
          continue
        #
        coeff = (t_proc/p_proc)
        {func_list[i]:n for i,n in enumerate(n_list)}
        t_info['itfunc_dict'] = {func_list[i]:coeff*n for i,n in enumerate(n_list)}
      #
    def itbundle_to_datawalk__ordereditbundle(netpath, itbundle):
      #construct data_walk
      walk = netpath
      for itr in itbundle:
        itr_id = self.actual_res_dict['res_id_map'][itr]
        conn_sw = self.actual_res_dict['id_info_map'][itr_id]['conn_sw']
        #
        lasti_conn_sw = len(walk) - walk[::-1].index(conn_sw) - 1
        walk.insert(lasti_conn_sw+1, itr)
        walk.insert(lasti_conn_sw+2, conn_sw)
      #extract it_order info from walk
      itbundle_, i_list = [], []
      i_itr_dict = {}
      for itr in itbundle:
        itr_i = walk.index(itr)
        i_list.append(itr_i)
        i_itr_dict[itr_i] = itr
      i_list.sort()
      itbundle_ = [i_itr_dict[i] for i in i_list]
      #
      return [walk, itbundle_]
    ###
    req_dict = self.sessions_beingserved_dict[s_id]['req_dict']
    ds = req_dict['data_size']
    pl = req_dict['parism_level']
    ps_list = req_dict['par_share']
    pc = req_dict['proc_comp']
    func_list = req_dict['func_list']
    
    psinfo_dict = self.sid_res_dict[s_id]['ps_info']
    
    n_list = [(float(self.s_n[s_id, k].value)**2) for k in range(len(req_dict['func_list']))]
    #n_list = [float(n)**2 for n in (self.s_n[s_id, :])[0] ]
    
    pitwalk_dict, pwalk_dict = {}, {}
    #
    for p_id in range(pl):
      pinfo_dict = psinfo_dict[p_id]
      pitwalk_dict[p_id] = {'itbundle':{}, 'p_info':{}}
      pitbundle_dict = pitwalk_dict[p_id]['itbundle']
      p_info_dict = pitwalk_dict[p_id]['p_info']
      #
      p_proc, p_dur = 0, 0
      for t_id in range(0, self.num_itr):
        s_id_ = s_id + p_id*self.N
        it_proc = float(self.r_proc[s_id_,t_id].value)
        #it_dur = float(self.r_dur[s_id_,t_id].value)
        if it_proc > 0: #Caused problem since session can directly go to c!
          p_proc += it_proc
          t_id_ = t_id + self.ll_index + 1
          it_tag = self.actual_res_dict['id_info_map'][t_id_]['tag']
          try:
            pitbundle_dict[it_tag].update({'proc': it_proc})
          except KeyError:
            pitbundle_dict[it_tag] = {'proc': it_proc}
        #
        '''
        if it_dur > 1:
          p_dur += it_dur
          t_id_ = t_id + self.ll_index + 1
          it_tag = self.actual_res_dict['id_info_map'][t_id_]['tag']
          try:
            pitbundle_dict[it_tag].update({'dur': it_dur})
          except KeyError:
            pitbundle_dict[it_tag] = {'dur': it_dur}
        #
        '''
      #
      p_info_dict['p_proc'] = p_proc
      p_info_dict['p_dur'] = p_dur
      p_info_dict['datasize'] = float(ds)*float(ps_list[p_id])
      p_info_dict['bw'] = self.p_bw[s_id, p_id].value
      p_info_dict['itfunc_dict'] = {func_list[i]:n for i,n in enumerate(n_list)}
      #
      
      add_nlisttoitrbundle(s_id = s_id, p_proc = p_proc,
                           n_list = n_list,
                           itbundle_dict = pitbundle_dict )
      [pwalk_dict[p_id], orded_itbundle] = itbundle_to_datawalk__ordereditbundle(netpath = pinfo_dict['path'], 
                                                                                 itbundle = [t for t in pitbundle_dict] )
      #
    #
    return [pitwalk_dict, pwalk_dict]
  
  def it_time__basedon_itwalkinfo_dict(self, itwalkinfo_dict):
    dict_ = {}
    for p_id,pinfo_dict in itwalkinfo_dict.items():
      p_ttime = 0
      #
      p_ds = pinfo_dict['p_info']['datasize']
      itbundle_dict = pinfo_dict['itbundle']
      for itres,job in itbundle_dict.items():
        #staging time
        try:
          p_ttime += job['dur']
        except KeyError:
          pass
        #procing time
        try:
          p_c = job['comp'] #pinfo_dict['p_info']['totalcomp']
          p_proc = job['proc']
          p_ttime += (p_ds/64)*p_c /p_proc #sec
        except KeyError:
          pass
      #
      dict_[p_id] = p_ttime
    return dict_
  
  # print info about optimization session
  def print_optimizer(self):
    self.logger.info('Optimizer is created with the follows;')
    self.logger.info('sessions_beingserved_dict=\n%s', pprint.pformat(self.sessions_beingserved_dict))
    self.logger.info('actual_res_dict=\n%s', pprint.pformat(self.actual_res_dict))
    self.logger.info('sid_res_dict=\n%s', pprint.pformat(self.sid_res_dict))
  
  def feasibilize_schinginfo(self):
    def trans_time_calc(s_pl,s_ds,s_pc,s_st,p_bw,ps_list):
      ptranst_list = [0]*s_pl
      for pl_id in range(0,s_pl):
        p_ds = 8*s_ds*ps_list[pl_id] #s_ds: in MB
        tx_t = p_ds*1/(BWREGCONST*p_bw[pl_id]) # sec
        ptranst_list.append(tx_t) #+ path_latency
      return __builtin__.max(ptranst_list) #s_transt
    
    self.add_path_sharing_info()
    #
    """
      Find out the min slack metric requirement for the requirements of a session
      to be feasible for the resource allocation optimization process.
    """
    for s_id in range(0, self.N):
      s_req_dict = self.sessions_beingserved_dict[s_id]['req_dict']
      s_pl = s_req_dict['parism_level']
      p_bw = [self.sid_res_dict[s_id]['ps_info'][p_id]['fair_bw'] for p_id in range(0,s_pl)]
      #print '---> s_id:%i' % s_id
      trans_t = trans_time_calc(s_pl = s_pl,
                                s_ds = s_req_dict['data_size'],
                                s_pc = s_req_dict['proc_comp'],
                                s_st = s_req_dict['slack_metric'],
                                p_bw = p_bw,
                                ps_list = s_req_dict['par_share'] )
      min_tt = trans_t*SLACKFEASIBILITYCONST
      slack = s_req_dict['slack_metric']
      #
      if slack < min_tt:
        self.logger.warning('S%s\'s slack_metric is not feasible!\nChanged from:%sms to:%sms', s_id, slack, min_tt)
        self.sessions_beingserved_dict[s_id]['req_dict']['slack_metric'] = min_tt
  
  def get_sching_result(self):
    return self.session_res_alloc_dict
  
  def add_proccomp__update_parism_info(self):
    def total_func_comp(s_id):
      fl = self.sessions_beingserved_dict[s_id]['req_dict']['func_list']
      c = 0
      for f in fl:
        c += self.func_compconstant_dict[f]
      return c
    #
    '''
    def my_min(x,y):
      min_ = x
      if (min_ > y):
        min_ = y
      return min_
    '''
    for s_id in self.sessions_beingserved_dict:
      self.sessions_beingserved_dict[s_id]['req_dict']['proc_comp'] = total_func_comp(s_id)
      s_parism_level = self.sessions_beingserved_dict[s_id]['req_dict']['parism_level']
      numspaths = len(self.sid_res_dict[s_id]['ps_info'])
      if s_parism_level > numspaths:
        self.logger.warning('S%s; Not enough numspaths:%s to provide parism_level:%s!\nparism_level is changed to numspaths', s_id, numspaths, s_parism_level)
        self.sessions_beingserved_dict[s_id]['req_dict']['parism_level'] = numspaths
  
  def add_sessionpathlinks_with_ids(self):
    net_edge = namedtuple("net_edge", ["pre", "post"])
    for s_id in self.sid_res_dict:
      s_linkid_list = []
      for p_id, p_info_dict in self.sid_res_dict[s_id]['ps_info'].items():
        p_linkid_list = []
        for ne_tuple in p_info_dict['net_edge_list']:
          ne = net_edge(pre=ne_tuple[0] ,post=ne_tuple[1])
          l_id = self.actual_res_dict['res_id_map'][ne]
          p_linkid_list.append(l_id)
        p_info_dict.update({'p_linkid_list':p_linkid_list})
        s_linkid_list = list(set(s_linkid_list) | set(p_linkid_list))
      #
      self.sid_res_dict[s_id]['s_info'].update({'s_linkid_list':s_linkid_list})
  
  def add_sessionpathitrs_with_ids(self):
    for s_id in self.sid_res_dict:
      s_itrid_list = []
      for pid, p_info_dict in self.sid_res_dict[s_id]['ps_info'].items():
        p_itrid_list = []
        for itr in p_info_dict['itres_list']:
          itr_id = self.actual_res_dict['res_id_map'][itr]
          p_itrid_list.append(itr_id)
        p_info_dict.update({'p_itrid_list':p_itrid_list})
        s_itrid_list = list(set(s_itrid_list) | set(p_itrid_list))
      #
      self.sid_res_dict[s_id]['s_info'].update({'s_itrid_list':s_itrid_list})
  
  def add_path_sharing_info(self):
    id_info_map_dict = self.actual_res_dict['id_info_map']
    res_id_map_dict = self.actual_res_dict['res_id_map']
    for res in res_id_map_dict:
      try:
        link_tuple = (res.pre, res.post)
        link_counter = 0
        #Every session is counted as num_available_paths user for the resource
        for s_id in range(0,self.N):
          s_pl = self.sessions_beingserved_dict[s_id]['req_dict']['parism_level']
          for p_id in range(0, s_pl):
            p_info_dict = self.sid_res_dict[s_id]['ps_info'][p_id]
            if link_tuple in p_info_dict['net_edge_list']:
              link_counter += 1
        
        res_id = res_id_map_dict[res]
        id_info_map_dict[res_id].update({'num_user':link_counter})
      except AttributeError: #res is not a link
        # not doing anything for now
        pass
    #returning fair bw share for the path
    def give_fair_bw_share(net_edge_list):
      id_info_map = self.actual_res_dict['id_info_map']
      res_id_map = self.actual_res_dict['res_id_map']
      bw_ = float('Inf')
      for net_edge in net_edge_list:
        l_info = id_info_map[res_id_map[net_edge]]
        l_bw = l_info['bw_cap']/l_info['num_user']
        if l_bw < bw_:
          bw_ = l_bw
      
      return bw_
    #Add fair bw allocation between sessions
    #(Currently) fair_bw of a session: Sum of fair_bw share from each session path
    #TODO: If there is supposed to be superority of a particular session over 
    #the bw, fair_bw of each session can be set to accordingly
    for s_id in range(0,self.N):
      s_fair_bw = 0
      s_pl = self.sessions_beingserved_dict[s_id]['req_dict']['parism_level']
      for p_id in range(0, s_pl):
        path_info_dict = self.sid_res_dict[s_id]['ps_info'][p_id]
        p_fair_bw = give_fair_bw_share(path_info_dict['net_edge_list'])
        path_info_dict.update({'fair_bw': p_fair_bw})
        s_fair_bw += p_fair_bw
      
      self.sid_res_dict[s_id]['s_info'].update({'fair_bw':s_fair_bw})
  def solve(self):
    while(1):
      (self.scal_var).value = 100
      #
      '''
      self.logger.debug('------------------------------')
      self.logger.debug('F0()=%s', self.F0())
      self.logger.debug('F0().is_convex()=%s', self.F0().is_convex())
      self.logger.debug('F1()=%s', self.F1())
      self.logger.debug('F1().is_concave()=%s', self.F1().is_concave())
      self.logger.debug('F()=%s', self.F())
      self.logger.debug('F().is_convex()=%s', self.F().is_convex())
      self.logger.debug('------------------------------')
      
      self.logger.debug('XXXXXXXXXXXXXXXXXXXXXXXXXXXXXX')
      self.logger.debug('constraint0=\n%s', self.constraint0())
      self.logger.debug('self.tt_epigraph_form_constraint()=\n%s', self.tt_epigraph_form_constraint())
      self.logger.debug('res_cap_constraint=\n%s', self.res_cap_constraint())
      self.logger.debug('p_bwprocdur_sparsity_constraint=\n%s', self.p_bwprocdur_sparsity_constraint())
      self.logger.debug('r_bwprocdur_sparsity_constraint=\n%s', self.r_bwprocdur_sparsity_constraint())
      self.logger.debug('s_n_sparsity_constraint=\n%s', self.s_n_sparsity_constraint())
      self.logger.debug('XXXXXXXXXXXXXXXXXXXXXXXXXXXXXX')
      '''
      
      p = cp.Problem(cp.Minimize(self.F()),
                     self.constraint0() + \
                     self.tt_epigraph_form_constraint() + \
                     self.res_cap_constraint() + \
                     self.r_bwprocdur_sparsity_constraint()  + \
                     self.p_bwprocdur_sparsity_constraint() + \
                     self.s_n_sparsity_constraint() )
      #print ">>>>>>>>>>>>>>>>>>>>>>>>>>"
      #p.show()
      #print 'p.variables:\n', p.variables
      #print 'p.parameters:\n', p.parameters
      #print 'p.constraints:\n', p.constraints
      #print ">>>>>>>>>>>>>>>>>>>>>>>>>>"
      #
      #print '(p.objective).is_convex(): ', (p.objective).is_convex()
      #print '(p.constraints).is_dcp(): ', (p.constraints).is_dcp()
      #p.options['abstol'] = 1e-4
      #p.options['realtol'] = 1e-4
      '''
      p.options['maxiters'] = 200
      p.options['use_correction'] = False
      p.options['maxiters'] = 500
      p.options['feastol'] = 1e-4
      '''
      t_s = time.time()
      print 'solving...' 
      '''
      opts = {'MAX_ITERS': 100000,
              'USE_INDIRECT': True }
      p.solve(verbose=True, solver=cp.SCS, solver_specific_opts=opts)
      '''
      #'''
      opts = {'maxiters': 500}
      #p.solve(verbose=True, solver=cp.CVXOPT, solver_specific_opts=opts.items())
      p.solve(solver=cp.CVXOPT, solver_specific_opts=opts.items())
      #'''
      #p.solve()
      print 'solved.took %s secs' % (time.time()-t_s)
      print 'status=%s' % p.status
      if p.status == 'solver_error':
        continue
      #
      '''
      self.logger.debug('||||||||||||||||||||||||||||||||||||')
      self.logger.debug('a=\n%s', self.a.value)
      self.logger.debug('p_bw=\n%s', self.p_bw.value)
      self.logger.debug('p_proc=\n%s', self.p_proc.value)
      #self.logger.debug('p_dur=\n%s', self.p_dur.value)
      self.logger.debug('r_bw=\n%s', self.r_bw.value)
      self.logger.debug('r_proc=\n%s', self.r_proc.value)
      #self.logger.debug('r_dur=\n%s', self.r_dur.value)
      self.logger.debug('r_proc2=\n%s', self.r_proc2.value)
      #self.logger.debug('r_dur2=\n%s', self.r_dur2.value)
      '''
      '''
      self.logger.debug('F0().value=%s', self.F0().value)
      self.logger.debug('F1().value=%s', self.F1().value)
      self.logger.debug('F().value=%s', self.F().value)
      #self.logger.debug('tt.value=%s', self.tt.value)
      self.logger.debug('||||||||||||||||||||||||||||||||||||')
      '''
      if self.grab_sching_result():
        break
      #
    #