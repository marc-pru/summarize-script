from netaddr import IPAddress, IPNetwork
from nodes import all_nodes, all_depv_vrf, other_vrf
from pprint import pprint
import json

all_depv_vrf = all_depv_vrf.splitlines()
other_vrf = other_vrf.splitlines()

def read_bgp_all_routes_dict_json(filename):
   fin = open(filename, 'rt')
   bgp_all_routes_dict_json = fin.read()
   fin.close()
   bgp_all_routes_dict = json.loads(bgp_all_routes_dict_json)
   print("bgp_all_routes_dict_ingelezen")
   return bgp_all_routes_dict

def cidr_merge_advanced(list_of_networks, start_summary, current_list_of_summary_nets = [], check_overlap = False, vrf = "", input_node = "", bgp_all_routes_dict = {}, current_networks_contained_in_pending_summary = []):
        if len(list_of_networks) == 0:
            return current_list_of_summary_nets
        summary = IPNetwork(start_summary).ip
        summary_net = IPNetwork(start_summary)
        prefix_length = IPNetwork(list_of_networks[0]).prefixlen
        min_overlap_required_mask = convert_prefix_length_to_mask(17) # grootste uitgegeven blokken per locatie zijn /17
        #current_networks_contained_in_pending_summary = []

        if not check_overlap:

            for i, network in enumerate(list_of_networks[1:]):

                if IPNetwork(network) in IPNetwork('1.0.0.0/8'): # geen summaries in T-Mobile segmenten
                    current_list_of_summary_nets.append(IPNetwork(network))
                    return cidr_merge_advanced(list_of_networks[i+1:], summary_net, current_list_of_summary_nets)

                elif IPNetwork(network).prefixlen >= 31: # geen summaries op point-to-point en loopback segmenten
                    current_list_of_summary_nets.append(IPNetwork(network))
                    return cidr_merge_advanced(list_of_networks[i+1:], summary_net, current_list_of_summary_nets)

                elif (IPNetwork(network).ip & min_overlap_required_mask) != (summary & min_overlap_required_mask):
                    # dit netwerk heeft niet voldoende overlap. We gaan door de naar het volgende netwerk. Summary wordt opgeslagen
                    current_list_of_summary_nets.append(summary_net)
                    current_networks_contained_in_pending_summary = []
                    return cidr_merge_advanced(list_of_networks[i+1:], list_of_networks[i+1], current_list_of_summary_nets)

                else:
                    prefix_length_new = 0
                    for x in range(0,32):
                        if format(int(IPNetwork(network).ip), '#034b')[x+2] == format(int(summary), '#034b')[x+2]:
                            prefix_length_new += 1
                        else:
                            break
                    prefix_length = min(prefix_length_new, IPNetwork(network).prefixlen)

                    if prefix_length < 16: # summaries met prefix kleiner dan 16 worden niet vertrouwd
                        current_list_of_summary_nets.append(IPNetwork(network))
                        return cidr_merge_advanced(list_of_networks[i+1:], summary_net, current_list_of_summary_nets)
       
                    else:
                        subnet_mask = convert_prefix_length_to_mask(prefix_length)
                        network_stripped = IPNetwork(network).ip & subnet_mask
                        summary = network_stripped & summary           
                        summary_net = IPNetwork(summary)
                        summary_net.prefixlen = prefix_length

            current_list_of_summary_nets.append(summary_net)
            current_list_of_summary_nets.sort()
            return current_list_of_summary_nets

        elif check_overlap:
            network_first_in_list = list_of_networks[0]

            for i, network in enumerate(list_of_networks[1:]):
                #print("list met networks", current_networks_contained_in_pending_summary)
                #print(len(current_networks_contained_in_pending_summary))

                if IPNetwork(network) in IPNetwork('1.0.0.0/8'): # geen summaries in T-Mobile segmenten 
                    current_list_of_summary_nets.append(IPNetwork(network))
                    return cidr_merge_advanced(list_of_networks[i+1:], summary_net, current_list_of_summary_nets, True, vrf, input_node, bgp_all_routes_dict, current_networks_contained_in_pending_summary)

                elif IPNetwork(network).prefixlen >= 31: # geen summaries op point-to-point en loopback segmenten
                    current_list_of_summary_nets.append(IPNetwork(network))
                    return cidr_merge_advanced(list_of_networks[i+1:], summary_net, current_list_of_summary_nets, True, vrf, input_node, bgp_all_routes_dict, current_networks_contained_in_pending_summary)

                elif (IPNetwork(network).ip & min_overlap_required_mask) != (summary & min_overlap_required_mask):
                    # dit netwerk heeft niet voldoende overlap. We gaan door de naar het volgende netwerk. Summary wordt opgeslagen
                    
                    if len(current_networks_contained_in_pending_summary) == 0: #overlap check is niet nodig, dit is pas het eerste netwerk in de reeks, overlap is onmogelijk
                        current_list_of_summary_nets.append(summary_net)
                        current_networks_contained_in_pending_summary = []
                        return cidr_merge_advanced(list_of_networks[i+1:], list_of_networks[i+1], current_list_of_summary_nets, True, vrf, input_node, bgp_all_routes_dict, current_networks_contained_in_pending_summary)

                    elif not check_summary_overlaps_with_other_route_jn4(summary_net, vrf, input_node, bgp_all_routes_dict, all_depv_vrf, other_vrf, False): #overlap check is ok, geen overlap is gevonden, summary wordt opgeslagen
                        current_list_of_summary_nets.append(summary_net)
                        current_networks_contained_in_pending_summary = []
                        return cidr_merge_advanced(list_of_networks[i+1:], list_of_networks[i+1], current_list_of_summary_nets, True, vrf, input_node, bgp_all_routes_dict, current_networks_contained_in_pending_summary)
                            
                    else:
                        # overlap check geeft fout, summary wordt niet opgeslagen, alle component routes van mislukte summary worden aan lijst toegevoegd
                        current_list_of_summary_nets.append(IPNetwork(network_first_in_list)) #Eerst network in lijst moet ook worden teruggegeven anders wordt deze overgeslagen
                        for network in current_networks_contained_in_pending_summary:
                            current_list_of_summary_nets.append(IPNetwork(network))
                        current_networks_contained_in_pending_summary = []
                        return cidr_merge_advanced(list_of_networks[i+1:], list_of_networks[i+1], current_list_of_summary_nets, True, vrf, input_node, bgp_all_routes_dict, current_networks_contained_in_pending_summary)

                else:
                    prefix_length_new = 0
                    for x in range(0,32):
                        if format(int(IPNetwork(network).ip), '#034b')[x+2] == format(int(summary), '#034b')[x+2]:
                            prefix_length_new += 1
                        else:
                            break
                    prefix_length_old = summary_net.prefixlen 
                    prefix_length = min(prefix_length_new, IPNetwork(network).prefixlen)

                    subnet_mask = convert_prefix_length_to_mask(prefix_length)
                    network_stripped = IPNetwork(network).ip & subnet_mask
                    summary_new = network_stripped & summary #let op aangepast naar new
                    summary_net = IPNetwork(summary_new)
                    summary_net.prefixlen = prefix_length
                    #print('prefix_length_new', prefix_length, 'prefix_length_old', prefix_length_old, 'IP Network', IPNetwork(network), 'summary_new', summary_new, 'summary_old', summary)
                    if (prefix_length < 16) or check_summary_overlaps_with_other_route_jn4(summary_net, vrf, input_node, bgp_all_routes_dict, all_depv_vrf, other_vrf,False): # summaries met prefix kleiner dan 16 worden niet vertrouwd en tevens extra overlap check nog binnen de forloop zodat niet de gehele summary wordt opgegeven
                        if (prefix_length < 16):
                            print("summary prefix length kleiner dan 16")
                        #elif check_summary_overlaps_with_other_route(summary_net, vrf, input_node, bgp_all_routes_dict):
                        #    print("Stop, summary address block van vrf {} heeft overlap met andere locatie, terug naar kleinere prefix".format(vrf))
                        summary_net = IPNetwork(summary) # terug naar oorspronkelijke summary met grote prefix waarde
                        summary_net.prefixlen = prefix_length_old
                        current_list_of_summary_nets.append(IPNetwork(network))
                        return cidr_merge_advanced(list_of_networks[i+1:], summary_net, current_list_of_summary_nets, True, vrf, input_node, bgp_all_routes_dict, current_networks_contained_in_pending_summary)

                    else:
                        current_networks_contained_in_pending_summary.append(network) # network is door alle checks gekomen en wordt toegevoegd aan de pending list
                        summary = summary_new #alles ok, summary wordt geupdated met nieuwste summary
            
            if len(current_networks_contained_in_pending_summary) <= 1: #overlap check is niet nodig, dit is pas het eerste netwerk in de reeks, overlap is onmogelijk
                current_list_of_summary_nets.append(summary_net)

            elif not check_summary_overlaps_with_other_route_jn4(summary_net, vrf, input_node, bgp_all_routes_dict, all_depv_vrf, other_vrf, False): #overlap check is ok, geen overlap is gevonden, summary wordt opgeslagen
                current_list_of_summary_nets.append(summary_net)
            else: 
                # overlap check geeft fout, summary wordt niet opgeslagen, alle component routes van mislukte summary worden aan de summary lijst toegevoegd
                current_list_of_summary_nets.append(IPNetwork(network_first_in_list)) #Eerst network in lijst moet ook worden teruggegeven anders wordt deze overgeslagen
                for network in current_networks_contained_in_pending_summary:
                    current_list_of_summary_nets.append(IPNetwork(network))
            current_networks_contained_in_pending_summary = []
            current_list_of_summary_nets.sort()
            return current_list_of_summary_nets

