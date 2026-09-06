import threading
import os
import sys
from http.server import HTTPServer

# Import handlers from existing files
sys.path.insert(0, os.path.dirname(__file__))

def start_portal_api():
    from portal_api import PortalAPIHandler
    from socketserver import ThreadingMixIn
    class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
        daemon_threads = True
    server = ThreadedHTTPServer(('0.0.0.0', 8000), PortalAPIHandler)
    print("Portal API running on port 8000")
    server.serve_forever()

def start_portal():
    from portal import PortalHandler
    server = HTTPServer(('0.0.0.0', 8001), PortalHandler)
    print("Demo Portal running on port 8001")
    server.serve_forever()

def start_dashboard():
    from server import Handler
    server = HTTPServer(('0.0.0.0', 5000), Handler)
    print("Automation Dashboard running on port 5000")
    server.serve_forever()

if __name__ == "__main__":
    # Start portal API in thread
    t1 = threading.Thread(target=start_portal_api, daemon=True)
    t1.start()

    # Start demo portal in thread
    t2 = threading.Thread(target=start_portal, daemon=True)
    t2.start()

    # Start dashboard (main thread)
    print("Starting all servers...")
    start_dashboard()