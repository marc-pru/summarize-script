import re
import jinja2
from netaddr import IPAddress, IPNetwork, cidr_merge
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
        #if (re.search(r"^Route Distinguisher", line)):
        if (re.search(r"[(]default for vrf", line)):
            # nieuwe vrf is gevonden, we gaan veder met het volgende vrf, maken nieuwe dict_key aan (route distinghuisher) en resetten prefix-list 
            #dict_key = (re.search(r"^Route Distinguisher:\s(\d+:\d+)", line).group(1))
            dict_key = (re.search(r"[(]default for vrf\s(\S+)[)]", line).group(1))
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
        elif a == ('0', '0', '0', '0'):
            list_with_tuples.append((a,'0')) 
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
        elif a == ('0', '0', '0', '0'):
            ip_a = ip[0]+'/'+'0'
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
    #print(retrieve_all_subnets_and_aggregates_from_show_command)
    ips_raw_dict = retrieve_all_subnets_and_aggregates_from_show_command[0] 
    ips_raw_dict_potential_aggregates = retrieve_all_subnets_and_aggregates_from_show_command[1]
    print()
    for vrf_name in ips_raw_dict: 
        ips_tuple = return_ips_tuple(ips_raw_dict[vrf_name])
        #vrf_name = get_vrf_name(rd)
        print('{:^40}'.format('VRF {}:').format(vrf_name))
        for ip in ips_tuple:
            print('{:>21}'.format('['+ip[0][0])+'.'+'{:>3}'.format(ip[0][1])+'.'+'{:>3}'.format(ip[0][2])+'.'+'{:>3}'.format(ip[0][3])+' / '+'{:>2}'.format(ip[1])+']') 
        print()
    ips_dict = {}
    ips_aggregates_dict = {}
    for vrf_name in ips_raw_dict:
        #vrf_name = get_vrf_name(rd)
        ip_list = return_ip_address_list(ips_raw_dict[vrf_name])
        ips_dict[vrf_name] = ip_list
    for vrf_name in ips_raw_dict_potential_aggregates:
        #vrf_name = get_vrf_name(rd)
        ip_list = return_ip_address_list(ips_raw_dict_potential_aggregates[vrf_name])
        ips_aggregates_dict[vrf_name] = ip_list  
    return ips_dict, ips_aggregates_dict

def handle_bgp_output_jn4(print_output, hostname, depv_vrf_list, non_depv_vrf_list):
    retrieve_all_subnets_and_aggregates_from_show_command = fetch_ips(print_output)
    #print(retrieve_all_subnets_and_aggregates_from_show_command)
    ips_raw_dict = retrieve_all_subnets_and_aggregates_from_show_command[0]
    ips_raw_dict_potential_aggregates = retrieve_all_subnets_and_aggregates_from_show_command[1]
    print()
    for vrf_name in ips_raw_dict:
        ips_tuple = return_ips_tuple(ips_raw_dict[vrf_name])
        #vrf_name = get_vrf_name(rd)
        print('{:^40}'.format('VRF {}:').format(vrf_name))
        for ip in ips_tuple:
            print('{:>21}'.format('['+ip[0][0])+'.'+'{:>3}'.format(ip[0][1])+'.'+'{:>3}'.format(ip[0][2])+'.'+'{:>3}'.format(ip[0][3])+' / '+'{:>2}'.format(ip[1])+']')
        print()
    ips_dict = {}
    ips_dict['depv_vrf'] = {}
    ips_dict['non_depv_vrf'] = {}
    ips_aggregates_dict = {}
    ips_aggregates_dict['depv_vrf'] = {}
    ips_aggregates_dict['non_depv_vrf'] = {}
    modified_default_vrf = 'default'
    for vrf_name in ips_raw_dict:
        #vrf_name = get_vrf_name(rd)
        ip_list = return_ip_address_list(ips_raw_dict[vrf_name])
        try: # remove default from ip_list, as this route will overlap with any route, and cause all candidate summaries to be removed
            ip_list.remove('0.0.0.0/0')
        except ValueError:
            pass
        vrf_name_jn4 = modify_vrfname_jn4(vrf_name, hostname, depv_vrf_list, non_depv_vrf_list)
        vrf_root = vrf_name_jn4[0]
        vrf_update = vrf_name_jn4[1]
        try:
            if vrf_name == 'default':
                ips_dict[vrf_root][vrf_update] += ip_list
            else: ips_dict[vrf_root][vrf_name] += ip_list
        except KeyError:
            if vrf_name == 'default':
                ips_dict[vrf_root][vrf_update] = ip_list 
            else: ips_dict[vrf_root][vrf_name] = ip_list
        # now store the vrf that corresponds to the global route table on this CPE:
        if vrf_name == 'default':
            modified_default_vrf = vrf_update
    for vrf_name in ips_raw_dict_potential_aggregates:
        ip_list = return_ip_address_list(ips_raw_dict_potential_aggregates[vrf_name])
        try: # remove default from ip_list, as this route will overlap with any route, and cause all candidate summaries to be removed
            ip_list.remove('0.0.0.0/0')
        except ValueError:
            pass
        vrf_name_jn4 = modify_vrfname_jn4(vrf_name, hostname, depv_vrf_list, non_depv_vrf_list)
        vrf_root = vrf_name_jn4[0]
        vrf_update = vrf_name_jn4[1]
        try:
            if vrf_name == 'default':
                ips_aggregates_dict[vrf_root][vrf_update] += ip_list
            else: ips_dict[vrf_root][vrf_name] += ip_list
        except KeyError:
            if vrf_name == 'default':
                ips_dict[vrf_root][vrf_update] = ip_list
            else: ips_dict[vrf_root][vrf_name] = ip_list 
    return ips_dict, ips_aggregates_dict, modified_default_vrf

