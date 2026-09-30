"""Print router state for troubleshooting the local lab."""
from check_lab import execute

for router in ("r1", "r2"):
    print(router, flush=True)
    for command in ("show running-config", "show ip ospf interface", "show ip ospf neighbor json", "show ip route json"):
        print(command, execute(router, "vtysh", "-c", command), flush=True)
    print(execute(router, "ip", "-br", "addr"), flush=True)
