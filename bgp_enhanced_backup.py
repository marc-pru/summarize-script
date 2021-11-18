import re
import jinja2
from netaddr import IPAddress, IPNetwork, cidr_merge
from vrf_database import get_vrf_name
from pprint import pprint

bgp_template_default = 'bgp_template.j2'
with open(bgp_template_default) as f:
    bgp_template = f.read()

bgp_template_remove_aggregate = 'bgp_remove_aggregate_template.j2'
with open(bgp_template_remove_aggregate) as f:
    bgp_remove_aggregate_template = f.read()

bgp_rollback_template = 'bgp_template_rollback.j2'
with open(bgp_rollback_template) as f:
    bgp_template_rollback = f.read()

def fetch_ips(print_output):
    bgp_prefixes = []
    bgp_potential_aggregates = []
    bgp_prefixes_dict = {}
    bgp_potential_aggregates_dict = {}
    output_list = print_output.splitlines()
    for line in output_list:
        if (re.search(r"^Route Distinguisher", line)):
            # nieuwe vrf is gevonden, we gaan veder met het volgende vrf, maken nieuwe dict_key aan (route distinghuisher) en resetten prefix-list 
            dict_key = (re.search(r"^Route Distinguisher:\s(\d+:\d+)", line).group(1))
            bgp_prefixes = []
            bgp_potential_aggregates = []
        if (re.search(r"\s+\*>\s+\d+.\d+.\d+.\d+", line) and re.search(r"\s+\*>\s+(\d+.\d+.\d+.\d+)/\d+", line)): #prefixes with mask
            bgp_prefixes.append((re.search(r"\s+\*>\s+(\d+.\d+.\d+.\d+)/\d+", line).group(1),re.search(r"\s+\*>\s+(\d+.\d+.\d+.\d+)/(\d+)", line).group(2)))
            bgp_prefixes_dict[dict_key] = bgp_prefixes
            if(re.search(r"32768 i$", line)): # mogelijk is een bestaande summary route gevonden (weight = 32768, origin = IGP)
                bgp_potential_aggregates.append(bgp_prefixes[-1]) #laatst gevonden prefix
                bgp_potential_aggregates_dict[dict_key] =  bgp_potential_aggregates
        elif (re.search(r"\s+\*>\s+\d+.\d+.\d+.\d+", line)): #prefixes without mask (classfull networks
            bgp_prefixes.append((re.search(r"\s+\*>\s+(\d+.\d+.\d+.\d+)", line).group(1),''))
            bgp_prefixes_dict[dict_key] = bgp_prefixes
            if(re.search(r"32768 i$", line)): #mogelijk is een bestaande summary route gevonden (weight = 32768, origin = IGP)
                bgp_potential_aggregates.append(bgp_prefixes[-1]) #laatst gevonden prefix
                bgp_potential_aggregates_dict[dict_key] =  bgp_potential_aggregates
    return bgp_prefixes_dict, bgp_potential_aggregates_dict


def return_ips_tuple(bgp_prefixes):
    list_with_tuples = []
    for ip in bgp_prefixes:
        a = tuple(ip[0].split('.'))
        if ip[1] != '':
            list_with_tuples.append((a,ip[1]))
        elif 0 <= int(a[0]) < 128: # Class A network
            list_with_tuples.append((a,'8'))
        elif 128 <=  int(a[0]) < 192: # Class B network
            list_with_tuples.append((a,'16'))
        elif 192 <= int(a[0]) < 224: # Class C network
            list_with_tuples.append((a,'24'))
    return(list_with_tuples)        


def return_ip_address_list(bgp_prefixes):
    list_with_ipaddresses = []
    for ip in bgp_prefixes:
        a = tuple(ip[0].split('.')) #obtain first octect of IP address to obtain the class, if classfull
        if ip[1] != '':
            ip_a = ip[0]+'/'+ip[1]
        elif 0 <= int(a[0]) < 128: # Class A network
            ip_a = ip[0]+'/'+'8'
        elif 128 <=  int(a[0]) < 192: # Class B network
            ip_a = ip[0]+'/'+'16'
        elif 192 <= int(a[0]) < 224: # Class C network 
            ip_a = ip[0]+'/'+'24'
        list_with_ipaddresses.append(ip_a)
    return list_with_ipaddresses


def handle_bgp_output(print_output):
    retrieve_all_subnets_and_aggregates_from_show_command = fetch_ips(print_output)
    print(retrieve_all_subnets_and_aggregates_from_show_command)
    ips_raw_dict = retrieve_all_subnets_and_aggregates_from_show_command[0] 
    ips_raw_dict_potential_aggregates = retrieve_all_subnets_and_aggregates_from_show_command[1]
    print()
    for rd in ips_raw_dict: 
        ips_tuple = return_ips_tuple(ips_raw_dict[rd])
        vrf_name = get_vrf_name(rd)
        print('{:^40}'.format('VRF {}:').format(vrf_name))
        for ip in ips_tuple:
            print('{:>21}'.format('['+ip[0][0])+'.'+'{:>3}'.format(ip[0][1])+'.'+'{:>3}'.format(ip[0][2])+'.'+'{:>3}'.format(ip[0][3])+' / '+'{:>2}'.format(ip[1])+']') 
        print()
    ips_dict = {}
    ips_aggregates_dict = {}
    for rd in ips_raw_dict:
        vrf_name = get_vrf_name(rd)
        ip_list = return_ip_address_list(ips_raw_dict[rd])
        ips_dict[vrf_name] = ip_list
    for rd in ips_raw_dict_potential_aggregates:
        vrf_name = get_vrf_name(rd)
        ip_list = return_ip_address_list(ips_raw_dict_potential_aggregates[rd])
        ips_aggregates_dict[vrf_name] = ip_list  
    return ips_dict, ips_aggregates_dict

