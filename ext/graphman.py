import pprint, itertools, json
import networkx as nx
import numpy as np
from collections import namedtuple

class GraphMan(object):
  def __init__(self):
    self.g = nx.Graph()
    #
    self.net_edge = namedtuple("net_edge", ["pre", "post"])
  
  def get_itr_on_path_list(self, path):
    node_dict = dict(self.g.nodes(data=True))
    # print 'get_itr_on_path_list:: node_dict=%s\n' % pprint.pformat(node_dict)
    # n_nbrs_dict = {(n if n in t_path else -1):(nbrs if n in t_path else -1) \
    #                 for n,nbrs in self.g.adjacency_list()}
    itr_on_path_list = []
    for sw in path:
      sw_itres_list = [node for node in node_dict \
                       if (node in self.g.neighbors(sw) and \
                           node_dict[node]['type'] == 't' )]
      if len(sw_itres_list) != 0:
        itr_on_path_list.extend(sw_itres_list)
    return itr_on_path_list

  def path_to_edge_list(self, path):
    net_edge_list = []
    pre_node = None
    for i, node in enumerate(path):
      if i == 0:
        pre_node = node
        continue
      # node: cur_node
      net_edge_list.append(
        self.give_ordered_net_node_tuple((pre_node, node)) )
      pre_node = node
    return net_edge_list
  
  def get_shortest_path(self, src, trgt, wght):
    return nx.shortest_path(self.g, source=src, target=trgt, weight=wght)
  
  def get_all_paths_list(self, src, trgt):
    if src == trgt:
      return [ [src] ]
    #
    paths = nx.all_simple_paths(self.g, source=src, target=trgt)
    path_list = []
    for path in paths:
      path_list.append(path)
    
    return path_list
  
  def get_actual_resource_dict(self):
    dict_ = {"overview":{}, "res_id_map":{}, "id_info_map":{}}
    # First fill links then itrs. This is used by last_link_index
    # fill links
    index = 0
    for edge in self.g.edges(data=True):
      ordered_edge = self.give_ordered_net_node_tuple((edge[0],edge[1]))
      # print 'ordered_edge: ', ordered_edge
      if 't' in ordered_edge[1]: #Link of HIGH cap, will not matter in optimization formulation
        continue
      dict_["res_id_map"]\
      [self.net_edge(pre=ordered_edge[0], post=ordered_edge[1])] = index
      dict_["id_info_map"][index] = {
        "bw_cap": float(edge[2]['bw']),
        "type":'link' }
      index = index + 1

    # Specify the separation point
    dict_['overview']['last_link_index'] = index - 1
    # Fill it_hosts
    node_dict = dict(self.g.nodes(data=True))
    for node in node_dict:
      if node_dict[node]['type'] == 't':
        dict_["res_id_map"][node] = index
        dict_["id_info_map"][index] = {
          "tag": node,
          "conn_sw": self.give_itr_sw_name(node),
          "proc_cap": node_dict[node]['proc_cap'],
          "stor_cap": node_dict[node]['stor_cap'],
          "type":'t' }
        index = index + 1
    
    return dict_
    
  def give_ordered_net_node_tuple(self, net_node_tuple):
    # s_X_node > s_Y_node if X > Y
    # t_node > s_node
    # returned tuple_order: lower, higher
    def compare_net_nodes(node1, node2): # returns which one is "higher"; 0 or 1
      # Only one of them is t_node
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
      
  def graph_add_nodes(self, nodes):
    for node in nodes:
      if node[1]['type'] == 'sw':
        self.g.add_node(node[0], node[1] )
      elif node[1]['type'] == 't':
        self.g.add_node(node[0], 
                        dict(node[1].items() + \
                             {'num_users': 0,
                              'fair_proc_cap': 0 }.items() ) )
  
  def graph_add_edges(self, edges):
    for edge in edges:
      self.g.add_edge(edge[0], edge[1], \
                      dict(edge[2].items() + \
                           {'num_users': 0,
                            'fair_bw': 0, #float(edge[2]['bw']),
                            'weight': int(edge[2]['delay']) }.items() ) )
      
  def get_edge(self, edge_tuple):
    return self.g[edge_tuple[0]][edge_tuple[1]]
  
  def get_node(self, node):
    return self.g.node[node]
  
  def print_graph(self):
    print '# of nodes: ', self.g.number_of_nodes()
    print '# of edges: ', self.g.number_of_edges()
    print 'nodes: ', self.g.nodes()
    print 'edges: ', self.g.edges()
    print 'node overview:'
    pprint.pprint(self.g.nodes(data=True))
    print 'edge overview:'
    pprint.pprint(self.g.edges(data=True))
    # for n,nbrs in self.g.adjacency_iter():
    #   for nbr,eattr in nbrs.items():
    #     #print 'eattr: ', eattr
    #     try:
    #       data=eattr['pre_dev']
    #       print('(<%s-%s> , <%s-%s> , bw:%s, delay:%s, loss:%s, max_queue_size:%s)'
    #       % (n,nbr,eattr['pre_dev'],eattr['post_dev'],eattr['bw'],eattr['delay'],
    #       eattr['loss'],eattr['max_queue_size']))
    #     except KeyError:
    #       pass
    
    # print 'exp:'
    # print 'g[s11][s1]: ',self.g['s11']['s1']
    
  def give_itr_sw_name(self, itr):
    return self.g.neighbors(itr)[0] #every itr will have only one neighbor!
  
  def add_user_to_edge(self, edge_tuple):
    edge = self.g[edge_tuple[0]][edge_tuple[1]]
    edge['num_users'] += 1
    edge['fair_bw'] = float(edge['bw']) / edge['num_users']
    
  def add_user_to_itr(self, itr):
    itr = self.g.node[itr]
    itr['num_users'] += 1
    itr['fair_proc_cap'] = float(itr['proc_cap']) / itr['num_users']
  
  def rm_user_from_edge(self, edge_tuple):
    edge = self.g[edge_tuple[0]][edge_tuple[1]]
    edge['num_users'] -= 1
    try:
      edge['fair_bw'] = float(edge['bw']) / edge['num_users']
    except ZeroDivisionError:
      edge['fair_bw'] = 0
    
  def rm_user_from_itr(self, itr):
    itr = self.g.node[itr]
    itr['num_users'] -= 1
    try:
      itr['fair_proc_cap'] = float(itr['proc_cap']) / itr['num_users']
    except ZeroDivisionError:
      itr['fair_proc_cap'] = 0
  
  def add_user_to_edge__itr_list(self, edge_list, itr_list):
    for edge in edge_list:
      self.add_user_to_edge(edge)
    for itr in itr_list:
      self.add_user_to_itr(itr)
  
  def rm_user_from_edge__itr_list(self, edge_list, itr_list):
    for edge in edge_list:
      self.rm_user_from_edge(edge)
    for itr in itr_list:
      self.rm_user_from_itr(itr)
    
  def get_path_bw__fair_bw(self, edge_on_path_list):
    path_bw, path_fair_bw = float('Inf'), float('Inf')
    for edge in edge_on_path_list:
      edge_ = self.g[edge[0]][edge[1]]
      edge_bw = float(edge_['bw'])
      if path_bw > edge_bw:
        path_bw = edge_bw
      edge_fair_bw = edge_['fair_bw']
      if path_fair_bw > edge_fair_bw:
        path_fair_bw = edge_fair_bw
    #
    return [path_bw, path_fair_bw]
  
  def get_path_fair_proc_cap(self, itr_on_path_list):
    path_fair_proc_cap = 0
    for itr in itr_on_path_list:
      path_fair_proc_cap += self.g.node[itr]['fair_proc_cap']
    #
    return path_fair_proc_cap
  
  def get_path__edge__itr_on_path_list__fair_bw_dict(self, src, trgt):
    all_paths_list = self.get_all_paths_list(src, trgt)
    # print 'get_path__edge__itr_on_path_list:: all_paths_list= \n%s' % pprint.pformat(all_paths_list)
    
    path_info_dict = {}
    for i, path in enumerate(all_paths_list):
      if not i in path_info_dict:
        path_info_dict[i] = {'path': path,
                             'edge_on_path_list': self.path_to_edge_list(path),
                             'itr_on_path_list': self.get_itr_on_path_list(path) }
      path_info = path_info_dict[i]
      self.add_user_to_edge__itr_list(path_info['edge_on_path_list'], path_info['itr_on_path_list'])
      
      path_fair_bw_list, path_fair_proc_cap_list = [], []
      for i_, path_ in enumerate(all_paths_list):
        if not i_ in path_info_dict:
          path_info_dict[i_] = {'path': path_,
                                'edge_on_path_list': self.path_to_edge_list(path_),
                                'itr_on_path_list': self.get_itr_on_path_list(path_) }
        path_info_ = path_info_dict[i_]
        [path_bw, path_fair_bw] = self.get_path_bw__fair_bw(path_info_['edge_on_path_list'])
        path_info_['bw'] = path_bw
        path_info_['fair_bw'] = path_fair_bw
        path_fair_bw_list.append(path_fair_bw)
        path_fair_proc_cap_list.append(self.get_path_fair_proc_cap(path_info_['itr_on_path_list']) )
      # cv: Coeff of variance
      # path_info['path_fair_bw_list'] = path_fair_bw_list
      # path_info['path_fair_proc_cap_list']= path_fair_proc_cap_list
      
      path_fair_bw_array = np.array(path_fair_bw_list)
      path_info['to_be_fair_bw_cv'] = float(np.std(path_fair_bw_array) / np.mean(path_fair_bw_array) )
      path_fair_proc_cap_array = np.array(path_fair_proc_cap_list)
      path_info['to_be_fair_proc_cap_cv'] = float(np.std(path_fair_proc_cap_array) / np.mean(path_fair_proc_cap_array) )
      path_info['to_be_fair_total_cv'] = path_info['to_be_fair_bw_cv'] + path_info['to_be_fair_proc_cap_cv']
      
      self.rm_user_from_edge__itr_list(path_info['edge_on_path_list'], path_info['itr_on_path_list'])
    #
    min_to_be_fair_total_cv = float('Inf')
    min_to_be_fair_total_cv_i = None
    for i, path_info in path_info_dict.items():
      to_be_fair_total_cv = path_info['to_be_fair_total_cv']
      if min_to_be_fair_total_cv > to_be_fair_total_cv:
        min_to_be_fair_total_cv = to_be_fair_total_cv
        min_to_be_fair_total_cv_i = i
    #
    # print '----------------------'
    # self.print_graph()
    # print 'get_path__edge__itr_on_path_list:: path_info_dict= \n%s' % pprint.pformat(path_info_dict)
    # print '----------------------'
    
    return path_info_dict[min_to_be_fair_total_cv_i]
  
  