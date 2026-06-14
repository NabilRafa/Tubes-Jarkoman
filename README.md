# Tubes-Jarkoman

Tubes Jarkom





NEW:

HTTP GET via Proxy (cache MISS pertama kali)

python client.py --mode tcp --path /index.html



HTTP GET via Proxy (cache HIT pertama kali)

python client.py --mode tcp --path /index.html



sama, MISS pertama kali



python client.py --mode tcp --path /osi.html

python client.py --mode tcp --path /tcpip.html

python client.py --mode tcp --path /qos.html

python client.py --mode tcp --path /implementation.html



HIT kedua kali



python client.py --mode tcp --path /osi.html

python client.py --mode tcp --path /tcpip.html

python client.py --mode tcp --path /qos.html

python client.py --mode tcp --path /implementation.html



QoS UDP Ping (default 10 paket)

python client.py --mode udp --jumlah 10



Multi-Client Concurrent (5 client + UDP QoS)

python client.py --mode multi --jumlah 5



Mode Interaktif

python client.py --mode single







OLD:

py client.py single        # menu interaktif, persis behavior lama

py client.py multi          # 5 client HTTP konkuren + 1 UDP QoS test

py client.py multi 8        # custom jumlah client

