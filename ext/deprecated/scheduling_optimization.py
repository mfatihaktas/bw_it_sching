# cvxpy related imports
from cvxpy import *
import pprint
import numpy as np
import sys
#
from collections import namedtuple
import __builtin__

class SchingOptimizer:
  def __init__(self, sessions_beingserved_dict, actual_res_dict,
               sid_res_dict):
    self.sessions_beingserved_dict = sessions_beingserved_dict
    self.actual_res_dict = actual_res_dict
    self.sid_res_dict = sid_res_dict
    self.N = len(sessions_beingserved_dict) # num of active transport sessions
    self.k = len(actual_res_dict['id_info_map']) # num of actual resources
    #
    self.ll_index = self.actual_res_dict['overview']['last_link_index']
    self.num_link = self.ll_index + 1
    self.num_itr = self.k - self.num_link
    """
      Necessary session and modeling info will be kept in arrays or matrices.
      e.g.
      - slack_time(ms), data_size (Mb), latency(ms)
      - func_dict, func_compconstant_dict
    """
    # func_compconstant_dict; key:function, val:comp_constant (2-8)
    self.func_compconstant_dict = {
      'f0':0.5,
      'f1':1,
      'f2':2,
      'f3':3,
      'f4':4
    }
    self.s_pref_dict = {
      0:{'p':1, 'u':1},
      1:{'p':1, 'u':1},
      2:{'p':1, 'u':1}
    }
    #
    self.add_proccomp__update_parism_info()
    self.add_sessionpathlinks_with_ids()
    self.add_sessionpathitrs_with_ids()
    #To deal with FEASIBILITY (due to small slackmetric) problems
    self.feasibilize_schinginfo()
    # scalarization factor
    self.scal_var = parameter(name='scal_var', attribute='nonnegative')
    # optimization variable vector: tt_epigraph_form_tracer
    self.tt = variable(self.N,1, name='tt')
    # SESSION ALLOC MATRIX
    '''
    a[:,i]: [bw_i (Mbps); proc_i (Mflop/s); dur_i (ms); n_i]
    By assuming in-transit host NIC bws are ALWAYS higher than allocated bw:
    stor (Mb) = dur (ms)/1000 x bw (Mbps)
    '''
    self.a = variable(4,self.N, name='a')
    self.n_grain = 100
    #RESOURCE ALLOC for each diff path of sessions; modeling parameter
    self.max_numspaths = self.get_max_numspaths()
    self.p_bw = variable(self.N,self.max_numspaths, name='p_bw')
    self.p_proc = variable(self.N,self.max_numspaths, name='p_proc')
    self.p_dur = variable(self.N,self.max_numspaths, name='p_dur')
    #self.a__p_bwprocdur_map()
    #print "a_1:\n", self.a
    #RESOURCE ALLOC for each session; modeling parameter
    self.r_bw = variable(self.N,self.num_link,name='r_bw')
    #
    self.print_optimizer()
    #
    self.r_bw__p_bw_map()
    self.r_proc2 = parameter(self.N,self.num_itr,name='r_proc2')
    self.r_dur2 = parameter(self.N,self.num_itr,name='r_dur2')
    '''
    Problem:
    Intersection of s_path_itres sets become is a bug for speculation
    - Especially critical when s_parism_level < num_spaths
    Solution:
    Encode 3-dim matrix (s_id-p_id-r_id) by repeating 2-dim matrix r_* (s_id-r_id)
    redundantly as max_parismlevel times.
    '''
    self.max_parismlevel = self.get_max_parismlevel()
    self.r_proc = variable(self.N*self.max_parismlevel,self.num_itr,name='r_proc')
    self.r_dur = variable(self.N*self.max_parismlevel,self.num_itr,name='r_dur')
    self.p_procdur__r_procdur_map()
    self.r_proc2dur2__r_procdur_map()
    self.a__p_bwprocdur_map()
    #to check min storage requirement for staging
    self.r_stor = variable(self.num_itr,1,name='r_stor')
    self.r_stor__r_durXs_bw_map()
    #to find out actual stor used by <bw_vector, dur_vector>
    #will be filled up in grab_sching
    self.r_stor_actual = [0]*self.num_itr #list index: res_id
    #
    self.sp_tx = parameter(self.N,self.max_numspaths, name='sp_tx')
    self.sp_proc = parameter(self.N,self.max_numspaths, name='sp_proc')
    self.sp_dur = parameter(self.N,self.max_numspaths, name='sp_dur')
    self.sp_trans = parameter(self.N,self.max_numspaths, name='sp_trans')
    self.fill__sp_txprocdurtrans_matrices()
    #To avoid re-run of r_hard&soft stuff
    self.r_hard_vector = parameter(self.N,1, name='r_hard_vector')
    self.r_soft_vector = parameter(self.N,1, name='r_soft_vector')
    self.s_pen_vector = parameter(self.N,1, name='s_pen_vector')
    self.s_util_vector = parameter(self.N,1, name='s_util_vector')
    self.fill__r_hardsoft__s_penutil_vectors()
    #
    #self.print_optimizer()
    #To keep SCHING DECISION in a dict
    self.session_res_alloc_dict = {'general':{},'s-wise': {}, 'res-wise': {}}
  
  ################### For Enabling Speculation ###############################
  def r_stor__r_durXs_bw_map(self):
    #
    def norm2_square(v):
      vs = v.shape
      #print 'vs: ', vs
      if vs[1] != 1:
        print 'vector shape is not suitable for norm_square'
        sys.exit(0)
      #if the vector is scalar
      if vs[1] == 1:
        return square(v)
      #
      r_ = parameter(vs[0],1, attribute='nonnegative')
      for i in range(0,vs[0]):
        r_[i,0] = square(v[i,0])
  
      return sum(r_)
    #
    # itr_storage requirement modeling for self.r_storstaging
    for i in range(0, self.num_itr):
      dur_vector = self.r_dur2[:, i] #Nx1
      bw_vector = (self.a[0, :]).T #Nx1
      self.r_stor[i, 0] = \
      (0.001/2)*( norm2_square(bw_vector)+norm2_square(dur_vector) )
      #(0.001/2)*( square(norm2(bw_vector))+square(norm2(dur_vector)) )
      #(0.001/2)*( power_pos(norm2(bw_vector), 2)+power_pos(norm2(dur_vector), 2) )
    #print 'r_stor: ', self.r_stor
  
  def r_proc2dur2__r_procdur_map(self):
    par_proc2 = parameter(self.N,self.num_itr, name = 'par_proc2')
    par_proc2.value = zeros((self.N,self.num_itr))
    par_dur2 = parameter(self.N,self.num_itr, name = 'par_dur2')
    par_dur2.value = zeros((self.N,self.num_itr))
    for r_id in range(0, self.num_itr):
      for s_id in range(0, self.N):
        for pl in range(0, self.max_parismlevel):
          s_id_ = s_id + pl*self.N
          if par_proc2[s_id,r_id].value == 0 and par_dur2[s_id,r_id].value == 0: #not touched yet
            par_proc2[s_id,r_id] = self.r_proc[s_id_,r_id]
            par_dur2[s_id,r_id] = self.r_dur[s_id_,r_id]
          else:
            par_proc2[s_id,r_id] += self.r_proc[s_id_,r_id]
            par_dur2[s_id,r_id] += self.r_dur[s_id_,r_id]
    self.r_proc2 = par_proc2
    self.r_dur2 = par_dur2
    #print 'r_proc2:\n', self.r_proc2
    #print 'r_dur2:\n', self.r_dur2
  
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
    #ones_ = ones((max_spaths,1))
    for i in range(0,self.N):
      self.a[0,i] = sum(self.p_bw[i,:])
      self.a[1,i] = sum(self.p_proc[i,:])
      self.a[2,i] = sum(self.p_dur[i,:])
    #print "a[2,:]:\n", self.a[2,:]

  def r_bw__p_bw_map(self):
    par_ = parameter(self.N,self.num_link, name = 'par_')
    stup_case = False
    if self.N == 1 and self.num_link == 1:
      stup_case = True
      par_.value = 0
    else:
      par_.value = zeros((self.N,self.num_link))
    for s_id in self.sid_res_dict:
      ps_info_list = self.sid_res_dict[s_id]['ps_info']
      for i in range(0, len(ps_info_list)):
        for l_id in ps_info_list[i]['p_linkid_list']:
          if par_[s_id,l_id].value == 0: #not touched yet
            par_[s_id,l_id] = self.p_bw[s_id,i]
          else:
            par_[s_id,l_id] += self.p_bw[s_id,i]
    #
    self.r_bw = par_
    #print "self.r_bw: \n", self.r_bw
  
  def p_procdur__r_procdur_map(self):
    par_proc = parameter(self.N,self.max_numspaths, name = 'par_proc')
    par_proc.value = zeros((self.N,self.max_numspaths))
    par_dur = parameter(self.N,self.max_numspaths, name = 'par_dur')
    par_dur.value = zeros((self.N,self.max_numspaths))
    for s_id in self.sid_res_dict:
      ps_info_dict = self.sid_res_dict[s_id]['ps_info']
      #s_pl = self.sessions_beingserved_dict[s_id]['req_dict']['parism_level']
      #for p_id in range(0, s_pl):
      for p_id in range(0, len(ps_info_dict)):
        p_info_dict = ps_info_dict[p_id]
        for itr_id in p_info_dict['p_itrid_list']:
          itr_id_ = itr_id - self.ll_index - 1
          s_id_ = s_id+p_id*self.N
          if par_proc[s_id,p_id].value == 0 and par_dur[s_id,p_id].value == 0: #not touched yet
            print 's_id_:%i, itr_id_:%i' % (s_id_,itr_id_)
            par_proc[s_id,p_id] = self.r_proc[s_id_,itr_id_]
            par_dur[s_id,p_id] = self.r_dur[s_id_,itr_id_]
          else:
            par_proc[s_id,p_id] += self.r_proc[s_id_,itr_id_]
            par_dur[s_id,p_id] += self.r_dur[s_id_,itr_id_]
    #
    self.p_proc = par_proc
    self.p_dur = par_dur
    #print "self.p_proc: \n", self.p_proc
    #print "self.p_dur: \n", self.p_dur
   
  def p_bwprocdur_sparsity_constraint(self):
    '''
    Not all the sessions have equal number of available transfer paths.
    This constraint will indicate this sparsity of p_bw, p_proc, p_dur.
    '''
    pbw_const_, pproc_const_, pdur_const_ = None, None, None
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
      #Workaround to avoid: 'NoneType' CONSTRAINT has no attribute 'is_dcp'
      dummy_par_ = parameter(0,0, name="par_for_proc" )
      return eq(dummy_par_, 0)
    elif total_sparsity == 1: #only one session has one sparsity in p_bw
      for s_id in range(0,self.N):
        num_sparsity = s_sparsity_dict[s_id]
        if num_sparsity == 0:
          continue
        pi = self.max_numspaths-num_sparsity
        dummy_par = parameter(3,1, name="dummy_par")
        dummy_par[0,0] = self.p_bw[s_id,pi]
        dummy_par[1,0] = self.p_proc[s_id,pi]
        dummy_par[2,0] = self.p_dur[s_id,pi]
        #
        return eq(dummy_par, 0)
    else:
      par_for_bw = parameter(total_sparsity,1, name="par_for_bw" )
      par_for_proc = parameter(total_sparsity,1, name="par_for_proc" )
      par_for_dur = parameter(total_sparsity,1, name="par_for_dur" )
      ti = 0
      for s_id in range(0,self.N):
        num_sparsity = s_sparsity_dict[s_id]
        if num_sparsity == 0:
          continue
        pi = self.max_numspaths-num_sparsity
        '''
        print "s%i" % s_id
        print "ti: ", ti
        print "pi: ", pi
        '''
        for i in range(0, num_sparsity):
          par_for_bw[ti+i,0] = self.p_bw[s_id,pi+i]
          par_for_proc[ti+i,0] = self.p_proc[s_id,pi+i]
          par_for_dur[ti+i,0] = self.p_dur[s_id,pi+i]
        ti += num_sparsity
      return eq(par_for_bw, 0) + \
             eq(par_for_proc, 0) + \
             eq(par_for_dur, 0)
  
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
      #
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
    par_for_proc = parameter(num_,1, name="par_for_proc" )
    par_for_dur = parameter(num_,1, name="par_for_dur" )
    #again to workaround this stupid cvxpy error=TypeError: 'cvxpy_scalar_param' object does not support item assignment
    if num_ == 1:
      for i,tup in enumerate(s_rid_notindomain_list):
        s_id_ = tup[0]+tup[1]*self.N
        par_for_proc = self.r_proc[s_id_, tup[2]]
        par_for_dur = self.r_dur[s_id_, tup[2]]
      inter_par_ = vstack( (par_for_proc, par_for_dur) )
      return eq(inter_par_, 0)
    else:
      for i,tup in enumerate(s_rid_notindomain_list):
        s_id_ = tup[0]+tup[1]*self.N
        par_for_proc[i,0] = self.r_proc[s_id_, tup[2]]
        par_for_dur[i,0] = self.r_dur[s_id_, tup[2]]
      #
      return  eq(par_for_proc, 0) + \
              eq(par_for_dur, 0)

  ###################          OOO             ###############################
  def fill__sp_txprocdurtrans_matrices(self):
    if self.N == 1 and self.max_numspaths == 1: #to workaround [0,0] indexing problem of cvxpy_scalars
      s_req_dict = self.sessions_beingserved_dict[0]['req_dict']
      s_ds = s_req_dict['data_size']
      s_par_share = s_req_dict['par_share']
      sp_ds = s_ds*s_par_share[0]
      num_itres = len(self.sid_res_dict[0]['ps_info'][0]['itres_list'])
      l_ = self.txprocdurtrans_time_model(s_id = 0, p_id = 0,
                                          datasize = sp_ds,
                                          pcomp = s_req_dict['proc_comp'],
                                          num_itres = num_itres)
      self.sp_tx = l_[0]
      self.sp_proc = l_[1]
      self.sp_dur = l_[2]
      self.sp_trans = l_[3]
    else:
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
                                              pcomp = s_req_dict['proc_comp'],
                                              num_itres = num_itres)
          self.sp_tx[s_id,p_id] = l_[0]
          self.sp_proc[s_id,p_id] = l_[1]
          self.sp_dur[s_id,p_id] = l_[2]
          self.sp_trans[s_id,p_id] = l_[3]
    '''
    #printout
    print 'self.sp_tx:\n', self.sp_tx
    print 'self.sp_proc:\n', self.sp_proc
    print 'self.sp_dur:\n', self.sp_dur
    print 'self.sp_trans:\n', self.sp_trans
    '''
  
  def fill__r_hardsoft__s_penutil_vectors(self):
    if self.N == 1: #to workaround [0,0] indexing problem of cvxpy_scalars
      self.r_hard_vector = self.R_hard(0)
      self.r_soft_vector = self.R_soft(0)
      #
      s_st = self.sessions_beingserved_dict[0]['req_dict']['slack_metric']
      self.s_pen_vector = self.P(0, square(self.tt-s_st))
      self.s_util_vector = self.U(0, self.r_soft_vector)
    else:
      for s_id in range(0, self.N):
        self.r_hard_vector[s_id,0] = self.R_hard(s_id)
        self.r_soft_vector[s_id,0] = self.R_soft(s_id)
        #
        s_st = self.sessions_beingserved_dict[s_id]['req_dict']['slack_metric']
        self.s_pen_vector[s_id,0] = self.P(s_id, square(self.tt[s_id,0]-s_st))
        self.s_util_vector[s_id,0] = self.U(s_id, self.r_soft_vector[s_id,0])
    '''
    #printout
    print 'self.r_hard_vector: \n', self.r_hard_vector
    print 'self.r_soft_vector: \n', self.r_soft_vector
    print 'self.s_pen_vector: \n', self.s_pen_vector
    print 'self.s_util_vector: \n', self.s_util_vector
    '''
  
  # Constraint modeling functions
  def tt_epigraph_form_constraint(self):
    # trans_time_i <= tt_i ; i=0,1,2,3,...,N-1
    return leq(self.r_hard_vector, self.tt)
  
  def constraint0(self):
    #TODO: Experiment with bw & proc lower bound to see if dur will take action in sching.
    #a[0,:] >= bw_lb + a[1,:] >= proc_lb + a[2:3,:] >= 0
    #bw_lb = 0
    #proc_lb = 0
    #
    #a >= 0 + tt >= 0 + n_i <= length(func_list_i)
    #r_bw >= 0 + r_proc >= 0 + r_stor >= 0
    return geq(self.p_bw, 0) + \
           geq(self.r_proc, 0) + \
           geq(self.r_dur, 0) + \
           [leq(self.a[3,:], 1)] + \
           [geq(self.tt, 0)] # + \
    
    '''
           geq(self.a[0,:], bw_lb) + \
           geq(self.a[1,:], proc_lb) + \
           geq(self.a[2:3,:], 0) + \
           [geq(self.tt, 0)] + \
           [leq(self.a[3,:], 1)] + \
           geq(self.r_proc, 0) + \
           geq(self.p_bw, 0) + \
    '''
  
  def res_cap_constraint(self):
    # resource capacity constraints
    res_id_info_map = self.actual_res_dict['id_info_map']
    # for resource bw
    r_bw_agged_column = ((self.r_bw).T)*ones((self.N,1))
    r_bw_cap_column = zeros((self.num_link, 1))
    for i in range(0, self.num_link):
      r_bw_cap_column[i,0] = res_id_info_map[i]['bw_cap']
    # for resource proc and stor
    r_proc_agged_column = ((self.r_proc2).T)*ones((self.N,1))
    r_proc_cap_column = zeros((self.num_itr, 1))
    r_stor_cap_column = zeros((self.num_itr, 1))
    for i in range(0, self.num_itr):
      i_corr = i + self.num_link
      r_proc_cap_column[i,0] = res_id_info_map[i_corr]['proc_cap']
      r_stor_cap_column[i,0] = res_id_info_map[i_corr]['stor_cap']

    return  leq(r_bw_agged_column, r_bw_cap_column) + \
            leq(r_proc_agged_column, r_proc_cap_column) + \
            leq(self.r_stor, r_stor_cap_column)
  
  def grab_sching_result(self):
    ###########################   S-WISE   #################################
    if self.N == 1:
      s_req_dict = self.sessions_beingserved_dict[0]['req_dict']
      (s_data_size, s_proc_comp, s_slack, s_parism_level) = (s_req_dict['data_size'],
                                                             s_req_dict['proc_comp'],
                                                             s_req_dict['slack_metric'],
                                                             s_req_dict['parism_level'])
      s_app_pref_dict = self.sessions_beingserved_dict[0]['app_pref_dict']
      (s_m_u, s_m_p, s_x_u, s_x_p) = (s_app_pref_dict['m_u'],
                                      s_app_pref_dict['m_p'],
                                      s_app_pref_dict['x_u'],
                                      s_app_pref_dict['x_p'])
      (bw, proc, dur, n) = (self.a[0,0].value,
                            self.a[1,0].value,
                            self.a[2,0].value,
                            self.a[3,0].value)
      #
      trans_t = self.r_hard_vector.value
      tt = self.tt.value
      [s_itwalkinfo_dict, s_pwalk_dict] = self.get_session_itwalkbundle_dict__walk(0)
      #ittime = self.it_time__basedon_itwalkinfo_dict(s_itwalkinfo_dict)
      #
      s_ps_info = self.sid_res_dict[0]['ps_info']
      num_ps = len(s_ps_info)
      p_bw, p_proc, p_dur = [], [], []
      sp_txt, sp_proct, sp_durt, sp_transt = [],[],[],[]
      for k in range(0,num_ps):
        #Adding p_bwprocdur info
        p_bw.append(self.p_bw[0,k].value)
        p_proc.append(self.p_proc[0,k].value)
        p_dur.append(self.p_dur[0,k].value)
        #Adding sp_txprocdurtrans info
        sp_txt.append(self.sp_tx[0,k].value)
        sp_proct.append(self.sp_proc[0,k].value)
        sp_durt.append(self.sp_dur[0,k].value)
        sp_transt.append(self.sp_trans[0,k].value)
      #
      self.session_res_alloc_dict['s-wise'][0] = {
                                           'p_bw':p_bw, 'p_proc':p_proc, 'p_dur':p_dur,
                                           'bw':bw, 'proc':proc,
                                           'dur':dur, 'n':n,'n**2':n**2,
                                           'stor':0.001*(bw*dur),
                                           'tt': tt,
                                           'trans_time': trans_t, #r_hard_perf
                                           'r_soft_perf': self.r_soft_vector.value,
                                           'm_u': s_m_u,
                                           'm_p': s_m_p,
                                           'x_u': s_x_u,
                                           'x_p': s_x_p,
                                           'hard_pi': abs(s_slack-tt),
                                           'parism_level': s_parism_level,
                                           'itwalkinfo_dict': s_itwalkinfo_dict,
                                           'pwalk_dict': s_pwalk_dict,
                                           'soft_pi': n, #(n/s_n_max)*100
                                           'sp_txt':sp_txt,
                                           'sp_proct':sp_proct,
                                           'sp_durt':sp_durt,
                                           'sp_transt':sp_transt
                                          }
                                          #'f_itcp_map': f_itcp_map,
    else:
      for i in range(0, self.N):
        s_req_dict = self.sessions_beingserved_dict[i]['req_dict']
        (s_data_size, s_proc_comp, s_slack, s_parism_level) = (s_req_dict['data_size'],
                                                               s_req_dict['proc_comp'],
                                                               s_req_dict['slack_metric'],
                                                               s_req_dict['parism_level'])
        s_app_pref_dict = self.sessions_beingserved_dict[i]['app_pref_dict']
        (s_m_u, s_m_p, s_x_u, s_x_p) = (s_app_pref_dict['m_u'],
                                        s_app_pref_dict['m_p'],
                                        s_app_pref_dict['x_u'],
                                        s_app_pref_dict['x_p'])
        (bw, proc, dur, n) = (self.a[0,i].value,
                              self.a[1,i].value,
                              self.a[2,i].value,
                              self.a[3,i].value)
        #
        trans_t = self.r_hard_vector[i,0].value
        tt = self.tt[i,0].value
        [s_itwalkinfo_dict, s_pwalk_dict] = self.get_session_itwalkbundle_dict__walk(i)
        #ittime = self.it_time__basedon_itwalkinfo_dict(s_itwalkinfo_dict)
        #
        s_ps_info = self.sid_res_dict[i]['ps_info']
        num_ps = len(s_ps_info)
        p_bw,p_proc,p_dur = [],[],[]
        sp_txt,sp_proct,sp_durt,sp_transt = [],[],[],[]
        for k in range(0,num_ps):
          #Adding p_bwprocdur info
          p_bw.append(self.p_bw[i,k].value)
          p_proc.append(self.p_proc[i,k].value)
          p_dur.append(self.p_dur[i,k].value)
          #Adding sp_txprocdurtrans info
          sp_txt.append(self.sp_tx[i,k].value)
          sp_proct.append(self.sp_proc[i,k].value)
          sp_durt.append(self.sp_dur[i,k].value)
          sp_transt.append(self.sp_trans[i,k].value)
        #
        self.session_res_alloc_dict['s-wise'][i] = {
                                             'p_bw':p_bw, 'p_proc':p_proc, 'p_dur':p_dur,
                                             'bw':bw, 'proc':proc,
                                             'dur':dur, 'n':n,'n**2':n**2,
                                             'stor':0.001*(bw*dur),
                                             'tt': tt,
                                             'trans_time': trans_t, #r_hard_perf
                                             'r_soft_perf': self.r_soft_vector[i,0].value,
                                             'm_u': s_m_u,
                                             'm_p': s_m_p,
                                             'x_u': s_x_u,
                                             'x_p': s_x_p,
                                             'hard_pi': abs(s_slack-tt),
                                             'parism_level': s_parism_level,
                                             'itwalkinfo_dict': s_itwalkinfo_dict,
                                             'pwalk_dict': s_pwalk_dict,
                                             'soft_pi': n, #(n/s_n_max)*100
                                             'sp_txt':sp_txt,
                                             'sp_proct':sp_proct,
                                             'sp_durt':sp_durt,
                                             'sp_transt':sp_transt
                                            }
                                            #'f_itcp_map': f_itcp_map,
    ###########################   RES-WISE   #################################
    r_bw_in_column = ((self.r_bw).T)*ones((self.N,1))
    r_proc_in_column = ((self.r_proc2).T)*ones((self.N,1))
    #FOR network links
    for i in range(0, self.num_link):
      #link_cap total usage
      self.session_res_alloc_dict['res-wise'][i] = {'bw': r_bw_in_column[i,0].value}
      #link_cap-session portion alloc
      if self.N == 1:
        self.session_res_alloc_dict['res-wise'][i].update(
          {'bw_palloc_list': [self.r_bw[:,i].value] })
      else:
        self.session_res_alloc_dict['res-wise'][i].update(
          {'bw_palloc_list': [float(e) for e in self.r_bw[:,i].value] })
    
    #FOR it-resources
    def dot(v1, v2):
      #print 'v1: ', v1
      #print 'v2: ', v2
      if isinstance(v1, float) and isinstance(v2, float): #two scalars
        return v1 * v2
      else:
        return np.dot(v1.T, v2)
    #
    for i in range(0, self.num_itr):
      #calculation of actual storage space
      dur_vector = (self.r_dur2[:, i]).value #Nx1
      bw_vector = ((self.a[0, :]).T).value #Nx1
      self.r_stor_actual[i] = dot(dur_vector, bw_vector)*0.001
      #res_cap total usage
      if self.N == 1:
        stor_model_val = self.r_stor[i,0].value
      else:
        #dump trick to work-around Cvxpy's not being able to turn SOMEthings to Python scalar
        stor_model_val = [float(e) for e in self.r_stor[i,0].value][0]
      self.session_res_alloc_dict['res-wise'][i+self.num_link] = {
        'proc': r_proc_in_column[i,0].value,
        'stor_model': stor_model_val,
        'stor_actual': float(self.r_stor_actual[i])
      }
      #res_cap-session portion alloc
      if self.N == 1:
        self.session_res_alloc_dict['res-wise'][i+self.num_link].update(
        {
          'proc_palloc_list': [self.r_proc2[:,i].value],
          'dur_palloc_list': [self.r_dur2[:,i].value]
        })
      else:
        self.session_res_alloc_dict['res-wise'][i+self.num_link].update(
        {
          'proc_palloc_list': [float(e) for e in self.r_proc2[:,i].value],
          'dur_palloc_list': [float(e) for e in self.r_dur2[:,i].value]
        })
    #
    
    #general info about sching_decision
    self.session_res_alloc_dict['general']['max_numspaths'] = self.max_numspaths
    self.session_res_alloc_dict['general']['ll_index'] = self.ll_index
  
  def solve(self):
    #self.resource_assign_model()
    (self.scal_var).value = 1
    #
    '''
    print '------------------------------'
    print 'F0(): ', self.F0()
    print 'F0().is_convex():', self.F0().is_convex()
    print 'F1(a): ', self.F1(self.a)
    print 'F1(a).is_concave():', self.F1(self.a).is_concave()
    print 'F(a): ', self.F(self.a)
    print 'F(a).is_convex():', self.F(self.a).is_convex()
    print '------------------------------'
    '''
    
    print 'XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX'
    #print 'constraint0: \n', self.constraint0()
    #print 'self.tt_epigraph_form_constraint(): \n', self.tt_epigraph_form_constraint()
    #print 'res_cap_constraint: \n', self.res_cap_constraint()
    print 'p_bwprocdur_sparsity_constraint:\n', self.p_bwprocdur_sparsity_constraint()
    print 'r_bwprocdur_sparsity_constraint:\n', self.r_bwprocdur_sparsity_constraint()
    print 'XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX'
    
    p = program(minimize(self.F()),
                ([self.constraint0(),
                  self.tt_epigraph_form_constraint(),
                  self.res_cap_constraint(),
                  self.r_bwprocdur_sparsity_constraint(),
                  self.p_bwprocdur_sparsity_constraint()
                 ]
                ),
                options = {
                  'abstol': 1e-7,
                  'feastol': 1e-6,
                  'reltol': 1e-6,
                  'maxiters':100
                  #'refinement':0
                }
               )
    print ">>>>>>>>>>>>>>>>>>>>>>>>>>"
    #p.show()
    #print 'p.variables:\n', p.variables
    #print 'p.parameters:\n', p.parameters
    #print 'p.constraints:\n', p.constraints
    print ">>>>>>>>>>>>>>>>>>>>>>>>>>"
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
    p.solve()
    '''
    print '||||||||||||||||||||||||||||||||||||'
    print 'optimal point: '
    print 'a:\n', self.a.value
    print 'p_bw:\n', self.p_bw.value
    print 'p_proc:\n', self.p_proc.value
    print 'p_dur:\n', self.p_dur.value
    #print 'r_bw:\n', self.r_bw.value
    print 'r_proc:\n', self.r_proc.value
    print 'r_dur:\n', self.r_dur.value
    print 'r_proc2:\n', self.r_proc2.value
    print 'r_dur2:\n', self.r_dur2.value
    #
    print 'optimal value:'
    print 'F0(a).value: ', self.F0().value
    print 'F1(a).value: ', self.F1(self.a).value
    print 'F(a).value: ', self.F(self.a).value
    print '||||||||||||||||||||||||||||||||||||'
    '''
    self.grab_sching_result()
  
  # modeling functions
  def trans_time_calc(self,s_pl,s_ds,s_pc,s_st,p_bw,ps_list,n=None,p_proc=None,p_dur=None):
    #To workaround dump assignment problem of par arrays in Cvxpy
    #p_transt_vector = parameter(s_pl,1, name='p_transt_vector')
    #s_ds: in MB
    p_transt_list = [0]*s_pl
    for pl_id in range(0,s_pl):
      p_ds = 8*s_ds*ps_list[pl_id]
      tx_t = p_ds*1000*1/p_bw[pl_id] # in (ms)
      if (p_proc == None and p_dur == None and n == None): #called from feasibilize_sching_info
        p_transt_list.append(tx_t) #+ path_latency
      elif (p_proc != None and p_dur != None and n != None): #called to calc true trans_time
        proc_t = p_ds*s_pc* 1000*(n**2)/p_proc[pl_id] #in (ms)
        stage_t = p_dur[pl_id] # in (ms)
        p_transt_list.append(tx_t + proc_t + stage_t) #+ path_latency
      else:
        print 'trans_time_calc() is called in with unexpected p_proc,p_dur,n.'
        print '### Abort.'
        sys.exit(0)
    return __builtin__.max(p_transt_list) #s_transt
  
  def txprocdurtrans_time_model(self,s_id,p_id, datasize,pcomp,num_itres):
    """
    def sp_proc_model(s_id,p_id):
      '''To get correct proc_time model not 1/(r1_proc + r2_proc + ...) but 1/r1_proc + 1/r2_proc + ... '''
      p_itrid_list = self.sid_res_dict[s_id]['ps_info'][p_id]['p_itrid_list']
      list_ = []
      for itr_id in p_itrid_list:
        itr_id_ = itr_id - self.ll_index - 1
        s_id_ = s_id+p_id*self.N
        #
        list_.append(quad_over_lin(self.a[3,s_id], self.r_proc[s_id_,itr_id_]))
      return sum(list_)
    """
    #datasize: MB
    tx_t = 1000*(8*datasize)*quad_over_lin(1, self.p_bw[s_id,p_id]) # (ms)
    #Assumption: Relation between proc_time and n is quadratic.
    pm = quad_over_lin(self.a[3,s_id], self.p_proc[s_id,p_id]) #sp_proc_model(s_id,p_id)
    #print 's_id:%s, p_id:%s; proc_model:%s' % (s_id,p_id,pm)
    '''
    - num_itres: the way totalwork(:total_proc_comp) is distributed over itres;
      r_work = totalwork*r_proc/p_proc -> proc_time at every itres takes same amount of time
      so that is where .*num_itres comes.
    - datasize/64 - how many Mflop: datasize (MB), assuming f(o1,o2)=1flop where o1,o2:4B operands
    '''
    proc_t = num_itres* 1000*float(8*float(datasize)/64)*pcomp*pm # (ms)
    #
    stage_t = self.p_dur[s_id,p_id] #self.a[2,s_id] # (ms)
    #
    trans_t = tx_t + proc_t + stage_t
    return [tx_t, proc_t, stage_t, trans_t]
  
  def R_hard(self, s_id):
    '''
    total_trans_time = max{ trans_time over each par_walk}
    '''
    #return max(self.sp_trans[s_id,:])
    s_pl = self.sessions_beingserved_dict[s_id]['req_dict']['parism_level']
    if s_pl == 1: #again workaround to scalar cvxpy object mess
      return self.sp_trans[s_id,0]
    #
    p_transt_vector = parameter(s_pl,1, name='p_transt_vector')
    for p_id in range(0,s_pl):
      p_transt_vector[p_id,0] = self.sp_trans[s_id,p_id]  #+ path_latency
    
    return max(p_transt_vector) #s_transt
  
  def R_soft(self, s_id):
    n = self.a[3,s_id] #quad_over_lin(self.a[3,s_id], 1) #square(self.a[3,s_id])
    return n*self.n_grain

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
  def P(self, session_num, expr_):
    #return self.s_pref_dict[session_num]['p']
    m_p = self.sessions_beingserved_dict[session_num]['app_pref_dict']['m_p']
    x_p = self.sessions_beingserved_dict[session_num]['app_pref_dict']['x_p']
    return max( vstack(( m_p*(expr_-x_p),0 )) )
    #return m_p*(expr_-x_p)
    #return self.s_pref_dict[session_num]['p']*expr_
    
  def U(self, session_num, expr_):
    #return self.s_pref_dict[session_num]['u']
    m_u = self.sessions_beingserved_dict[session_num]['app_pref_dict']['m_u']
    x_u = self.sessions_beingserved_dict[session_num]['app_pref_dict']['x_u']
    #return max( vstack(( m_u*(expr_-x_u),0 )) )
    #return min( vstack(( -1*m_u*(expr_-x_u),0 )) )
    return m_u*(expr_-x_u)
    #return self.s_pref_dict[session_num]['u']*expr_

  # objective functions
  def F0(self):
    if self.N == 1:
      return self.s_pen_vector
    else:
      return max(self.s_pen_vector)

  def F1(self):
    if self.N == 1:
      return self.U(0, self.R_soft(0) )
    else:
      return min(self.s_util_vector)
    
  def F(self):
    return self.F0() - self.scal_var*self.F1()
  
  # print info about optimization session
  def print_optimizer(self):
    print 'Optimizer is created with the follows: '
    print 'sessions_beingserved_dict: '
    pprint.pprint(self.sessions_beingserved_dict)
    print 'actual_res_dict: '
    pprint.pprint(self.actual_res_dict)
    print 'sid_res_dict: '
    pprint.pprint(self.sid_res_dict)
  
  def give_scal_var_range_dict(var_vector):
    dict_ = {}
    for var in var_vector:
      (self.scal_var).value = var
      p.solve(quiet=True) # Solve element of family
      dict_[var] = {"a": self.a.value,
                    "F0": self.F0(self.a).value,
                    "F1": self.F1(self.a).value
                   }
    return dict_
    #scal_var_vector = numpy.linspace(1e0,1e1,num=5) #1e-8
    #scal_var_range_dict = give_scal_var_range_dict(scal_var_vector)
    #print 'scal_var_range_dict: '
    #pprint.pprint(scal_var_range_dict)
    """
    # for Pareto optimal curve plotting
    def f(func):
      def g(var):
        (self.scal_var).value = var
        p.solve(quiet=True) # Solve element of family
        return func.value
      return g
    scal_var_vals = numpy.linspace(1e-8,1e2,num=50) # scal_var values to be used
    #(self.scal_var).value = 2
    #p.solve(quiet=True)
    #print 'self.F0(self.a).value: ', self.F0(self.a).value
    # Compute and plot Pareto optimal curve
    pylab.plot(map(f(self.F0(self.a)),scal_var_vals),
               map(f(self.F1(self.a)),scal_var_vals) )
    pylab.title("Pareto Optimal Curve")
    pylab.xlabel("F0")
    pylab.ylabel("F1")
    pylab.grid()
    pylab.show()
    """
  
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
          p_ttime += 1000*(p_ds/64)*p_c /p_proc #in (ms)
        except KeyError:
          pass
      #
      dict_[p_id] = p_ttime
    return dict_
  
  def get_session_itwalkbundle_dict__walk(self, s_id):
    s_req_dict = self.sessions_beingserved_dict[s_id]['req_dict']
    n = (self.a[3, s_id].value)**2
    s_pc = s_req_dict['proc_comp']
    tc = float(s_pc*n) #s_it_executable_totalcomp
    #
    def get_func_itexectablecomp_map(s_id):
      """
      Returns which function is executed over what percentage of data based on
      the allocated 'n**2'.
      """
      fl = s_req_dict['func_list']
      dict_ = {}
      m = tc
      for func in fl:
        f_c = self.func_compconstant_dict[func]
        if m < 0:
          dict_[func] = 0
        elif m > f_c:
          dict_[func] = f_c
        else: #0 < . < f_c
          dict_[func] = m
        m -= f_c
      return dict_
    #
    def add_itbundleres_itexeccomp(s_id, p_proc, itbundle_dict):
      #updates itbundle to include comp portion the res is responsible
      for t_id,t_info in itbundle_dict.items():
        try:
          t_proc = t_info['proc']
        except KeyError: #res may only be there for dur
          continue
        t_info['comp'] = tc*(t_proc/p_proc)
    #
    def add_itbundleres_itfuncdataportion(s_id, f_itcomp_dict, itbundle_dict, orded_itwalkbundle):
      cur_f_id, curf_tag, f_itcomp = -1, None, None
      s_fl = s_req_dict['func_list']
      for t_tag in orded_itwalkbundle:
        itbundle_dict[t_tag]['itfunc_dict'] = {}
        ttag_itfunc_dict = itbundle_dict[t_tag]['itfunc_dict']
        t_comp = itbundle_dict[t_tag]['comp']
        while t_comp > 0:
          if f_itcomp == None:
            cur_f_id += 1
            #print 'cur_f_id: ', cur_f_id
            try:
              curf_tag = s_fl[cur_f_id]
            except IndexError:
              #to workaround more t_comp >= f_itcomp than supposed to because 
              #of slight numerical difference
              t_comp -= t_comp
              continue
            f_itcomp = f_itcomp_dict[curf_tag]
          if t_comp <= 0:
            continue
          if t_comp >= f_itcomp:
            ttag_itfunc_dict[curf_tag] = f_itcomp
            t_comp -= f_itcomp
            f_itcomp = None
            #print '>= t_tag:%s, ttag_itfunc_dict:' % t_tag
            #pprint.pprint(ttag_itfunc_dict)
          elif t_comp < f_itcomp:
            ttag_itfunc_dict[curf_tag] = t_comp
            f_itcomp -= t_comp
            t_comp -= t_comp
            #print '< t_tag:%s, ttag_itfunc_dict:' % t_tag
            #pprint.pprint(ttag_itfunc_dict)
    #
    def itwalkbundle_to_walk__ordereditwalkbundle(net_path, itwalkbundle):
      #construct data_walk
      walk = net_path
      for itr in itwalkbundle:
        itr_id = self.actual_res_dict['res_id_map'][itr]
        conn_sw = self.actual_res_dict['id_info_map'][itr_id]['conn_sw']
        #
        lasti_conn_sw = len(walk) - walk[::-1].index(conn_sw) - 1
        walk.insert(lasti_conn_sw+1, itr)
        walk.insert(lasti_conn_sw+2, conn_sw)
      #extract it_order info from data_walk
      itwalkbundle_, i_list = [], []
      i_itr_dict = {}
      for itr in itwalkbundle:
        itr_i = walk.index(itr)
        i_list.append(itr_i)
        i_itr_dict[itr_i] = itr
      i_list.sort()
      itwalkbundle_ = [i_itr_dict[i] for i in i_list]
      #
      return [walk, itwalkbundle_]
    #      
    '''
    Walk_bundle of a session includes only assigned it_nodes NOT links because
    they (links on given session_transfer_path) are already supposed to be in
    the bundle.
    Info_consisted: for every itres in the bundle proc_alloc, itfunc and the
    corresponding data_perc
    '''
    dict_, p_walk = {}, {}
    s_ps_info = self.sid_res_dict[s_id]['ps_info']
    s_ds = s_req_dict['data_size']
    s_ps = s_req_dict['par_share']
    #print 's_ps:', s_ps
    s_pl = s_req_dict['parism_level']
    for p_id in range(0, s_pl):
      p_info_dict = s_ps_info[p_id]
      dict_[p_id] = {'itbundle':{}, 'p_info':{}}
      p_itbundle_dict = dict_[p_id]['itbundle']
      p_proc, p_dur = 0, 0
      for t_id in range(0, self.num_itr):
        s_id_ = s_id + p_id*self.N
        it_proc = float(self.r_proc[s_id_,t_id].value)
        it_dur = float(self.r_dur[s_id_,t_id].value)
        if it_proc > 1: #For proc 1 Mflop/s is min_threshold
          p_proc += it_proc
          t_id_ = t_id + self.ll_index + 1
          it_tag = self.actual_res_dict['id_info_map'][t_id_]['tag']
          try:
            p_itbundle_dict[it_tag].update({'proc': it_proc})
          except KeyError:
            p_itbundle_dict[it_tag] = {'proc': it_proc}
        if it_dur > 1: #For dur 1ms is min_threshold
          p_dur += it_dur
          t_id_ = t_id + self.ll_index + 1
          it_tag = self.actual_res_dict['id_info_map'][t_id_]['tag']
          try:
            p_itbundle_dict[it_tag].update({'dur': it_dur})
          except KeyError:
            p_itbundle_dict[it_tag] = {'dur': it_dur}
      dict_[p_id]['p_info']['p_proc'] = p_proc
      dict_[p_id]['p_info']['p_dur'] = p_dur
      dict_[p_id]['p_info']['datasize'] = float(s_ds)*float(s_ps[p_id])
      dict_[p_id]['p_info']['totalcomp'] = tc
      add_itbundleres_itexeccomp(s_id, p_proc = p_proc,
                                 itbundle_dict = p_itbundle_dict)
      f_itcomp_dict = get_func_itexectablecomp_map(s_id)
      #to ensure itfuncs are execed over ordered itreses on the path
      '''
      print 'p_itbundle_dict: '
      pprint.pprint( p_itbundle_dict )
      print '[t for t in p_itbundle_dict]: ', [t for t in p_itbundle_dict]
      '''
      itwalkbundle = [t for t in p_itbundle_dict]
      [p_walk[p_id], orded_itwalkbundle] = \
        itwalkbundle_to_walk__ordereditwalkbundle(p_info_dict['path'], 
                                                  itwalkbundle = itwalkbundle)
      #
      add_itbundleres_itfuncdataportion(s_id, f_itcomp_dict,
                                        itbundle_dict = p_itbundle_dict,
                                        orded_itwalkbundle = orded_itwalkbundle)
    #
    return [dict_,p_walk]
  
  def feasibilize_schinginfo(self):
    self.add_path_sharing_info()
    #
    """
      Find out the min slack metric requirement for the requirements of a session
      to be feasible for the resource allocation optimization process.
    """
    safe_p = 0.02 #safety margin for feasibility purposes
    for s_id in range(0, self.N):
      s_req_dict = self.sessions_beingserved_dict[s_id]['req_dict']
      s_pl = s_req_dict['parism_level']
      p_bw = [self.sid_res_dict[s_id]['ps_info'][p_id]['fair_bw'] for p_id in range(0,s_pl)]
      #print '---> s_id:%i' % s_id
      trans_t = self.trans_time_calc(s_pl = s_pl,
                                     s_ds = s_req_dict['data_size'],
                                     s_pc = s_req_dict['proc_comp'],
                                     s_st = s_req_dict['slack_metric'],
                                     p_bw = p_bw,
                                     ps_list = s_req_dict['par_share'])
      min_tt = trans_t*(1+safe_p)
      slack = s_req_dict['slack_metric']
      #
      if slack < min_tt:
        print '### S{}\'s slack_metric is NOT FEASIBLE !'.format(s_id)
        print '  * Changed from:{}ms to:{}ms'.format(slack, min_tt)
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
        print '### S{}; Not enough numspaths:{} to provide parism_level:{}'.format(s_id, numspaths, s_parism_level)
        print '  * parism_level is changed to numspaths'
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

