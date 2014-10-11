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
    if src == trgt:
      return [ [src] ]
    #
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
      
  def graph_add_nodes(self, nodes):
    print "graph_add_nodes:: nodes= ", nodes
    for node in nodes:
      if node[1]['type'] == 'sw':
        self.g.add_node(node[0], node[1] )
      elif node[1]['type'] == 't':
        self.g.add_node(node[0], dict(node[1].items() + node[2].items() ))
  
  def graph_add_edges(self, edges):
    for edge in edges:
      w_dict = {'weight':int(edge[3]['delay']),
                'num_users': 0}
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
  ### 
  def inc_num_user__update_weight_on_net_edge_list(self, net_edge_list):
    for net_edge in net_edge_list:
      # print "net_edge= ", net_edge
      self.inc_num_user__update_weight_on_edge(net_edge)
    #
    
  def dec_num_user__update_weight_on_net_edge_list(self, net_edge_list):
    for net_edge in net_edge_list:
      # print "net_edge= ", net_edge
      self.dec_num_user__update_weight_on_edge(net_edge)
    #
    
  def inc_num_user__update_weight_on_edge(self, edge_list):
    # print "edge_list= ", edge_list
    pre_node = edge_list[0]
    post_node = edge_list[1]
    # print "pre_node= ", pre_node
    # print "post_node= ", post_node
    # print "pre_node= ", pre_node
    # print "post_node= ", post_node
    try:
      self.g[pre_node][post_node]['num_users'] += 1
      self.g[pre_node][post_node]['weight'] += 60
    except KeyError:
      return
    #
    # print "inc_num_user__update_weight_on_edge done on edge= ", edge_list
    
  def dec_num_user__update_weight_on_edge(self, edge_list):
    try:
      pre_node = edge_list[0]
      post_node = edge_list[1]
      self.g[pre_node][post_node]['num_users'] -= 1
      self.g[pre_node][post_node]['weight'] -= 60
    except KeyError:
      return
