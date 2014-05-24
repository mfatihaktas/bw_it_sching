from errors import ParseError
from xml.dom import minidom
try:
    import xml.etree.cElementTree as ET
except ImportError:
    import xml.etree.ElementTree as ET

import pprint,json

class RuleParser (object):
  def __init__ (self, walkrule_xmlfile_url, itjobrule_xmlfile_url):
    self.walkrule_xmlfile_url=walkrule_xmlfile_url
    self.itjobrule_xmlfile_url=itjobrule_xmlfile_url
    #
    self.walkrule_tree = ET.parse(walkrule_xmlfile_url)
    self.itjobrule_tree = ET.parse(itjobrule_xmlfile_url)
    #
    self.walkrule_root = self.walkrule_tree.getroot()
    self.itjobrule_root = self.itjobrule_tree.getroot()
  
  def indent(self, elem, level=0):
    i = "\n" + level*"  "
    if len(elem):
      if not elem.text or not elem.text.strip():
        elem.text = i + "  "
      if not elem.tail or not elem.tail.strip():
        elem.tail = i
      for elem in elem:
        self.indent(elem, level+1)
      if not elem.tail or not elem.tail.strip():
        elem.tail = i
    else:
      if level and (not elem.tail or not elem.tail.strip()):
        elem.tail = i
  
  def prettify(self, elem):
    '''Return a pretty-printed XML string for the Element.
    '''
    rough_string = ET.tostring(elem, 'utf-8')
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent="  ")
  
####################  For scheditjob_xmlfile operations #########################
  def modify_scheditjobxmlfile_by_itjobrule(self, s_id, p_id, conn_itjobrulelist_dict):
    '''
    Modify the scheditjob_xmlfile according to newly rxed itjobrule
     - s_id and p_id are string
    '''
    for child in self.itjobrule_root:
      if child.get('s_id') == s_id and child.get('p_id') == p_id:
        self.itjobrule_root.remove(child) #old itjobrule for session is deleted
    #write the new s_itjobrule
    new_session = ET.Element('session')
    new_session.set('s_id', s_id)
    new_session.set('p_id', p_id)
    for conn_dpid,itjobrule_list in conn_itjobrulelist_dict.items():
      new_conn = ET.SubElement(new_session, 'connection')
      new_conn.set('dpid', conn_dpid)
      for itjobrule in itjobrule_list:
        new_itjob = ET.SubElement(new_conn, 'itjob')
        #
        new_uptojobinfo = ET.SubElement(new_itjob, 'uptojobinfo')
        for itfunc,comp in itjobrule['completeduptohere_job'].items():
          new_itfunc = ET.SubElement(new_uptojobinfo, 'func')
          new_itfunc.set('n',str(comp))
          new_itfunc.set('tag',itfunc)
        #
        new_jobinfo = ET.SubElement(new_itjob, 'jobinfo')
        ji_dict = itjobrule['assigned_job']
        new_jobinfo.set('proc', str(ji_dict['proc']))
        new_jobinfo.set('data_to_ip', itjobrule['consumer_ip'])
        new_jobinfo.set('proto', str(itjobrule['proto']))
        new_jobinfo.set('s_tp', str(itjobrule['session_tp']))
        new_jobinfo.set('datasize', str(itjobrule['datasize']))
        new_jobinfo.set('bw', str(itjobrule['bw']))
        for itfunc,n in ji_dict['itfunc_dict'].items():
          new_itfunc = ET.SubElement(new_jobinfo, 'func')
          new_itfunc.set('n',str(n))
          new_itfunc.set('tag',itfunc)
        #
        new_walkinfo = ET.SubElement(new_itjob, 'walkinfo')
        new_walkinfo.set('swdev_to_node',itjobrule['swdev_to_tpr'])
        new_walkinfo.set('node_ip',itjobrule['tpr_ip'])
        new_walkinfo.set('node_mac',itjobrule['tpr_mac'])
    self.itjobrule_root.append((new_session))
    self.indent(self.itjobrule_root,0)
    """
    print '***'
    print ET.dump(self.itjobrule_root)
    print '***'
    """
    self.itjobrule_tree.write(self.itjobrule_xmlfile_url)
  
  def get_itjobruledict_forsp(self, s_id, p_id):
    #s_id and p_id are string
    #hmfromdpid_dict = {}
    dict_ = {} #conndpid_itjoblist
    for session in self.itjobrule_root:
      if session.get('s_id') == s_id and session.get('p_id') == p_id:
        for conn in session.iter('connection'):
          dpid = conn.get('dpid')
          dict_[dpid] = []
          for itjob in conn.iter('itjob'):
            itjob_dict = {}
            #
            uptojobinfo = itjob.find('uptojobinfo')
            uptoitfunc_dict = {}
            for func in uptojobinfo.iter('func'):
              uptoitfunc_dict[func.get('tag')] = float(func.get('n'))
            #
            jobinfo = itjob.find('jobinfo')
            itfunc_dict = {}
            for func in jobinfo.iter('func'):
              itfunc_dict[func.get('tag')] = float(func.get('n'))
            #
            itjob_dict['jobinfo'] = {'proc':float(jobinfo.get('proc')),
                                     'uptoitfunc_dict':uptoitfunc_dict,
                                     'itfunc_dict':itfunc_dict,
                                     'proto':int(jobinfo.get('proto')),
                                     's_tp':int(jobinfo.get('s_tp')),
                                     'data_to_ip':jobinfo.get('data_to_ip'),
                                     'datasize':float(jobinfo.get('datasize')),
                                     'bw':float(jobinfo.get('bw')) }
            walkinfo = itjob.find('walkinfo')
            itjob_dict['walkinfo'] = {'swdev_to_itr':walkinfo.get('swdev_to_node'),
                                      'itr_ip':walkinfo.get('node_ip'),
                                      'itr_mac':walkinfo.get('node_mac') }
            #
            dict_[dpid].append(itjob_dict)
        return dict_
  
