import sys
from nodes import all_nodes, all_depv_vrf, other_vrf 
import bgp_enhanced
import json
from netaddr import IPAddress, IPNetwork, cidr_merge
from cidr_merge_advanced import cidr_merge_advanced, read_bgp_all_routes_dict_json, check_summary_overlaps_with_other_route, check_summary_overlaps_with_an_existing_aggregate
from netmiko import Netmiko
from netmiko.ssh_exception import NetMikoTimeoutException
from paramiko.ssh_exception import SSHException
from paramiko import SSHClient
from netmiko.ssh_exception import AuthenticationException
from getpass import getpass
from pprint import pprint
import genie
# Connecthandler

sys.setrecursionlimit(4000)

def goto_sleep(seconds):
    import time
    time.sleep(seconds)
 
print('\n'*40)
print('{:<30}'.format('>'*30)+'{:^40}'.format('JN4 BGP AGGREGATE SCRIPT')+'{:>30}'.format('<'*30))
print('{:^104}'.format('This script will determine potential BGP summary routes to be applied on the CPE.'))
print('{:^104}'.format('The script must be run twice in order to build up a local database with all prefixes.'))
print('{:<52}'.format('>'*52)+'{:>52}'.format('<'*52))
print('\n'*5)
username = input("username: ")
password = getpass()

#all_core_nodes = [ 'jn4bd01gv07' ]
all_core_nodes = all_nodes.splitlines()
all_depv_vrf = all_depv_vrf.splitlines()
other_vrf = other_vrf.splitlines()
global_counter = 0
bgp_summary_dict = {}
devices_no_connection = []
bgp_counters_dict = {}
bgp_all_routes_dict = {}
bgp_remove_aggregate_dict = {}
bgp_default_vrf_dict = {}
try:
    bgp_all_routes_dict_previousattempt = read_bgp_all_routes_dict_json('bgp_all_routes_dict.json')
    print()
    print("Alle BGP routes van de vorige run zijn succesvol ingelezen.....")
    print("Summary Overlapping checks kunnen nu worden uitgevoerd.")
    print()
    script_already_run = True
except Exception:
    print()
    print("Dit is de eerste keer dat het script wordt gerund. Run het hierna nog een keer zodat een overlap check kan worden gedaan.")
    print()
    script_already_run = False

for node in all_core_nodes:

    output = ''
    bgp_vrf_dict = {}
    
    node_dict = {
    'host': node,
    'username': username,
    'password': password,
    'device_type': 'cisco_ios',
    'global_delay_factor': 2}

