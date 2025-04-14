def get_ips():
    import psutil
    import socket
    IPs = {}

    try:
        NIC_devices = psutil.net_if_addrs()
        for name, NIC in NIC_devices.items():
            if name == 'lo':
                continue
            try:
                for af in NIC:
                    if af.family == socket.AF_INET: # 2:'IPV4'
                        IPs[name] = af.address
            except:
                continue
    except Exception as e:
        print(f"Failed to get ips: {str(e)}")

    result = {}
    for key in IPs:
        if IPs[key] != '' and IPs[key] != None:
            result[key] = IPs[key]

    return result

