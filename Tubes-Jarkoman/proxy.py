import socket
import threading
import os
import hashlib
import datetime
import time

# ─── Konfigurasi ────────────────────────────────────────────────────
PROXY_HOST    = "192.168.18.9"
PROXY_PORT    = 8080

# Alamat Web Server — ubah
WEBSERVER_HOST = "192.168.18.7" # 127.0.0.1 (local)
WEBSERVER_PORT = 8000

CONNECT_TIMEOUT  = 5   # detik — timeout koneksi ke server
RECV_TIMEOUT     = 10  # detik — timeout baca data dari server

# Direktori cache (dibuat otomatis jika belum ada)
CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "proxy_cache")
os.makedirs(CACHE_DIR, exist_ok=True)

# Lock global untuk akses cache agar thread-safe
cache_lock = threading.Lock()


# ─── Helpers ────────────────────────────────────────────────────────

def log(client_ip, url, cache_status, elapsed_ms):
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[PROXY] {ts} | {client_ip} | {url} | {cache_status} | {elapsed_ms:.1f} ms")


def cache_key(path):
    """Buat nama file cache dari path URL (hash MD5 untuk keamanan)."""
    return hashlib.md5(path.encode()).hexdigest() + ".cache"


def read_cache(path):
    """Kembalikan isi cache"""
    key  = cache_key(path)
    file = os.path.join(CACHE_DIR, key)
    with cache_lock:
        if os.path.isfile(file):
            with open(file, "rb") as f:
                return f.read()
    return None


def write_cache(path, data):
    """Simpan response ke file cache."""
    key  = cache_key(path)
    file = os.path.join(CACHE_DIR, key)
    with cache_lock:
        with open(file, "wb") as f:
            f.write(data)


def build_error_response(status_code, status_text, message):
    """Buat respons HTTP error sederhana."""
    body = (
        f"<html><body>"
        f"<h1>{status_code} {status_text}</h1>"
        f"<p>{message}</p>"
        f"</body></html>"
    ).encode("utf-8")
    header = (
        f"HTTP/1.1 {status_code} {status_text}\r\n"
        f"Content-Type: text/html; charset=utf-8\r\n"
        f"Content-Length: {len(body)}\r\n"
        f"Connection: close\r\n\r\n"
    )
    return header.encode("utf-8") + body


def forward_to_server(raw_request):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(CONNECT_TIMEOUT)
    try:
        s.connect((WEBSERVER_HOST, WEBSERVER_PORT))
    except (ConnectionRefusedError, OSError, socket.timeout):
        raise TimeoutError("Cannot connect to web server")

    s.settimeout(RECV_TIMEOUT)
    s.sendall(raw_request)

    response = b""
    while True:
        try:
            chunk = s.recv(4096)
            if not chunk:
                break
            response += chunk
        except socket.timeout:
            break
    s.close()
    return response


def parse_request_path(raw_request):
    try:
        first_line = raw_request.split(b"\r\n")[0].decode("utf-8", errors="replace")
        parts = first_line.split()
        if len(parts) >= 2:
            path = parts[1].split("?")[0]   # hapus query string
            return path
    except Exception:
        pass
    return "/"


# ─── Handler per koneksi ────────────────────────────────────────────

def handle_client(conn, addr):
    client_ip = addr[0]
    request_path = "/"
    start = time.time()
    cache_status = "MISS"

    try:
        # ── Terima request dari client ──────────────────────────────
        raw_request = b""
        conn.settimeout(5)
        while b"\r\n\r\n" not in raw_request:
            chunk = conn.recv(4096)
            if not chunk:
                break
            raw_request += chunk

        if not raw_request:
            conn.close()
            return

        request_path = parse_request_path(raw_request)

        # ── Cek cache ───────────────────────────────────────────────
        cached = read_cache(request_path)
        if cached:
            cache_status = "HIT"
            conn.sendall(cached)
            elapsed = (time.time() - start) * 1000
            log(client_ip, request_path, cache_status, elapsed)
            return

        # ── Cache MISS: forward ke Web Server ───────────────────────
        try:
            response = forward_to_server(raw_request)
        except TimeoutError as e:
            err = build_error_response(504, "Gateway Timeout",
                                       f"Web server tidak dapat dijangkau: {e}")
            conn.sendall(err)
            elapsed = (time.time() - start) * 1000
            log(client_ip, request_path, "504", elapsed)
            return
        except Exception as e:
            err = build_error_response(502, "Bad Gateway",
                                       f"Respons tidak valid dari server: {e}")
            conn.sendall(err)
            elapsed = (time.time() - start) * 1000
            log(client_ip, request_path, "502", elapsed)
            return

        # ── Periksa apakah server mengembalikan error ───────────────
        try:
            status_line = response.split(b"\r\n")[0].decode("utf-8", errors="replace")
            status_code_str = status_line.split(" ")[1] if len(status_line.split(" ")) > 1 else "200"
            status_code = int(status_code_str)
        except Exception:
            status_code = 200

        if status_code >= 500:
            # Jangan cache error server
            conn.sendall(response)
            elapsed = (time.time() - start) * 1000
            log(client_ip, request_path, f"SERVER-{status_code}", elapsed)
            return

        # ── Simpan ke cache & kirim ke client ──────────────────────
        write_cache(request_path, response)
        conn.sendall(response)
        elapsed = (time.time() - start) * 1000
        log(client_ip, request_path, cache_status, elapsed)

    except Exception as e:
        try:
            err = build_error_response(502, "Bad Gateway", str(e))
            conn.sendall(err)
        except Exception:
            pass
        elapsed = (time.time() - start) * 1000
        log(client_ip, request_path, f"ERR({e})", elapsed)
    finally:
        conn.close()


# ─── Entry point ────────────────────────────────────────────────────

if __name__ == "__main__":
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((PROXY_HOST, PROXY_PORT))
    server.listen(100)

    print("=" * 55)
    print("  PROXY.PY - Jaringan Komputer Modul 8")
    print("=" * 55)
    print(f"  Listening on  : {PROXY_HOST}:{PROXY_PORT}")
    print(f"  Web Server    : {WEBSERVER_HOST}:{WEBSERVER_PORT}")
    print(f"  Cache dir     : {CACHE_DIR}")
    print("=" * 55)

    while True:
        conn, addr = server.accept()
        t = threading.Thread(target=handle_client, args=(conn, addr), daemon=True)
        t.start()
        print(f"[PROXY] New thread for {addr[0]}:{addr[1]} (active: {threading.active_count()-1})")