def convert_prefix_length_to_mask(prefix_length):
        if prefix_length > 32:
                print("wrong prefix length")
                return 0
        mask_integer = 0
        for i in range(31,31-prefix_length,-1):
                mask_integer += 2 ** i
        return IPAddress(mask_integer)


def check_summary_overlaps_with_other_route(summary_net, vrf, input_node, bgp_all_routes_dict, print_output = False):
    for node,item in bgp_all_routes_dict.items():
        try:
            #print("start overlap check")
            for route in item[vrf]:
               if (IPNetwork(route) in summary_net) & (not (node[:10] in input_node)):
                    if print_output:
                        print("Summary {} in vrf {} van node {} heeft overlap met netwerk {} van node {}".format(summary_net, vrf, input_node, route, node))
                        print("Deze summary kan helaas niet worden gebruikt.")
                        print()
                    return True
                    break
        except KeyError:
            pass
    return False 

def check_summary_overlaps_with_other_route_jn4(summary_net, vrf, input_node, bgp_all_routes_dict, depv_vrf_list, non_depv_vrf_list, print_output = False):
    vrf_main_branch = find_vrf_mainbranch_jn4(vrf, input_node, depv_vrf_list, non_depv_vrf_list)
    if vrf_main_branch == "depv_vrf":
        for node,all_depv_vrf_in_node in bgp_all_routes_dict.items():
            if "jn4isr01" in node:
                pass #as isr nodes contain by definition all the routes of all vrfs there will always be an overlap here
            else:
             # for depv_vrf additional for loop which goes through all vrfs that exist in depv_vrf collection
                for vrf_dict in all_depv_vrf: 
                    try:
                        #print("start overlap check")
                        for route in all_depv_vrf_in_node[vrf_main_branch][vrf_dict]:
                            if (IPNetwork(route) in summary_net) & (not (node[:10] in input_node)):
                                if print_output:
                                    print("Summary {} in vrf {} van node {} heeft overlap met netwerk {} van node {}".format(summary_net, vrf, input_node, route, node))
                                    print("Deze summary kan helaas niet worden gebruikt.")
                                    print()
                                return True
                                break
                    except KeyError:
                        pass
        return False
    elif vrf_main_branch == "non_depv_vrf":
        if vrf == "default":
            vrf_update = get_vrf_name_jn4(input_node, depv_vrf_list, non_depv_vrf_list) 
        else: vrf_update = vrf
        for node,all_non_depv_vrf_in_node in bgp_all_routes_dict.items():
         # for non_depv_vrf only the vrf is checked which applies for this non_depv_vrf
            try:
                #print("start overlap check")
                for route in all_non_depv_vrf_in_node[vrf_main_branch][vrf_update]:
                    if (IPNetwork(route) in summary_net) & (not (node[:10] in input_node)):
                        if print_output:
                            print("Summary {} in vrf {} van node {} heeft overlap met netwerk {} van node {}".format(summary_net, vrf_update, input_node, route, node))
                            print("Deze summary kan helaas niet worden gebruikt.")
                            print()
                        return True
                        break
            except KeyError:
                pass
        return False

