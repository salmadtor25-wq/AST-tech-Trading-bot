"""
AST Capital Trading Platform — Server Launcher

Usage:
  python run.py              # start on http://0.0.0.0:8000
  python run.py --port 8080  # custom port
  python run.py --reload     # dev mode with auto-reload

Open your browser at:  http://localhost:8000
For LAN / VPS access:  http://<your-ip>:8000
"""
import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import uvicorn

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AST Capital Trading Platform")
    parser.add_argument("--host",   default="0.0.0.0",  help="Bind host (default: 0.0.0.0)")
    parser.add_argument("--port",   default=8000, type=int, help="Port (default: 8000)")
    parser.add_argument("--reload", action="store_true",   help="Enable auto-reload (dev mode)")
    args = parser.parse_args()

    print("""
╔══════════════════════════════════════════════════════════╗
║          ◈  AST CAPITAL  ·  Trading Platform             ║
╠══════════════════════════════════════════════════════════╣
║                                                          ║
║   Open your browser at:                                  ║
║   → http://localhost:{port:<5}                            ║
║                                                          ║
║   For network access:                                    ║
║   → http://<your-ip>:{port:<5}                            ║
║                                                          ║
║   Press  Ctrl+C  to stop.                               ║
╚══════════════════════════════════════════════════════════╝
""".format(port=args.port))

    uvicorn.run(
        "app.server:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info",
    )
