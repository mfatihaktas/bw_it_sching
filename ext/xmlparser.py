try:
    import xml.etree.cElementTree as ET
except ImportError:
    import xml.etree.ElementTree as ET

class XMLParser(object):
  def __init__(self, xmlfile_url, network_number):
    self.network_number = network_number
    self.xmlfile_url = xmlfile_url
    self.tree = ET.parse(xmlfile_url)
    # self.node_tree = self.tree.getiterator('node')
    self.root = self.tree.getroot()
  
  def get_node__edge_list(self):
    def dev_name_to_sw(dev_name):
      return dev_name.split('-', 1)[0]
    
    node_list, edge_list = [], []
    for network in self.root:
      if network.get('number') == self.network_number:
        nodes = network.find('nodes')
        for node in nodes:
          node_type = node.get('type')
          if node_type == 'sw':
            node_list.append([node.tag, 
                              {'type': node_type,
                               'dpid': node.get('dpid') } ])
          elif node_type == 't':
            node_list.append([node.tag, 
                              {'type': node_type,
                               'ip': node.get('ip'),
                               'mac': node.get('mac'),
                               'proc_cap': node.get('proc_cap'),
                               'stor_cap': node.get('stor_cap') } ])
          else:
            raise KeyError('Unknown node_type')
        #
        edges = network.find('edges')
        for edge in edges:
          dev = edge.find('dev')
          session = edge.find('session')
          link_cap = edge.find('link_cap')
          edge_list.append([edge.get('pre_node'), edge.get('post_node'),
                            {'pre_dev': dev.get('pre_dev'),
                             'pre_node': dev_name_to_sw(dev.get('pre_dev')),
                             'post_dev': dev.get('post_dev') ,
                             'post_node': dev_name_to_sw(dev.get('post_dev')),
                             'bw': link_cap.get('bw'),
                             'delay': link_cap.get('delay'),
                             'loss': link_cap.get('loss'),
                             'max_queue_size': link_cap.get('max_queue_size')} ])
        #
    return [node_list, edge_list]

