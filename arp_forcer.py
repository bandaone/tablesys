import socket
import concurrent.futures
import subprocess

def trigger_arp(ip):
    # Attempting to connect to any port will force the OS to send an ARP request
    # even if we are not root!
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.5)
        s.connect((ip, 80))
        s.close()
    except Exception:
        pass
    return ip

if __name__ == "__main__":
    print("Starting Layer 4 scan to force Layer 2 ARP discovery on 192.168.0.0/24...")
    ips = [f"192.168.0.{i}" for i in range(1, 255)]
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=100) as executor:
        executor.map(trigger_arp, ips)
        
    print("Scan complete. Now dumping the ARP table...")
