import re

def fetch_ips(print_output):
    bgp_prefixes = []
    output_list = print_output.splitlines()
    for line in output_list:
        if (re.search(r"\s+\*>\s+\d+.\d+.\d+.\d+", line)):
            bgp_prefixes.append((re.search(r"\s+\*>\s+(\d+.\d+.\d+.\d+)/\d+", line).group(1),re.search(r"\s+\*>\s+(\d+.\d+.\d+.\d+)/(\d+)", line).group(2)))
                                #re.search(r"\s+\*>\s+(\d+.\d+.\d+.\d+)(/\d+)", line).group(2))
    return bgp_prefixes


def return_ips_tuple(bgp_prefixes):
    list_with_tuples = []
    for ip in bgp_prefixes:
        a = tuple(ip[0].split('.'))
        list_with_tuples.append((a,ip[1]))
    return(list_with_tuples)


def return_ip_address_list(bgp_prefixes):
    list_with_ipaddresses = []
    for ip in bgp_prefixes:
        ip_a = ip[0]+'/'+ip[1]
        list_with_ipaddresses.append(ip_a)
    return list_with_ipaddresses


def handle_bgp_output(print_output):
    ips_raw = fetch_ips(print_output)
    ips_tuple = return_ips_tuple(ips_raw)
    ip_list = return_ip_address_list(ips_raw)
    for ip in ips_tuple:
        print('{:>20}'.format('['+ip[0][0])+'.'+'{:>3}'.format(ip[0][1])+'.'+'{:>3}'.format(ip[0][2])+'.'+'{:>3}'.format(ip[0][3])+' / '+'{:>2}'.format(ip[1])+']')
    return ip_list
