import nodes
from netmiko import Netmiko
from getpass import getpass
from pprint import pprint

def goto_sleep(seconds):
    import time
    time.sleep(seconds)
 

VRF = input("Van welk VRF moeten de lokale routes worden bepaald?")

# Connecthandler

password = getpass()

all_core_nodes = nodes.e1 + nodes.c1

for i,node in enumerate(all_core_nodes):
    
    node_dict = {
    'host': node,
    'username': "933513-adm",
    'password': password,
    'device_type': 'cisco_ios'}

    #pprint(node_dict)
    print("Verbinding maken met:", node)
    
    net_conn = Netmiko(**node_dict) 
    output = net_conn.send_command("show bgp vpnv4 unicast vrf "+VRF, use_textfsm=True)
    print("Print output van Router", node_dict['host'])
    print()
    print("-"*80)
    pprint(output)
    print("-"*80)
    net_conn.disconnect()
    goto_sleep(5)    

#net_conn = Netmiko(**ch27_00_d1)
#net_conn.send_command_timing("disable")
#print(net_conn.find_prompt())