####################  For schedwalk_xmlfile operations #########################
  def modify_schedwalkxmlfile_by_walkrule(self, s_id, p_id, walkrule):
    '''
    Modify the schedwalk_xmlfile according to newly rxed walkrule
     - s_id and p_id are string
    '''
    for child in self.walkrule_root:
      if child.get('s_id') == s_id and child.get('p_id') == p_id:
        self.walkrule_root.remove(child) #old walkrule for session is deleted
    #write the new s_walkrule
    new_session = ET.Element('session')
    new_session.set('s_id', s_id)
    new_session.set('p_id', p_id)
    for step_dict in walkrule:
      new_conn = ET.SubElement(new_session, 'connection')
      new_conn.set('dpid', str(step_dict['conn'][0]))
      new_conn.set('from', step_dict['conn'][1])
      new_type = ET.SubElement(new_conn, 'type')
      new_type.text = step_dict['typ']
      new_wcs = ET.SubElement(new_conn, 'wildcards')
      new_wcs.set('src_ip',step_dict['wc'][0])
      new_wcs.set('dst_ip',step_dict['wc'][1])
      new_wcs.set('nw_proto',str(step_dict['wc'][2]))
      new_wcs.set('tp_src',str(step_dict['wc'][3]))
      new_wcs.set('tp_dst',str(step_dict['wc'][4]))
      new_rule = ET.SubElement(new_conn, 'rule')
      if new_type.text == 'forward':
        new_rule.set('fport', step_dict['rule'][0])
        new_rule.set('duration', str(step_dict['rule'][1]))
      elif new_type.text == 'mod_nw_src__forward':
        new_rule.set('new_src_ip', step_dict['rule'][0])
        new_rule.set('new_src_mac', step_dict['rule'][1])
        new_rule.set('fport', step_dict['rule'][2])
        new_rule.set('duration', str(step_dict['rule'][3]) )
      elif new_type.text == 'mod_nw_dst__forward':
        new_rule.set('new_dst_ip', step_dict['rule'][0])
        new_rule.set('new_dst_mac', step_dict['rule'][1])
        new_rule.set('fport', step_dict['rule'][2])
        new_rule.set('duration', str(step_dict['rule'][3]) )
      else:
        raise ParseError('Unexpected type', new_type.text)
    self.walkrule_root.append((new_session))
    self.indent(self.walkrule_root,0)
    """
    print '***'
    print ET.dump(self.walkrule_root)
    print '***'
    """
    self.walkrule_tree.write(self.walkrule_xmlfile_url)
  
  def get_walkruledict_forsp(self, s_id, p_id):
    #s_id and p_id are string
    hmfromdpid_dict = {}
    dict_ = {}
    for session in self.walkrule_root:
      if session.get('s_id') == s_id and session.get('p_id') == p_id:
        for conn in session.iter('connection'):
          dpid = conn.get('dpid')
          #
          typ = conn.find('type').text
          wc = conn.find('wildcards')
          wc_dict = {}
          wc_dict['src_ip'] = wc.get('src_ip')
          wc_dict['dst_ip'] = wc.get('dst_ip')
          wc_dict['nw_proto'] = wc.get('nw_proto')
          wc_dict['tp_src'] = wc.get('tp_src')
          wc_dict['tp_dst'] = wc.get('tp_dst')
          #
          rule = conn.find('rule')
          rule_dict = {}
          if typ == 'forward':
            rule_dict['fport'] = rule.get('fport')
            rule_dict['duration'] = rule.get('duration')
          elif typ == 'mod_nw_src__forward':
            rule_dict['new_src_ip'] = rule.get('new_src_ip')
            rule_dict['new_src_mac'] = rule.get('new_src_mac')
            rule_dict['fport'] = rule.get('fport')
            rule_dict['duration'] = rule.get('duration')
          elif typ == 'mod_nw_dst__forward':
            rule_dict['new_dst_ip'] = rule.get('new_dst_ip')
            rule_dict['new_dst_mac'] = rule.get('new_dst_mac')
            rule_dict['fport'] = rule.get('fport')
            rule_dict['duration'] = rule.get('duration')
          else:
            raise ParseError('Unexpected type', typ)
          #
          if dpid in hmfromdpid_dict:
            hmfromdpid_dict[dpid] += 1;
          else:
            hmfromdpid_dict[dpid] = 0
          #
          tup = dpid, hmfromdpid_dict[dpid]
          dict_[tup] = { 'typ': typ, 'wc_dict': wc_dict, 'rule_dict': rule_dict}
        return [dict_, hmfromdpid_dict]
  """
  #by sending json_walkrule from scher to cont1, (not in xml_walkrule)
  #DEPRECATED
  def rule_dict_rxed_cmd_from_sch(self, xml_walkrule):
    dict_ = {}
    root = ET.fromstring(xml_walkrule)
    for child in root:
      #print "child.get('number'): ", child.get('number')
      s_id = child.get('number')
      dict_[s_id] = {}
      for conn in child.iter('connection'):
        dpid = conn.get('dpid')
        fromm = conn.get('from')
        tup = dpid, fromm

        typ = conn.find('type').text
        wc = conn.find('wildcards')
        wc_dict = {}
        wc_dict['src_ip'] = wc.get('src_ip')
        wc_dict['dst_ip'] = wc.get('dst_ip')
        wc_dict['tp_dst'] = wc.get('tp_dst')

        rule = conn.find('rule')
        rule_dict = {}
        if typ == 'forward':
          rule_dict['fport'] = rule.get('fport')
          rule_dict['duration'] = rule.get('duration')
        elif typ == 'modify_forward':
          rule_dict['new_dst_ip'] = rule.get('new_dst_ip')
          rule_dict['new_dst_mac'] = rule.get('new_dst_mac')
          rule_dict['fport'] = rule.get('fport')
          rule_dict['duration'] = rule.get('duration')
        else:
          print 'Unrecognized rule type'

        dict_[s_id][tup] = { 'typ': typ, 'wc_dict': wc_dict, 'rule_dict': rule_dict}

    return dict_
  """