def get_bgp_config_jinja(bgp_vrf_dict, bgp_remove_aggregate_dict = {}):
    bgp_vars = {}
    bgp_vrf_dict_masks = {}
    bgp_remove_aggregate_dict_masks = {}

    for vrf,summaries in bgp_vrf_dict.items():
       bgp_vrf_dict_masks[vrf] = {}
       for summary in summaries: 
           summary_IP = IPNetwork(summary)
           summary_network = str(summary_IP.network)
           summary_mask = summary_IP.netmask
           bgp_vrf_dict_masks[vrf][summary_network] = {}
           bgp_vrf_dict_masks[vrf][summary_network] = str(summary_IP.netmask) 

    for vrf,summaries in bgp_remove_aggregate_dict.items():
       bgp_remove_aggregate_dict_masks[vrf] = {}
       for summary in summaries:
           summary_IP = IPNetwork(summary)
           summary_network = str(summary_IP.network)
           summary_mask = summary_IP.netmask
           bgp_remove_aggregate_dict_masks[vrf][summary_network] = {}
           bgp_remove_aggregate_dict_masks[vrf][summary_network] = str(summary_IP.netmask)
    
    bgp_vars['bgp_vrf_dict'] = bgp_vrf_dict_masks
    bgp_vars['bgp_remove_aggregate_dict'] = bgp_remove_aggregate_dict_masks
    template = jinja2.Template(bgp_template)
    config = template.render(bgp_vars)
    return(config)
  
def get_bgp_remove_config_jinja(bgp_remove_aggregate_dict):
    bgp_vars = {}
    bgp_remove_aggregate_dict_masks = {}

    for vrf,summaries in bgp_remove_aggregate_dict.items():
       bgp_remove_aggregate_dict_masks[vrf] = {}
       for summary in summaries:
           summary_IP = IPNetwork(summary)
           summary_network = str(summary_IP.network)
           summary_mask = summary_IP.netmask
           bgp_remove_aggregate_dict_masks[vrf][summary_network] = {}
           bgp_remove_aggregate_dict_masks[vrf][summary_network] = str(summary_IP.netmask)
  
    bgp_vars['bgp_remove_aggregate_dict'] = bgp_remove_aggregate_dict_masks
    template = jinja2.Template(bgp_template)
    config = template.render(bgp_vars)
    return(config)

def get_bgp_rollback_config_jinja(bgp_vrf_dict, bgp_remove_aggregate_dict = {}):
    bgp_vars = {}
    bgp_vrf_dict_masks = {}
    bgp_remove_aggregate_dict_masks = {}

    for vrf,summaries in bgp_vrf_dict.items():
       bgp_vrf_dict_masks[vrf] = {}
       for summary in summaries:
           summary_IP = IPNetwork(summary)
           summary_network = str(summary_IP.network)
           summary_mask = summary_IP.netmask
           bgp_vrf_dict_masks[vrf][summary_network] = {}
           bgp_vrf_dict_masks[vrf][summary_network] = str(summary_IP.netmask)

    for vrf,summaries in bgp_remove_aggregate_dict.items():
       bgp_remove_aggregate_dict_masks[vrf] = {}
       for summary in summaries:
           summary_IP = IPNetwork(summary)
           summary_network = str(summary_IP.network)
           summary_mask = summary_IP.netmask
           bgp_remove_aggregate_dict_masks[vrf][summary_network] = {}
           bgp_remove_aggregate_dict_masks[vrf][summary_network] = str(summary_IP.netmask)

    bgp_vars['bgp_vrf_dict'] = bgp_vrf_dict_masks
    bgp_vars['bgp_remove_aggregate_dict'] = bgp_remove_aggregate_dict_masks
    template = jinja2.Template(bgp_template_rollback)
    config = template.render(bgp_vars)
    return(config)

def get_bgp_config(bgp_vrf_dict): #obsolete
    config_string1 = """
conf t
router bgp 65000
"""
    config_string2 = "" 
    for vrf in bgp_vrf_dict:
        config_string2 += 'address-family ipv4 vrf {}'.format(vrf)+'\n'
        for summary in bgp_vrf_dict[vrf]:
            summary_IP = IPNetwork(summary)
            config_string2 += " aggregate-address {} {} summary-only".format(summary_IP.network,summary_IP.netmask)+"\n"
        config_string2 += "exit-address-family"+"\n"
        config_string2 += "end"+"\n"+"\n"
    if config_string2 != '': 
        config = config_string1 + config_string2
    else: config = ''
    return config

def get_bgp_rollback_config(bgp_vrf_dict): #obsolete
    config_string1 = """
conf t
router bgp 65000
"""
    config_string2 = ""
    for vrf in bgp_vrf_dict:
        config_string2 += 'address-family ipv4 vrf {}'.format(vrf)+'\n'
        for summary in bgp_vrf_dict[vrf]:
            summary_IP = IPNetwork(summary)
            config_string2 += " no aggregate-address {} {} summary-only".format(summary_IP.network,summary_IP.netmask)+"\n"
        config_string2 += "exit-address-family"+"\n"
        config_string2 += "end"+"\n"+"\n"
    if config_string2 != '':
        config = config_string1 + config_string2
    else: config = ''
    return config