def modify_vrfname_jn4(vrf, hostname, depv_vrf_list, non_depv_vrf_list):
    # return tuple with root vrf (depv_vrf or non_depv_vrf) and modified vrf based on the hostname
    if vrf == 'default':
        for vrf_name in depv_vrf_list:
            if vrf_name in hostname:
                return ('depv_vrf', vrf_name) 
        for vrf_name in non_depv_vrf_list:
            if vrf_name in hostname:
                return ('non_depv_vrf', vrf_name) 
    else:
        for vrf_name in depv_vrf_list:
            if vrf_name in vrf:
                return ('depv_vrf', vrf_name)
        for vrf_name in non_depv_vrf_list: 
            if vrf_name in vrf:
                return ('non_depv_vrf', vrf_name) 
    return ('depv_vrf', vrf)
    
def get_bgp_config_jinja(hostname, bgp_vrf_dict, bgp_default_vrf_dict, bgp_remove_aggregate_dict = {}):
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
    
    bgp_vars['hostname'] = hostname 
    bgp_vars['bgp_vrf_dict'] = bgp_vrf_dict_masks
    bgp_vars['bgp_default_vrf_dict'] = bgp_default_vrf_dict
    bgp_vars['bgp_remove_aggregate_dict'] = bgp_remove_aggregate_dict_masks
    template = jinja2.Template(bgp_template)
    config = template.render(bgp_vars)
    return(config)
  
def get_bgp_remove_config_jinja(hostname, bgp_remove_aggregate_dict, bgp_default_vrf_dict):
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
  
    bgp_vars['hostname'] = hostname
    bgp_vars['bgp_default_vrf_dict'] = bgp_default_vrf_dict
    bgp_vars['bgp_remove_aggregate_dict'] = bgp_remove_aggregate_dict_masks
    template = jinja2.Template(bgp_template)
    config = template.render(bgp_vars)
    return(config)

def get_bgp_rollback_config_jinja(hostname, bgp_vrf_dict, bgp_default_vrf_dict, bgp_remove_aggregate_dict = {}):
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

    bgp_vars['hostname'] = hostname
    bgp_vars['bgp_vrf_dict'] = bgp_vrf_dict_masks
    bgp_vars['bgp_default_vrf_dict'] = bgp_default_vrf_dict
    bgp_vars['bgp_remove_aggregate_dict'] = bgp_remove_aggregate_dict_masks
    template = jinja2.Template(bgp_template_rollback)
    config = template.render(bgp_vars)
    return(config)