###################################  OOO  ######################################
def main():
  my_p = RuleParser('schedwalks.xml', 'scheditjobs.xml')
  '''
  rule_dict = my_p.walkrule_dict_for_session_I('1')
  for k,v in rule_dict.iteritems():
    print k, "- ", v, "\n"
  
  print my_p.hmfromdpid_dict
  '''
  itjob_rule ={'1': [{'assigned_job': {'comp': 2.8333333331303283,
                                       'itfunc_dict': {'f1': 2, 'f2': 0.8333333331303283},
                                       'proc': 288.9353187878799},
                      'consumer_ip': '10.0.0.1',
                      'session_tp': 6000,
                      'swdev_to_tpr': 's1-eth4',
                      'tpr_ip': '10.0.0.11',
                      'tpr_mac': '00:00:00:00:01:01'}],
               '2': [{'assigned_job': {'comp': 2.8333333331303283,
                                       'itfunc_dict': {'f2': 0.3333333337393434,
                                                       'f3': 2.499999999390985},
                                       'proc': 288.9353187878799},
                      'consumer_ip': '10.0.0.1',
                      'session_tp': 6000,
                      'swdev_to_tpr': 's2-eth4',
                      'tpr_ip': '10.0.0.21',
                      'tpr_mac': '00:00:00:00:02:01'}],
               '3': [{'assigned_job': {'comp': 2.8333333331303283,
                                       'itfunc_dict': {'f2': 2.8333333331303283},
                                       'proc': 288.9353187878799},
                      'consumer_ip': '10.0.0.1',
                      'session_tp': 6000,
                      'swdev_to_tpr': 's3-eth3',
                      'tpr_ip': '10.0.0.31',
                      'tpr_mac': '00:00:00:00:03:01'}]}
  s_id, p_id = '0', '0'
  my_p.modify_scheditjobxmlfile_by_itjobrule(s_id, p_id, itjob_rule)
  itjobrule = my_p.get_itjobruledict_forsp(s_id, p_id)
  print 'itjobrule:'
  pprint.pprint(itjobrule)

if __name__ == "__main__":
  main()



