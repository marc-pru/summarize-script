import bgp_enhanced
import json
from netaddr import IPNetwork, IPAddress

fin = open('bgp_default_vrf_dict.json', 'rt')
bgp_default_vrf_dict_json = fin.read()
fin.close()
bgp_default_vrf_dict = json.loads(bgp_default_vrf_dict_json)

def generate_used_vrfs_list(bgp_summary_dict):
   vrflist = []
   for node in bgp_summary_dict:
      a = [vrf for vrf in bgp_summary_dict[node]]
      vrflist += a
   a_set = set(vrflist)
   return a_set

def read_bgp_summary_json(filename1):
   fin1 = open(filename1, 'rt')
   bgp_summary_dict_json = fin1.read()
   fin1.close()
   bgp_summary_dict = json.loads(bgp_summary_dict_json)
   print("-"*80)
   output = ''
   for router in bgp_summary_dict:
      output += (router + '\n')
      output += (bgp_enhanced.get_bgp_config_jinja(router, bgp_summary_dict[router], bgp_default_vrf_dict) + '\n')
      output += ("-"*80 + '\n')
   fout = open('config_example.txt', 'wt')
   fout.write(output)
   fout.close()
   return bgp_summary_dict

def read_bgp_remove_aggregate_json(filename2):
   fin2 = open(filename2, 'rt')
   bgp_remove_aggregate_dict_json = fin2.read()
   fin2.close()
   bgp_remove_aggregate_dict = json.loads(bgp_remove_aggregate_dict_json)
   print("-"*80)
   output = ''
   for router in bgp_remove_aggregate_dict:
      output += (router + '\n')
      output += (bgp_enhanced.get_bgp_remove_config_jinja(router, bgp_remove_aggregate_dict[router], bgp_default_vrf_dict) + '\n')
      output += ("-"*80 + '\n')
   fout = open('config_remove_example.txt', 'wt')
   fout.write(output)
   fout.close()
   return bgp_remove_aggregate_dict

def generate_list_all_summaries_in_vrf(bgp_summary_dict, vrf):
   summary_list = []
   for node in bgp_summary_dict:
      try:
         for summary in bgp_summary_dict[node][vrf]:
            summary_list.append(IPNetwork(summary))
      except: KeyError
   return summary_list

def check_overlap_summary_list(summary_list):
   for summary1 in summary_list:
      for summary2 in summary_list:
         if set(summary1) == set(summary2):
            continue
         elif set(summary1) & set(summary2):
            print(summary1)
            print(summary2)
            print()

def check_overlap_all_vrfs(vrf_list, bgp_summary_dict):
   for vrf in vrf_list:
      print("check vrf {}".format(vrf))
      summary_list = generate_list_all_summaries_in_vrf(bgp_summary_dict, vrf)
      check_overlap_summary_list(summary_list)


bgp_summary_dict = read_bgp_summary_json('bgp_summary_dict.json')
bgp_remove_aggregate_dict = read_bgp_remove_aggregate_json('bgp_remove_aggregate_dict.json')
#vrf_list = list(generate_used_vrfs_list(bgp_nodes_dict))
#vrf_list.sort()
#check_overlap_all_vrfs(vrf_list, bgp_nodes_dict)

#for vrf in vrf_list:
#   print(vrf)

#test = generate_list_all_summaries_in_vrf(bgp_nodes_dict, 'citi')
#test.sort()
#for ip in test:
#   print(ip.network,'/',ip.prefixlen,sep='')

#check_overlap_summary_list(test)

def generate_config_per_node(bgp_summary_dict, bgp_remove_aggregate_dict, host_name):
    output = ''
    #output = (host_name + '\n')
    #output += '\n'
    if host_name in bgp_remove_aggregate_dict:
        output += (bgp_enhanced.get_bgp_config_jinja(host_name, bgp_summary_dict[host_name], bgp_default_vrf_dict, bgp_remove_aggregate_dict[host_name]) + '\n')
    else: output += (bgp_enhanced.get_bgp_config_jinja(host_name, bgp_summary_dict[host_name], bgp_default_vrf_dict) + '\n') 
    output += '\n'
    fout1 = open('config_{}.txt'.format(host_name), 'wt')
    fout1.write(output)
    fout1.close()
    return output
 
def generate_rollback_config_per_node(bgp_summary_dict,  bgp_remove_aggregate_dict, host_name):
    output = ''
    #output = (host_name + '\n')
    #output += '\n'
    if host_name in bgp_remove_aggregate_dict:
        output += (bgp_enhanced.get_bgp_rollback_config_jinja(host_name, bgp_summary_dict[host_name], bgp_default_vrf_dict, bgp_remove_aggregate_dict[host_name]) + '\n')
    else: output += (bgp_enhanced.get_bgp_rollback_config_jinja(host_name, bgp_summary_dict[host_name], bgp_default_vrf_dict) + '\n')
    output += '\n'
    fout1 = open('rollback_config_{}.txt'.format(host_name), 'wt')
    fout1.write(output)
    fout1.close()
    return output

node_input = input("Van welke node config en rollback config genereren? ")
if node_input == 'all':
    config = ''
    for node in bgp_summary_dict:
        config += generate_config_per_node(bgp_summary_dict,bgp_remove_aggregate_dict, node)
        config_rollback =  generate_rollback_config_per_node(bgp_summary_dict, bgp_remove_aggregate_dict, node)
else:
    try:
        config = generate_config_per_node(bgp_summary_dict, bgp_remove_aggregate_dict, node_input)
        config_rollback =  generate_rollback_config_per_node(bgp_summary_dict, bgp_remove_aggregate_dict, node_input)
    except KeyError:
        print("Deze router heeft geen summary routes nodig")
#config1 = generate_config_per_node(bgp_nodes_dict, 'whk179-22-c1')
#config1_rollback = generate_rollback_config_per_node(bgp_nodes_dict, 'whk179-22-c1')
#config2 = generate_config_per_node(bgp_nodes_dict, 'whk179-22-c2')
#config2_rollback = generate_rollback_config_per_node(bgp_nodes_dict, 'whk179-22-c2')

try: 
   print(config)
   print(config_rollback)
except Exception:
    pass
