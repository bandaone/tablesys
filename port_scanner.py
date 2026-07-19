import socket
import concurrent.futures

# A list of common ports and their typical uses
PORTS_TO_CHECK = {
    21: "FTP (File Transfer)",
    22: "SSH (Secure Shell - Linux/Mac)",
    23: "Telnet (Insecure Login)",
    53: "DNS (Domain Name System)",
    80: "HTTP (Web Server / Admin Panel)",
    111: "RPCBind (Linux/Unix RPC)",
    139: "NetBIOS (Windows/Samba File Sharing)",
    443: "HTTPS (Secure Web Server)",
    445: "SMB (Windows File Sharing)",
    548: "AFP (Apple File Sharing)",
    631: "IPP (Printers)",
    3389: "RDP (Windows Remote Desktop)",
    5000: "UPnP (Media streaming / IoT)",
    5900: "VNC (Remote Desktop Screen Sharing)",
    8000: "HTTP Alternative",
    8080: "HTTP Alternative",
    62078: "Apple iPhone Sync"
}

def scan_port(ip, port):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.5) # Short timeout for speed
        result = s.connect_ex((ip, port))
        s.close()
        if result == 0:
            return port
    except Exception:
        pass
    return None

def scan_device(ip):
    print(f"\n--- Scanning IP: {ip} ---")
    open_ports = []
    
    # We use ThreadPoolExecutor to scan ports in parallel for speed
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        futures = {executor.submit(scan_port, ip, port): port for port in PORTS_TO_CHECK.keys()}
        for future in concurrent.futures.as_completed(futures):
            port_result = future.result()
            if port_result:
                open_ports.append(port_result)
                
    if not open_ports:
        print("  No common ports open. Device might have a strict firewall or is a locked-down phone/IoT device.")
    else:
        open_ports.sort()
        for p in open_ports:
            service = PORTS_TO_CHECK.get(p, "Unknown")
            print(f"  [OPEN] Port {p} -> {service}")

if __name__ == "__main__":
    devices = ["192.168.0.1", "192.168.0.54"]
    for ip in devices:
        scan_device(ip)
