import socket
import time
import datetime

# ─── Konfigurasi ────────────────────────────────────────────────────
PROXY_HOST   = "10.211.61.1"   # ubah ke IP proxy
PROXY_PORT   = 8080

SERVER_UDP_HOST = "10.211.61.5"  # ubah ke IP webserver
SERVER_UDP_PORT = 9000

UDP_PACKET_COUNT = 10
UDP_TIMEOUT      = 1.0          # detik per paket


# ────────────────────────────────────────────────────────────────────
# MODE 1 — HTTP via Proxy (TCP)
# ────────────────────────────────────────────────────────────────────

def http_get(path="/"):
    """
    Kirim HTTP GET ke Proxy, terima respons, tampilkan header + body.
    """
    request = (
        f"GET {path} HTTP/1.1\r\n"
        f"Host: {PROXY_HOST}:{PROXY_PORT}\r\n"
        f"Connection: close\r\n"
        f"\r\n"
    )

    print(f"\n[CLIENT] Connecting to proxy {PROXY_HOST}:{PROXY_PORT} ...")
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
        print(f"[CLIENT] Response received in {elapsed:.1f} ms  ({len(response)} bytes)\n")

        # Pisahkan header dan body
        if b"\r\n\r\n" in response:
            header_bytes, body = response.split(b"\r\n\r\n", 1)
            print("─── HTTP RESPONSE HEADER ───")
            print(header_bytes.decode("utf-8", errors="replace"))
            print("─── BODY (first 1000 chars) ───")
            body_text = body.decode("utf-8", errors="replace")
            print(body_text[:1000])
            if len(body_text) > 1000:
                print(f"... (truncated, total {len(body_text)} chars)")
        else:
            print(response.decode("utf-8", errors="replace"))

    except ConnectionRefusedError:
        print(f"[CLIENT] ERROR: Proxy tidak dapat dijangkau di {PROXY_HOST}:{PROXY_PORT}")
    except socket.timeout:
        print("[CLIENT] ERROR: Request timeout")
    except Exception as e:
        print(f"[CLIENT] ERROR: {e}")


# ────────────────────────────────────────────────────────────────────
# MODE 2 — UDP QoS Ping
# ────────────────────────────────────────────────────────────────────

def udp_qos(count=UDP_PACKET_COUNT):
    print(f"\n[CLIENT-UDP] Pinging {SERVER_UDP_HOST}:{SERVER_UDP_PORT} — {count} packets\n")

    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(UDP_TIMEOUT)

    rtts = []
    lost = 0
    prev_rtt = None

    for seq in range(1, count + 1):
        ts = time.time()
        payload = f"Ping {seq} {ts:.6f}".encode("utf-8")

        send_time = time.time()
        s.sendto(payload, (SERVER_UDP_HOST, SERVER_UDP_PORT))

        try:
            data, _ = s.recvfrom(1024)
            rtt = (time.time() - send_time) * 1000   # ms
            rtts.append(rtt)
            print(f"  seq={seq:>2}  RTT={rtt:.3f} ms  payload={data.decode('utf-8', errors='replace')}")
        except socket.timeout:
            lost += 1
            print(f"  seq={seq:>2}  Request timed out")

        time.sleep(0.1)   # jeda kecil antar paket

    s.close()

    # ── Statistik ──────────────────────────────────────────────────
    print("\n─── QoS STATISTICS ───────────────────────────────────")
    print(f"  Packets sent     : {count}")
    print(f"  Packets received : {len(rtts)}")
    print(f"  Packet loss      : {lost}/{count}  ({lost/count*100:.1f}%)")

    if rtts:
        min_rtt  = min(rtts)
        max_rtt  = max(rtts)
        avg_rtt  = sum(rtts) / len(rtts)

        # Jitter = rata-rata |RTT[i] - RTT[i-1]|
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
# Menu Utama
# ────────────────────────────────────────────────────────────────────

def print_banner():
    print("=" * 55)
    print("  CLIENT.PY - Jaringan Komputer Modul 8")
    print("=" * 55)
    print(f"  Proxy    : {PROXY_HOST}:{PROXY_PORT}")
    print(f"  UDP echo : {SERVER_UDP_HOST}:{SERVER_UDP_PORT}")
    print("=" * 55)


def menu():
    print_banner()
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


if __name__ == "__main__":
    menu()
