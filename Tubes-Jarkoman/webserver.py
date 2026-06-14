import socket
import threading
import os
import mimetypes
import datetime

# ─── Konfigurasi ────────────────────────────────────────────────────
TCP_HOST = "0.0.0.0"
TCP_PORT = 8000
UDP_HOST = "0.0.0.0"
UDP_PORT = 9000
BASE_DIR  = os.path.dirname(os.path.abspath(__file__))   # direktori webserver.py


# ─── Halaman error bawaan (fallback jika file status/*.html tidak ada) ───
ERROR_PAGES = {
    404: b"<html><body><h1>404 Not Found</h1><p>The requested resource was not found.</p></body></html>",
    500: b"<html><body><h1>500 Internal Server Error</h1><p>An unexpected error occurred.</p></body></html>",
}


def log(client_ip, path, status_code):
    """Catat log ke konsol dengan format standar."""
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[WEBSERVER] {ts} | {client_ip} | {path} | {status_code}")


def load_error_page(code):
    """Muat halaman error dari file status/<code>.html jika tersedia."""
    path = os.path.join(BASE_DIR, "status", f"{code}.html")
    if os.path.isfile(path):
        with open(path, "rb") as f:
            return f.read()
    return ERROR_PAGES.get(code, b"<html><body><h1>Error</h1></body></html>")


def build_response(status_code, status_text, content_type, body):
    """Buat HTTP/1.1 response lengkap."""
    header = (
        f"HTTP/1.1 {status_code} {status_text}\r\n"
        f"Content-Type: {content_type}; charset=utf-8\r\n"
        f"Content-Length: {len(body)}\r\n"
        f"Connection: close\r\n"
        f"\r\n"
    )
    return header.encode("utf-8") + body


def serve_file(path):
    """
    Kembalikan (status_code, status_text, content_type, body).
    Path sudah dibersihkan dari karakter berbahaya.
    """
    # Normalisasi: hapus leading slash, cegah path traversal
    safe_path = path.lstrip("/")
    if not safe_path:
        safe_path = "index.html"

    full_path = os.path.normpath(os.path.join(BASE_DIR, safe_path))

    # Cegah akses keluar dari BASE_DIR
    if not full_path.startswith(BASE_DIR):
        return (403, "Forbidden", "text/html", load_error_page(404))

    # Jika direktori, coba index.html di dalamnya
    if os.path.isdir(full_path):
        full_path = os.path.join(full_path, "index.html")

    if not os.path.isfile(full_path):
        return (404, "Not Found", "text/html", load_error_page(404))

    mime_type, _ = mimetypes.guess_type(full_path)
    if mime_type is None:
        mime_type = "application/octet-stream"

    with open(full_path, "rb") as f:
        body = f.read()

    return (200, "OK", mime_type, body)


def handle_tcp_client(conn, addr):
    """Tangani satu koneksi HTTP dari client (atau proxy)."""
    client_ip = addr[0]
    request_path = "/"
    try:
        raw = b""
        while b"\r\n\r\n" not in raw:
            chunk = conn.recv(4096)
            if not chunk:
                break
            raw += chunk

        if not raw:
            return

        # ── Parse request line ──────────────────────────────────────
        first_line = raw.split(b"\r\n")[0].decode("utf-8", errors="replace")
        parts = first_line.split()
        if len(parts) < 2:
            # Malformed request
            body  = load_error_page(500)
            resp  = build_response(500, "Internal Server Error", "text/html", body)
            conn.sendall(resp)
            log(client_ip, "MALFORMED", 500)
            return

        method = parts[0].upper()
        request_path = parts[1]

        if method != "GET":
            body = b"<html><body><h1>405 Method Not Allowed</h1></body></html>"
            resp = build_response(405, "Method Not Allowed", "text/html", body)
            conn.sendall(resp)
            log(client_ip, request_path, 405)
            return

        # Hapus query string
        request_path_clean = request_path.split("?")[0]

        status_code, status_text, content_type, body = serve_file(request_path_clean)
        resp = build_response(status_code, status_text, content_type, body)
        conn.sendall(resp)
        log(client_ip, request_path, status_code)

    except Exception as e:
        try:
            body = load_error_page(500)
            resp = build_response(500, "Internal Server Error", "text/html", body)
            conn.sendall(resp)
        except Exception:
            pass
        log(client_ip, request_path, f"500 (exc: {e})")
    finally:
        conn.close()


def start_tcp_server():
    """Jalankan HTTP server berbasis TCP di port TCP_PORT."""
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((TCP_HOST, TCP_PORT))
    server.listen(100)
    print(f"[WEBSERVER] TCP HTTP server listening on {TCP_HOST}:{TCP_PORT}")

    while True:
        conn, addr = server.accept()
        t = threading.Thread(target=handle_tcp_client, args=(conn, addr), daemon=True)
        t.start()
        print(f"[WEBSERVER] New thread spawned for {addr[0]}:{addr[1]} (active: {threading.active_count()-1})")


def start_udp_server():
    """Jalankan UDP echo server di port UDP_PORT untuk pengujian QoS."""
    server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server.bind((UDP_HOST, UDP_PORT))
    print(f"[WEBSERVER] UDP echo server listening on {UDP_HOST}:{UDP_PORT}")

    while True:
        data, addr = server.recvfrom(1024)
        # Echo balik payload tanpa perubahan
        server.sendto(data, addr)
        ts = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
        print(f"[WEBSERVER-UDP] {ts} | Echo {len(data)} bytes → {addr[0]}:{addr[1]}")


# ─── Entry point ────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 55)
    print("  WEBSERVER.PY - Jaringan Komputer Modul 8")
    print("=" * 55)
    print(f"  Base directory : {BASE_DIR}")
    print(f"  TCP HTTP port  : {TCP_PORT}")
    print(f"  UDP echo port  : {UDP_PORT}")
    print("=" * 55)

    # Jalankan UDP server di thread terpisah
    udp_thread = threading.Thread(target=start_udp_server, daemon=True)
    udp_thread.start()

    # Jalankan TCP server di main thread
    start_tcp_server()
