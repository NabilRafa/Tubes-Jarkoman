import socket
import time
import sys
import threading

# ─── Konfigurasi ────────────────────────────────────────────────────
PROXY_HOST   = "10.211.61.1"   # ubah ke IP proxy
PROXY_PORT   = 8080

SERVER_UDP_HOST = "10.211.61.5"  # ubah ke IP webserver
SERVER_UDP_PORT = 9000

UDP_PACKET_COUNT = 10
UDP_TIMEOUT      = 1.0          # detik per paket

# Path-path yang dipakai untuk demo multi-client (HIT vs MISS)
MULTI_CLIENT_PATHS = [
    "/index.html",
    "/index.html",   # sama -> sebagian HIT
    "/about.html",
    "/about.html",   # sama -> sebagian HIT
    "/contact.html",
]


# ────────────────────────────────────────────────────────────────────
# MODE HTTP via Proxy (TCP)
# ────────────────────────────────────────────────────────────────────

def http_get(path="/", label="CLIENT"):
    """
    Kirim HTTP GET ke Proxy, terima respons, tampilkan header + body.
    """
    request = (
        f"GET {path} HTTP/1.1\r\n"
        f"Host: {PROXY_HOST}:{PROXY_PORT}\r\n"
        f"Connection: close\r\n"
        f"\r\n"
    )

    print(f"\n[{label}] Connecting to proxy {PROXY_HOST}:{PROXY_PORT} for {path} ...")
    start = time.time()

    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(10)
        s.connect((PROXY_HOST, PROXY_PORT))
        s.sendall(request.encode("utf-8"))

        response = b""
        while True:
            chunk = s.recv(4096)
            if not chunk:
                break
            response += chunk
        s.close()

        elapsed = (time.time() - start) * 1000
        print(f"[{label}] Response received in {elapsed:.1f} ms  ({len(response)} bytes)  path={path}")

        if b"\r\n\r\n" in response:
            header_bytes, body = response.split(b"\r\n\r\n", 1)
            print(f"─── [{label}] HTTP RESPONSE HEADER ({path}) ───")
            print(header_bytes.decode("utf-8", errors="replace"))
            print(f"─── [{label}] BODY (first 1000 chars) ───")
            body_text = body.decode("utf-8", errors="replace")
            print(body_text[:1000])
            if len(body_text) > 1000:
                print(f"... (truncated, total {len(body_text)} chars)")
        else:
            print(response.decode("utf-8", errors="replace"))

    except ConnectionRefusedError:
        print(f"[{label}] ERROR: Proxy tidak dapat dijangkau di {PROXY_HOST}:{PROXY_PORT}")
    except socket.timeout:
        print(f"[{label}] ERROR: Request timeout")
    except Exception as e:
        print(f"[{label}] ERROR: {e}")


# ────────────────────────────────────────────────────────────────────
# MODE QoS Ping (UDP)
# ────────────────────────────────────────────────────────────────────

def udp_qos(count=UDP_PACKET_COUNT, label="CLIENT-UDP"):
    print(f"\n[{label}] Pinging {SERVER_UDP_HOST}:{SERVER_UDP_PORT} — {count} packets\n")

    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(UDP_TIMEOUT)

    rtts = []
    lost = 0

    for seq in range(1, count + 1):
        ts = time.time()
        payload = f"Ping {seq} {ts:.6f}".encode("utf-8")

        send_time = time.time()
        s.sendto(payload, (SERVER_UDP_HOST, SERVER_UDP_PORT))

        try:
            data, _ = s.recvfrom(1024)
            rtt = (time.time() - send_time) * 1000   # ms
            rtts.append(rtt)
            print(f"  [{label}] seq={seq:>2}  RTT={rtt:.3f} ms  payload={data.decode('utf-8', errors='replace')}")
        except socket.timeout:
            lost += 1
            print(f"  [{label}] seq={seq:>2}  Request timed out")

        time.sleep(0.1)   # jeda kecil antar paket

    s.close()

    print(f"\n─── [{label}] QoS STATISTICS ───────────────────────────────────")
    print(f"  Packets sent     : {count}")
    print(f"  Packets received : {len(rtts)}")
    print(f"  Packet loss      : {lost}/{count}  ({lost/count*100:.1f}%)")

    if rtts:
        min_rtt  = min(rtts)
        max_rtt  = max(rtts)
        avg_rtt  = sum(rtts) / len(rtts)

        jitter = 0.0
        if len(rtts) > 1:
            diffs  = [abs(rtts[i] - rtts[i-1]) for i in range(1, len(rtts))]
            jitter = sum(diffs) / len(diffs)

        print(f"  Min RTT          : {min_rtt:.3f} ms")
        print(f"  Avg RTT          : {avg_rtt:.3f} ms")
        print(f"  Max RTT          : {max_rtt:.3f} ms")
        print(f"  Jitter           : {jitter:.3f} ms")
    else:
        print("  Semua paket hilang — tidak ada data RTT.")
    print("──────────────────────────────────────────────────────")


