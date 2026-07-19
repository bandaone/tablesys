import subprocess
import concurrent.futures

def ping(ip):
    # Ping once, wait up to 1 second
    result = subprocess.run(['ping', '-c', '1', '-W', '1', ip], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return ip if result.returncode == 0 else None

if __name__ == "__main__":
    print("Starting fast ICMP ping sweep on 192.168.0.0/24...")
    ips = [f"192.168.0.{i}" for i in range(1, 255)]
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
        results = executor.map(ping, ips)
        
    active_ips = [ip for ip in results if ip is not None]
    
    print(f"Sweep complete. Found {len(active_ips)} responding hosts (excluding self if not pingable).")
    for ip in active_ips:
        print(f" - {ip}")
    
    print("\nExtracting MAC addresses from ARP table...")
    arp_output = subprocess.check_output(['ip', 'neigh', 'show']).decode('utf-8')
    print(arp_output)