def check_summary_overlaps_with_an_existing_aggregate(aggregate, vrf, bgp_vrf_dict, print_output = False):
   try:
       for summary in bgp_vrf_dict[vrf]:
           if (IPNetwork(aggregate) in IPNetwork(summary)):
               if print_output:
                   print("Bestaande BGP aggregate {} in vrf {} heeft overlap met nieuwe aggregate {}".format(aggregate, vrf, summary))
                   print("Deze bestaande BGP aggregate zal worden verwijderd in de nieuwe configuratie.")
                   print()
               return True
               break
   except KeyError:
       pass
   return False

    
def find_vrf_mainbranch_jn4(vrf, hostname, depv_vrf_list, non_depv_vrf_list):
    if vrf == 'default':
        for vrf_name in depv_vrf_list:
            if vrf_name in hostname:
                return "depv_vrf"
        for vrf_name in non_depv_vrf_list:
            if vrf_name in hostname:
                return "non_depv_vrf" 
    elif vrf != 'default': 
        for vrf_name in depv_vrf_list:
            if vrf_name in vrf:
                return "depv_vrf" 
        for vrf_name in non_depv_vrf_list:
            if vrf_name in vrf:
                return "non_depv_vrf" 
    return "depv_vrf"

def get_vrf_name_jn4(hostname, depv_vrf_list, non_depv_vrf_list):
    for vrf_name in depv_vrf_list:
        if vrf_name in hostname:
            return vrf_name
    for vrf_name in non_depv_vrf_list:
        if vrf_name in hostname:
            return vrf_name
    print("Error, juiste vrf naam die bij global hoort in deze CPE niet gevonden")
    return "default"
    
