import pprint
import itertools
import json
import networkx as nx
from collections import namedtuple

# used to adjust computational time difference between diff functions
func_tcomplexity_dict = {
  'f1':1.1, 'f2':1.2, 'f3':1.3, 
  'f4':1.4, 'f5':1.5, 'f6':1.6
}

class GraphMan(object):
  def __init__(self):
    self.g = nx.Graph()
    #
    self.net_edge = namedtuple("net_edge", ["pre", "post"])
  
  def give_itreslist_on_path(self,path):
    node_dict = dict(self.g.nodes(data=True))
    #print 'give_itreslist_on_path:: node_dict=%s\n' % pprint.pformat(node_dict)
    #n_nbrs_dict = {(n if n in t_path else -1):(nbrs if n in t_path else -1) \
    #                for n,nbrs in self.g.adjacency_list()}
    itres_on_path_list = []
    for sw in path:
      sw_itres_list = [node for node in node_dict \
                       if (node in self.g.neighbors(sw) and \
                           node_dict[node]['type'] == 't' )]
      if len(sw_itres_list) != 0:
        itres_on_path_list.extend(sw_itres_list)
    return itres_on_path_list

  def pathlist_to_netedgelist(self, path):
    net_edge_list = []
    pre_node = None
    for i, node in enumerate(path):
      if i == 0:
        pre_node = node
        continue
      # node: cur_node
      net_edge_list.append(
        self.give_ordered_net_node_tuple((pre_node,node)) )
      pre_node = node
    return net_edge_list
  
  def give_shortest_path(self, src, trgt, wght):
    return nx.shortest_path(self.g, source=src, target=trgt, weight=wght)
  
  def give_all_paths(self, src, trgt):
    if src == trgt:
      return [ [src] ]
    #
    return nx.all_simple_paths(self.g, source=src, target=trgt)
  
  def give_actual_resource_dict(self):
    dict_ = {"overview":{}, "res_id_map":{}, "id_info_map":{}}
    #First fill links then itrs. This is used by last_link_index
    # fill links
    index = 0
    for edge in self.g.edges(data=True):
      ordered_edge = self.give_ordered_net_node_tuple((edge[0],edge[1]))
      #print 'ordered_edge: ', ordered_edge
      if 't' in ordered_edge[1]: #Link of HIGH cap, will not matter in optimization formulation
        continue
      dict_["res_id_map"]\
      [self.net_edge(pre=ordered_edge[0], post=ordered_edge[1])] = index
      dict_["id_info_map"][index] = {
        "bw_cap": float(edge[2]['bw']),
        "type":'link'
      }
      index = index + 1

    # specify the separation point
    dict_['overview']['last_link_index'] = index - 1
    # fill it_hosts
    node_dict = dict(self.g.nodes(data=True))
    for node in node_dict:
      if node_dict[node]['type'] == 't':
        dict_["res_id_map"][node] = index
        dict_["id_info_map"][index] = {
          "tag": node,
          "conn_sw": self.give_tpr_sw_name(node),
          "proc_cap": node_dict[node]['proc_cap'],
          "stor_cap": node_dict[node]['stor_cap'],
          "type":'t'
        }
        index = index + 1
    return dict_
    
  def give_ordered_net_node_tuple(self, net_node_tuple):
    """
    s_X_node > s_Y_node if X > Y
    t_node > s_node
    returned tuple_order: lower, higher
    """
    def compare_net_nodes(node1, node2): # returns which one is "higher"; 0 or 1
      # only one of them is t_node
      if ('t' in node1): 
        return 0
      elif ('t' in node2):
        return 1
        
      if ('s' in node1) and ('s' in node2):
        if int(node1.split('s')[1]) > int(node2.split('s')[1]):
          return 0
        else:
          return 1 
    higher_index = compare_net_nodes(net_node_tuple[0], net_node_tuple[1])
    if higher_index == 1:
      return net_node_tuple
    else: # higher_index == 0:
      return (net_node_tuple[1], net_node_tuple[0])
      
  def sch_path(self, sch_req_id, qos_dict):
    """
    For now: Will assume 
    * All sch request is made to allocate a path between 1 gw-pair(s11-s12)
    * Resource Allocation will be based on FIFO
    * P resources will be allocated over the possible network paths
    * EVERY P resource can run ANY requested computation
    * Best-effort. Only criterion is to increase data quality.
      If delivering data is impossible, ISA will return NACK.
      Data will only be delivered even if no chance for data quality increase due to 
      - strict slack_metric
      - no available transit resource
    * Every P resource can serve for one session only at a time
    * No data amount increase introduced by the transit computations
    -> Initially
    * LINEAR comp_time vs. data_amount relation
    * STATIC scheduling scheme
    qos_dict: {'data_amount(Gb)':, 'slack_metric(ms)':, 'func_list':{}}
    """
    #best_path_comb = self.give_best_path_comb(qos_dict)
    best_path_comb = self.better_give_best_path(sch_req_id, qos_dict)
    
    #print 'best_path_comb: '
    #pprint.pprint(best_path_comb)
    
    return best_path_comb
    
  def give_best_path_comb(self, req_dict):
    """
    !!! DEPRECATED !!!
    Will give the best path. Metric for comparison is del_time. The less, the better.
    req_dict: {'data_amount(Gb)':,'slack_metric(ms)':, 'func_list':[]}
    """
    data_amount = req_dict['data_amount']
    slack_metric = req_dict['slack_metric']
    func_list = req_dict['func_list']
    best_path_comb = {'total_cost':float('Inf'),'path_del_cost':float('Inf'),
                      'comp_cost':float('Inf'),'del_path':None,'path_avcap':None,
                      't_comb':None,'path':None}
    for path in nx.all_simple_paths(self.g, source='s11', target='s12'):
      path_avcap = self.find_path_avcap(path)
      del_time = float(path_avcap['latency']) + \
                 float(data_amount)*(1+float(path_avcap['loss']))/float(path_avcap['bw']) * \
                 len(path)*2
      #print 'del_time: ', del_time
      if del_time > float(slack_metric):
        continue
      #######################################################################
      """
      P resource alloc needs also be done in this method while considering all
      the possible paths. Procedure:
      * Find all possible available p resources on the path
      * Alloc p resources to maximize the quality of data
        - slack_metric is the constraint (computational_time = p_index(0-1) * data_amount(Gb))
        - order of processing done by given functions MATTERS
        - try to decrease contention at the intermediate SA sws i.e. i.e. out_bw - in_bw
        - available p capacity at each AS i.e. total p_index of available p resources
          in an AS
      """
      node_dict = dict(self.g.nodes(data=True))
      #n_nbrs_dict = {(n if n in t_path else -1):(nbrs if n in t_path else -1) \
      #                for n,nbrs in self.g.adjacency_list()}
      pr_on_path_dict = {}
      #print 'path: ', path
      num_pr_on_path = 0
      for sw in path:
        sw_pr_dict = {node:node_dict[node] for node in node_dict \
                      if (node in self.g.neighbors(sw) and \
                          node_dict[node]['type'] == 't' and \
                          len(node_dict[node]['session']) == 0 )}
        if len(sw_pr_dict) != 0:
          for pr,attr in sw_pr_dict.items():
            pr_on_path_dict[pr] = attr
          num_pr_on_path = num_pr_on_path + len(sw_pr_dict)
          
      #pprint.pprint(pr_on_path_dict)
      
      len_func_list = len(func_list)
      alloc_pr_num = len_func_list if (num_pr_on_path > len_func_list) else num_pr_on_path
      #######################################################################
      def trans_to_ordered_comb(all_combs): #comb is tuple of prs
        for comb in all_combs:
          order_index_list = []
          orderindex_pr_dict = {}
          for pr in comb:
            sa_sw = self.g.neighbors(pr)[0] # each pr is connected to only one sa_sw
            order_index = path.index(sa_sw)
            order_index_list.append(order_index)
            if not (order_index in orderindex_pr_dict):
              orderindex_pr_dict[order_index] = []
            orderindex_pr_dict[order_index].append(pr)
          if order_index_list == sorted(order_index_list):
            continue
          #print 'comb: ', comb, 'order_index_list: ', order_index_list
          order_index_list = list(set(order_index_list)) #to remove the duplicate indexes
          ordered_comb = [pr for i in order_index_list for pr in orderindex_pr_dict[i]]
          all_combs.remove(comb)
          all_combs.append(ordered_comb)
          #print 'ordered_comb: ', ordered_comb
      all_combs = list(itertools.combinations(pr_on_path_dict, r=alloc_pr_num))
      trans_to_ordered_comb(all_combs)
      #######################################################################
      def comb_cost_calc(all_combs):
        """
        Calculate total time for data trans, prop and computation in SAs
        - trans = data_amount / link_bw
        - comp_time = data_amount*p_index*func_t_complexity
        """
        comb_cost_list = []
        for comb in all_combs:
          comb_trans_time = 0
          comb_prop_time = 0
          comb_comp_time = 0
          fl_counter = 0
          for pr in comb:
            link_tuple = list(self.g[pr].iteritems())[0]   #always one entity !
            
            comb_trans_time = comb_trans_time + \
                              4*float(data_amount) / float(link_tuple[1]['bw'])
            comb_prop_time = comb_prop_time + 2*float(link_tuple[1]['delay'])
            comb_comp_time = comb_comp_time + float(data_amount) * \
                             float(pr_on_path_dict[pr]['p_index']) * \
                             func_tcomplexity_dict[func_list[fl_counter]]
            fl_counter = fl_counter + 1
            comb_total_cost = comb_trans_time + comb_prop_time + comb_comp_time
          comb_cost_list.append((comb, {'comb_trans_time':comb_trans_time,
                                        'comb_prop_time':comb_prop_time,
                                        'comb_comp_time':comb_comp_time,
                                        'comb_total_cost':comb_total_cost
                                       }
                               ))
        return comb_cost_list
      comb_cost_list = comb_cost_calc(all_combs)
      #pprint.pprint(comb_cost_list)
      def find_min_total_cost_comb(comb_cost_list):
        min_total_cost = float('Inf')
        min_total_cost_comb = None
        for comb_costmap in comb_cost_list:
          comb_total_cost = comb_costmap[1]['comb_total_cost']
          if comb_total_cost < min_total_cost:
            min_total_cost = comb_total_cost
            min_total_cost_comb = comb_costmap[0]
        return [min_total_cost_comb, {'comb_total_cost':min_total_cost}]
      mincost_comb_cost_list = find_min_total_cost_comb(comb_cost_list)
      comp_time = mincost_comb_cost_list[1]['comb_total_cost']
      best_comb = mincost_comb_cost_list[0]
      #pprint.pprint(mincost_comb_cost_list)
      #print '-------------------'
      #######################################################################
      #del_cost + min_comp_cost
      total_cost = del_time + comp_time
      if total_cost > float(slack_metric):
        continue
      if total_cost < best_path_comb['total_cost']:
          best_path_comb['total_cost'] = total_cost
          best_path_comb['path_del_cost'] = del_time
          best_path_comb['comp_cost'] = comp_time
          best_path_comb['del_path'] = path
          best_path_comb['path'] = path
          best_path_comb['path_avcap'] = path_avcap
          best_path_comb['t_comb'] = best_comb
       
    if best_path_comb['t_comb'] == None:
      print 'A sching based on req_dict: ', req_dict,' not possible !'
      return None
    for t_p in best_path_comb['t_comb']:
      #print 'nbr_info of t_p:', t_p, '_', list(self.g[t_p].iteritems())[0][0]
      conn_sw = list(self.g[t_p].iteritems())[0][0]
      conn_sw_list_i = best_path_comb['del_path'].index(conn_sw)
      best_path_comb['path'].insert(conn_sw_list_i+1, t_p)
      best_path_comb['path'].insert(conn_sw_list_i+2, conn_sw)
      
    return best_path_comb
    
  def find_path_avcap(self, path):
    """
    Finds and returns the link bw with least in the path.
    path is the list of overlaying nodes.
    """
    path_bw = float('Inf')
    path_latency = 0
    path_success = 1.0
    for j, node in enumerate(path):
      if j == 0: continue
      i = j - 1
      # Simply assume that link bw is shared between the served sessions equally
      link_bw = float(self.g[path[i]][path[j]]['bw']) / (len(self.g[path[i]][path[j]]['session'])+1)
      path_latency = path_latency + int(self.g[path[i]][path[j]]['delay'])
      path_success = path_success*(1-float(self.g[path[i]][path[j]]['loss']))
      
      if link_bw < path_bw:
        path_bw = link_bw
    path_loss = 1 - path_success
    #'bw', 'delay', 'loss'
    return {'bw':path_bw, 'latency':path_latency, 'loss':path_loss}
  
  def graph_add_nodes(self, nodes):
    for node in nodes:
      if node[1]['type'] == 'sw':
        self.g.add_node(node[0], node[1] )
      elif node[1]['type'] == 't':
        self.g.add_node(node[0], dict(node[1].items() + node[2].items() ))
  
  def graph_add_edges(self, edges):
    for edge in edges:
      w_dict = {'weight':int(edge[3]['delay'])}
      self.g.add_edge(edge[0],edge[1], \
                      dict(w_dict.items() + edge[2].items() + edge[3].items() ))
      
  def get_edge(self, pre_node, post_node):
    #print 'pre_node: {}, post_node: {}'.format(pre_node, post_node)
    return self.g[pre_node][post_node]
  
  def get_node(self, node):
    node_dict = dict(self.g.nodes(data=True))
    return node_dict[node]
  
  def print_graph(self):
    print '# of nodes: ', self.g.number_of_nodes()
    print '# of edges: ', self.g.number_of_edges()
    print 'nodes: ', self.g.nodes()
    print 'edges: ', self.g.edges()
    print 'node overview:'
    pprint.pprint(self.g.nodes(data=True))
    print 'edge overview:'
    pprint.pprint(self.g.edges(data=True))
    """
    for n,nbrs in self.g.adjacency_iter():
      for nbr,eattr in nbrs.items():
        #print 'eattr: ', eattr
        try:
          data=eattr['pre_dev']
          print('(<%s-%s> , <%s-%s> , bw:%s, delay:%s, loss:%s, max_queue_size:%s)'
          % (n,nbr,eattr['pre_dev'],eattr['post_dev'],eattr['bw'],eattr['delay'],
          eattr['loss'],eattr['max_queue_size']))
        except KeyError:
          pass
    """
    #print 'exp:'
    #print 'g[s11][s1]: ',self.g['s11']['s1']
    
  def give_tpr_sw_name(self, tpr_name):
    return self.g.neighbors(tpr_name)[0] #every tpr will have only one neighbor !

