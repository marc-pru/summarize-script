import nodes
import bgp_enhanced
import json
from vrf_database import get_vrf_name
from netaddr import IPAddress, IPNetwork, cidr_merge
from cidr_merge_advanced import cidr_merge_advanced, read_bgp_all_routes_dict_json, check_summary_overlaps_with_other_route, check_summary_overlaps_with_an_existing_aggregate
from netmiko import Netmiko
from getpass import getpass
from pprint import pprint
# Connecthandler

def goto_sleep(seconds):
    import time
    time.sleep(seconds)
 

#password = getpass()
password = 'koXshEM1YJfn4'

#all_core_nodes = nodes.e1 + nodes.c1 + nodes.datacenter_nodes
all_core_nodes = nodes.c1 + nodes.datacenter_nodes + nodes.e1
#print(all_core_nodes)
#all_core_nodes = nodes.wilhelminakade_nodes
all_core_nodes = ['whk179-22-c1', 'whk179-22-c2'] 
#all_core_nodes = nodes.list_of_core_devices_lab
global_counter = 0
bgp_summary_dict = {}
devices_no_connection = []
bgp_counters_dict = {}
bgp_all_routes_dict = {}
bgp_remove_aggregate_dict = {}
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
    'username': "933513-adm",
    'password': password,
    'device_type': 'cisco_ios'}

#    print(node_dict)
    print("Verbinding maken met:", node)
    
    net_conn = Netmiko(**node_dict)
    output = net_conn.send_command("show bgp vpnv4 unicast all neighbor 10.3.0.1 advertised-routes", use_textfsm=True)
    print()
    print("Router", node_dict['host'], "adverteert de volgende prefixes via BGP:")
    print()
    ip_dict_router = bgp_enhanced.handle_bgp_output(output) #let op ip_dict_router[0] bevat al de geadverteerde routes, ip_dict_router[1] mogelijk al geconfigureerde aggregates
    bgp_all_routes_dict[node] = ip_dict_router[0]


    if ip_dict_router[1] != {}:
        print("Er zijn mogelijk voorgeconfigureerde BGP aggregates aanwezig op deze router:")
        pprint(ip_dict_router[1])
        print()
        #controleer op voor geconfigureerde _aggregates
    dict_keys_to_be_deleted = []
    for vrf in ip_dict_router[1]:
        for aggregate in ip_dict_router[1][vrf]:
            print("Check of de gevonden aggregate {} in vrf {} ook echt configureerd is:".format(aggregate, vrf))
            #print(".........")
            output = net_conn.send_command("show bgp vpnv4 unicast all {} | include atomic-aggregate".format(aggregate), use_textfsm=True)
            if "atomic-aggregate" in output:
                print(output)
                print("                                     >>>>>>>CHECK<<<<<<<")
            else:
                print("                                     >>>>>>UNCHECK<<<<<<")
                ip_dict_router[1][vrf].remove(aggregate)
                if ip_dict_router[1][vrf] == []:
                    dict_keys_to_be_deleted.append(vrf)
            print()
            goto_sleep(2)
    for key in dict_keys_to_be_deleted:
        del ip_dict_router[1][vrf]




    print()
    print("Mogelijke BGP Summary Routes:")
    print()
    counter = 0
    for vrf in ip_dict_router[0]:
        #vrf = get_vrf_name(rd)
        print("VRF", vrf)
        summary_list = []
        if script_already_run:
           summary_list = cidr_merge_advanced(ip_dict_router[0][vrf], ip_dict_router[0][vrf][0], current_list_of_summary_nets = [], check_overlap = True, vrf = vrf, input_node = node, bgp_all_routes_dict = bgp_all_routes_dict_previousattempt, current_networks_contained_in_pending_summary = [])
        else:
            summary_list = cidr_merge_advanced(ip_dict_router[0][vrf], ip_dict_router[0][vrf][0], current_list_of_summary_nets = [])
        set_summaries = set(summary_list)
        set_ips = set([IPNetwork(ip) for ip in ip_dict_router[0][vrf]])
        difference_sets = set_summaries - set_ips
        counter += (len(set_ips) - len(set_summaries))
        #print(counter)
        if difference_sets == set():
            print("Geen")
        else:
            bgp_vrf_dict[vrf] = [str(ip) for ip in difference_sets]
            for ip in difference_sets:
                print(ip)
        print()
    global_counter += counter
    bgp_counters_dict[node_dict['host']] = counter
    if bgp_vrf_dict != {}:
        bgp_summary_dict[node_dict['host']] = bgp_vrf_dict

    bgp_vrf_dict_remove_aggregates = {}
    if ip_dict_router[1] != {}:
        for vrf in ip_dict_router[1]:
            list_of_remove_aggregates = []
            for aggregate in ip_dict_router[1][vrf]:
                if check_summary_overlaps_with_an_existing_aggregate(aggregate, vrf, bgp_vrf_dict, True):
                    list_of_remove_aggregates.append(aggregate)
            if list_of_remove_aggregates != []:
                bgp_vrf_dict_remove_aggregates[vrf] = list_of_remove_aggregates 
    if bgp_vrf_dict_remove_aggregates != {}:
        bgp_remove_aggregate_dict[node_dict['host']] =  bgp_vrf_dict_remove_aggregates

    print("-"*80)
    print("Totale besparing door summarization op BGP-tabel door deze router: {} entries".format(counter))
    print("-"*80)
    if bgp_vrf_dict == {} and ip_dict_router[1] != {}:
        print("Deze router heeft al bgp-aggregates geconfigureerd, en die zijn nog up-to-date!")
        print("-"*80)
        print()
    if bgp_vrf_dict != {}:
        print("Config to be parsed on router {}:".format(node_dict['host']))
        print(bgp_enhanced.get_bgp_config_jinja(bgp_vrf_dict, bgp_vrf_dict_remove_aggregates))
        print("-"*80)
    net_conn.disconnect()
    goto_sleep(5)
        

bgp_counters_dict['_besparingen_bgp_tabel_totaal'] = global_counter
print("Totale besparing door summarization op BGP-tabel door alle routers: {} entries".format(global_counter))
if devices_no_connection:
    print("Devices die niet bereikbaar waren:")
    for device in devices_no_connection:
        print(device)

devices_notreachable_json = json.dumps(devices_no_connection, sort_keys=True, indent=4)
bgp_summary_dict_json = json.dumps(bgp_summary_dict, sort_keys=True, indent=4)
bgp_counters_dict_json = json.dumps(bgp_counters_dict, sort_keys=True, indent=4)
bgp_all_routes_dict_json = json.dumps(bgp_all_routes_dict, sort_keys=True, indent=4)
print(devices_notreachable_json)
if script_already_run: 
    print("De volgende summary routes zijn per node aanbevolen:")
    pprint(bgp_summary_dict_json)

fout1 = open('devices_notreachable.json', 'wt')
fout2 = open('bgp_summary_dict.json', 'wt')
fout3 = open('bgp_counters_dict.json', 'wt')
fout4 = open('bgp_all_routes_dict.json', 'wt')
fout1.write(devices_notreachable_json)
fout2.write(bgp_summary_dict_json)
fout3.write(bgp_counters_dict_json)
fout4.write(bgp_all_routes_dict_json)
fout1.close()
fout2.close()
fout3.close()
fout4.close()
