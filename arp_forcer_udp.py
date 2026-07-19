import socket
import time
import subprocess

def force_arp():
    print("Sending UDP packets to all IPs to force ARP...")
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    for i in range(1, 255):
        ip = f"192.168.0.{i}"
        # Send a tiny UDP payload to a random high port
        try:
            s.sendto(b'ping', (ip, 5353))
        except Exception:
            pass
    s.close()
    
    # Wait a bit for ARP replies to arrive
    time.sleep(2)
    
    print("Current ARP Table (Active devices):")
    output = subprocess.check_output(['ip', 'neigh', 'show']).decode('utf-8')
    for line in output.splitlines():
        if "REACHABLE" in line or "STALE" in line or "DELAY" in line:
            print(line)

if __name__ == "__main__":
    force_arp()