#    print(node_dict)
    print("Verbinding maken met:", node)
    
    try: 
        net_conn = Netmiko(**node_dict)
        neighbors_default = net_conn.send_command("show bgp ipv4 unicast summary", use_genie=True)
        list_neighbors_default = []

        # create bgp neighbor list vrf default
        if "bgp_id" in neighbors_default: # only if ipv4 neighbors exist
            for neighbor in neighbors_default['vrf']['default']['neighbor']:
                if IPAddress(neighbor) in IPNetwork('1.0.0.0/8'): # only consider networks advertised to T-Mobile PE's
                    list_neighbors_default.append(neighbor)

        neighbors_other_vrf = net_conn.send_command("show bgp vpnv4 unicast all summary", use_genie=True)
        list_of_neighbors_other_vrf = [] 

        # create bgp neighbor all other vrfs
        if "bgp_id" in neighbors_other_vrf:  #only if vpnv4 neighbors exist
            for neighbor in neighbors_other_vrf['vrf']['default']['neighbor']:
                if IPAddress(neighbor) in IPNetwork('1.0.0.0/8'): # only consider networks advertised to T-Mobile PE's
                    list_of_neighbors_other_vrf.append(neighbor)
       
        # send the actual show bgp commands to the CPE router
        output = ''
        for neighbor in list_neighbors_default:
            output += "(default for vrf default)"+"\n"
            output += net_conn.send_command("show bgp ipv4 unicast neighbors {} advertised-routes".format(neighbor), use_textfsm=True)     
            output += '\n'
        for neighbor in list_of_neighbors_other_vrf:
            output += net_conn.send_command("show bgp vpnv4 unicast all neighbors {} advertised-routes".format(neighbor), use_textfsm=True)
            output += '\n'
        print()
        print("Router", node_dict['host'], "adverteert de volgende prefixes via BGP:")
        print()
        #ip_dict_router = bgp_enhanced.handle_bgp_output(output) #let op ip_dict_router[0] bevat al de geadverteerde routes, ip_dict_router[1] mogelijk al geconfigureerde aggregates
        ip_dict_router = bgp_enhanced.handle_bgp_output_jn4(output, node, all_depv_vrf, other_vrf) #let op ip_dict_router[0] bevat al de geadverteerde routes, ip_dict_router[1] mogelijk al geconfigureerde aggregates
        bgp_all_routes_dict[node] = ip_dict_router[0]
        # now store the default vrf for each CPE in a dictionary
        bgp_default_vrf_dict[node] = ip_dict_router[2]
        
        for vrf_type in ip_dict_router[1]:
            if ip_dict_router[1][vrf_type] != {}:
                print("Er zijn mogelijk al BGP aggregates aanwezig op deze router:")
                print()
        #controleer op voor geconfigureerde _aggregates
        for vrf_type in ip_dict_router[1]: 
            dict_keys_to_be_deleted = []
            for vrf in ip_dict_router[1][vrf_type]:
                for aggregate in ip_dict_router[1][vrf_type][vrf]:
                    print("Check of de gevonden aggregate {} in vrf {} ook echt configureerd is:".format(aggregate, vrf))
                    if vrf == 'default':
                        output = net_conn.send_command("show ip bgp {} | include atomic-aggregate".format(aggregate), use_textfsm=True)
                    else: output = net_conn.send_command("show bgp vpnv4 unicast all {} | include atomic-aggregate".format(aggregate), use_textfsm=True)
                    if "atomic-aggregate" in output:
                        print("                                     >>>>>>>CHECK<<<<<<<")
                    else:
                        print("                                     >>>>>>UNCHECK<<<<<<")
                        ip_dict_router[1][vrf_type][vrf].remove(aggregate)
                        if ip_dict_router[1][vrf_type][vrf] == []:
                            dict_keys_to_be_deleted.append(vrf)
                    print()
                    goto_sleep(2)
            for key in dict_keys_to_be_deleted:
                del ip_dict_router[1][vrf_type][vrf]
  
        print()
        print("Mogelijke BGP Summary Routes:")
        print()
        counter = 0
        print_geen_flag = True # alleen bij deze flag kan "geen" worden geprint op scherm
        for vrf_type in ip_dict_router[0]:
            for vrf in ip_dict_router[0][vrf_type]:
                #vrf = get_vrf_name(rd)
                summary_list = []
                if script_already_run:
                     summary_list = cidr_merge_advanced(ip_dict_router[0][vrf_type][vrf], ip_dict_router[0][vrf_type][vrf][0], current_list_of_summary_nets = [], check_overlap = True, vrf = vrf, input_node = node, bgp_all_routes_dict = bgp_all_routes_dict_previousattempt, current_networks_contained_in_pending_summary = [])
                else:
                    summary_list = cidr_merge_advanced(ip_dict_router[0][vrf_type][vrf], ip_dict_router[0][vrf_type][vrf][0], current_list_of_summary_nets = [])
                    #print("huidige summary_list:", summary_list)
                set_summaries = set(summary_list)
                set_ips = set([IPNetwork(ip) for ip in ip_dict_router[0][vrf_type][vrf]])
                difference_sets = set_summaries - set_ips
                counter += (len(set_ips) - len(set_summaries))
                #print(counter)
                if difference_sets != set():
                    bgp_vrf_dict[vrf] = [str(ip) for ip in difference_sets]
                    for ip in difference_sets:
                        print(ip)
                    print_geen_flag = False
                #elif difference_sets == set() and print_geen_flag:
        if print_geen_flag:
            print("Geen")
            #print()
        global_counter += counter
        bgp_counters_dict[node_dict['host']] = counter
   
       # now let's handle existing bgp aggregates in config  
        bgp_vrf_dict_remove_aggregates = {}
        for vrf_type in ip_dict_router[1]:
            if ip_dict_router[1][vrf_type] != {}:
                for vrf in ip_dict_router[1][vrf_type]:
                    list_of_remove_aggregates = []
                    for aggregate in ip_dict_router[1][vrf_type][vrf]:
                        if check_summary_overlaps_with_an_existing_aggregate(aggregate, vrf, bgp_vrf_dict, True):
                            list_of_remove_aggregates.append(aggregate)
                    if list_of_remove_aggregates != []:
                        bgp_vrf_dict_remove_aggregates[vrf] = list_of_remove_aggregates 
            if bgp_vrf_dict_remove_aggregates != {}:
                bgp_remove_aggregate_dict[node_dict['host']] = bgp_vrf_dict_remove_aggregates

        if bgp_vrf_dict != {}:
            bgp_summary_dict[node_dict['host']] = bgp_vrf_dict
            bgp_vrf_dict = {}
          

        print("-"*80)
        print("Totale besparing door summarization op BGP-tabel door deze router: {} entries".format(counter))
        print("-"*80)
        if bgp_vrf_dict == {} and (ip_dict_router[1]['depv_vrf'] != {} or ip_dict_router[1]['non_depv_vrf'] != {}):
            print("Deze router heeft al bgp-aggregates geconfigureerd, en die zijn nog up-to-date!")
            print("-"*80)
            print()
        if bgp_vrf_dict != {}:
            print("Config to be parsed on router {}:".format(node_dict['host']))
            print(bgp_enhanced.get_bgp_config_jinja(node, bgp_vrf_dict,bgp_default_vrf_dict,bgp_vrf_dict_remove_aggregates))
            print("-"*80)
        net_conn.disconnect()
        goto_sleep(5)
    except AuthenticationException:
        print('Authentication Failure: ' + node)
        #unsuccessfull_hosts[node] = 'Authentication Failure.'
        devices_no_connection.append(node_dict['host'])        
        break

    except NetMikoTimeoutException:
        print ('\n' + 'Timeout to device: ' + node)
        #unsuccessfull_hosts[node] = 'Device not reachable.'
        devices_no_connection.append(node_dict['host'])
        continue

    except AssertionError:
        print("Kan geen verbinding maken")
        devices_no_connection.append(node_dict['host'])
    
    devices_notreachable_json = json.dumps(devices_no_connection, sort_keys=True, indent=4)
    bgp_summary_dict_json = json.dumps(bgp_summary_dict, sort_keys=True, indent=4)
    bgp_counters_dict_json = json.dumps(bgp_counters_dict, sort_keys=True, indent=4)
    bgp_all_routes_dict_json = json.dumps(bgp_all_routes_dict, sort_keys=True, indent=4)
    bgp_remove_aggregate_dict_json = json.dumps(bgp_remove_aggregate_dict, sort_keys=True, indent=4)
    bgp_default_vrf_dict_json = json.dumps(bgp_default_vrf_dict, sort_keys=True, indent=4)
    fout1 = open('devices_notreachable.json', 'wt')
    fout2 = open('bgp_summary_dict.json', 'wt')
    fout3 = open('bgp_counters_dict.json', 'wt')
    fout4 = open('bgp_all_routes_dict.json', 'wt')
    fout5 = open('bgp_remove_aggregate_dict.json', 'wt')
    fout6 = open('bgp_default_vrf_dict.json', 'wt')
    fout1.write(devices_notreachable_json)
    fout2.write(bgp_summary_dict_json)
    fout3.write(bgp_counters_dict_json)
    fout4.write(bgp_all_routes_dict_json)
    fout5.write(bgp_remove_aggregate_dict_json)
    fout6.write(bgp_default_vrf_dict_json)
    fout1.close() 
    fout2.close()
    fout3.close()
    fout4.close()
    fout5.close()
    fout6.close()

bgp_counters_dict['_besparingen_bgp_tabel_totaal'] = global_counter
print("Totale besparing door summarization op BGP-tabel door alle routers: {} entries".format(global_counter))
if devices_no_connection:
    print("Devices die niet bereikbaar waren:")
    for device in devices_no_connection:
        print(device)

pprint(bgp_remove_aggregate_dict)
print(devices_notreachable_json)
if script_already_run: 
    print("De volgende summary routes zijn per node aanbevolen:")
    pprint(bgp_summary_dict_json)