# ────────────────────────────────────────────────────────────────────
# SINGLE MODE — menu interaktif (perilaku original)
# ────────────────────────────────────────────────────────────────────

def print_banner(mode_label):
    print("=" * 55)
    print(f"  CLIENT.PY - Jaringan Komputer Modul 8 [{mode_label}]")
    print("=" * 55)
    print(f"  Proxy    : {PROXY_HOST}:{PROXY_PORT}")
    print(f"  UDP echo : {SERVER_UDP_HOST}:{SERVER_UDP_PORT}")
    print("=" * 55)


def run_single():
    print_banner("SINGLE")
    while True:
        print("\n  [1] HTTP GET via Proxy (TCP)")
        print("  [2] QoS Ping via UDP")
        print("  [q] Keluar")
        choice = input("\n  Pilih mode: ").strip().lower()

        if choice == "1":
            path = input("  Masukkan path (contoh: /index.html) [default=/]: ").strip()
            if not path:
                path = "/"
            http_get(path)

        elif choice == "2":
            try:
                n = int(input(f"  Jumlah paket [default={UDP_PACKET_COUNT}]: ").strip() or UDP_PACKET_COUNT)
            except ValueError:
                n = UDP_PACKET_COUNT
            udp_qos(n)

        elif choice == "q":
            print("\n[CLIENT] Goodbye!\n")
            break
        else:
            print("  Pilihan tidak valid, coba lagi.")


# ────────────────────────────────────────────────────────────────────
# MULTI MODE — spawn beberapa client thread sekaligus
# (memenuhi ketentuan: pengujian minimal 5 client konkuren,
#  request ke path berbeda untuk uji MISS dan path sama untuk uji HIT)
# ────────────────────────────────────────────────────────────────────

def run_multi(num_clients=5, udp_count=UDP_PACKET_COUNT):
    print_banner(f"MULTI x{num_clients}")
    print(f"\n[MULTI] Menjalankan {num_clients} client HTTP secara konkuren...")
    print(f"[MULTI] Daftar path: {MULTI_CLIENT_PATHS[:num_clients]}\n")

    threads = []

    # ── Spawn N client HTTP secara bersamaan ──────────────────────
    for i in range(num_clients):
        path = MULTI_CLIENT_PATHS[i % len(MULTI_CLIENT_PATHS)]
        label = f"CLIENT-{i+1}"
        t = threading.Thread(target=http_get, args=(path, label), daemon=True)
        threads.append(t)

    start = time.time()
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    elapsed = (time.time() - start) * 1000
    print(f"\n[MULTI] Semua {num_clients} client HTTP selesai dalam {elapsed:.1f} ms total")

    # ── Jalankan UDP QoS test setelah HTTP selesai ────────────────
    print("\n[MULTI] Menjalankan QoS UDP test...")
    udp_qos(udp_count, label="CLIENT-UDP")


# ────────────────────────────────────────────────────────────────────
# Entry point — pilih mode via argv
#   py client.py single
#   py client.py multi [jumlah_client]
# ────────────────────────────────────────────────────────────────────

def main():
    args = sys.argv[1:]

    if not args:
        print("Usage:")
        print("  py client.py single")
        print("  py client.py multi [jumlah_client]")
        print("\nTidak ada argumen, menjalankan mode SINGLE secara default...\n")
        run_single()
        return

    mode = args[0].lower()

    if mode == "single":
        run_single()
    elif mode == "multi":
        n = 5
        if len(args) > 1:
            try:
                n = int(args[1])
            except ValueError:
                print(f"[WARN] '{args[1]}' bukan angka valid, pakai default n=5")
        run_multi(num_clients=n)
    else:
        print(f"[ERROR] Mode '{mode}' tidak dikenal. Gunakan 'single' atau 'multi'.")
        sys.exit(1)


if __name__ == "__main__":
    main()
