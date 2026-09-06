from http.server import HTTPServer, BaseHTTPRequestHandler
import os

PORTAL_DIR = os.path.join(os.path.dirname(__file__), 'portal')
os.makedirs(PORTAL_DIR, exist_ok=True)


class PortalHandler(BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        pass

    def serve_file(self, filepath, content_type):
        try:
            with open(filepath, 'rb') as f:
                content = f.read()
            self.send_response(200)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', len(content))
            self.end_headers()
            self.wfile.write(content)
        except FileNotFoundError:
            self.send_error(404)

    def do_GET(self):
        path = self.path.split('?')[0]

        if path == '/' or path == '/index.html':
            self.serve_file(os.path.join(PORTAL_DIR, 'index.html'), 'text/html')
        elif path == '/portal.css':
            self.serve_file(os.path.join(PORTAL_DIR, 'portal.css'), 'text/css')
        elif path == '/portal.js':
            self.serve_file(os.path.join(PORTAL_DIR, 'portal.js'), 'application/javascript')
        elif path.startswith('/images/'):
            img_path = os.path.join(os.path.dirname(__file__), 'static', path.lstrip('/'))
            if path.endswith('.png'):
                self.serve_file(img_path, 'image/png')
            elif path.endswith('.jpg') or path.endswith('.jpeg'):
                self.serve_file(img_path, 'image/jpeg')
            elif path.endswith('.svg'):
                self.serve_file(img_path, 'image/svg+xml')    
            else:
                self.send_error(404)
        

if __name__ == "__main__":
    import socket
    PORT     = 8001
    hostname = socket.gethostname()
    try:
        local_ip = socket.gethostbyname(hostname)
    except:
        local_ip = "localhost"

    server = HTTPServer(('0.0.0.0', PORT), PortalHandler)
    print(f"\n{'='*50}")
    print(f"  Upay Portal running!")
    print(f"  Local:   http://localhost:{PORT}")
    print(f"  Network: http://{local_ip}:{PORT}")
    print(f"  Press Ctrl+C to stop")
    print(f"{'='*50}\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nPortal stopped.")