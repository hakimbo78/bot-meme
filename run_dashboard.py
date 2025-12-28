"""
Dashboard Launcher with HTTPS Support
Run: python run_dashboard.py [--https] [--port 8501] [--host 0.0.0.0]

Examples:
    python run_dashboard.py                  # HTTP on port 8501
    python run_dashboard.py --https          # HTTPS on port 8501
    python run_dashboard.py --port 8080      # HTTP on port 8080
    python run_dashboard.py --https --port 443 --host 0.0.0.0
"""
import argparse
import subprocess
import sys
import os
from pathlib import Path


def check_dependencies():
    """Check if required dependencies are installed."""
    missing = []
    
    try:
        import streamlit
    except ImportError:
        missing.append("streamlit")
    
    try:
        import plotly
    except ImportError:
        missing.append("plotly")
    
    try:
        import pandas
    except ImportError:
        missing.append("pandas")
    
    if missing:
        print("❌ Missing dependencies:", ", ".join(missing))
        print("   Install with: pip install " + " ".join(missing))
        return False
    
    return True


def main():
    parser = argparse.ArgumentParser(
        description='Launch Operator Dashboard',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  HTTP mode:     python run_dashboard.py
  HTTPS mode:    python run_dashboard.py --https
  Custom port:   python run_dashboard.py --port 8080
  Production:    python run_dashboard.py --https --port 443 --host 0.0.0.0
        """
    )
    
    parser.add_argument('--https', action='store_true', 
                       help='Enable HTTPS (requires SSL certificates)')
    parser.add_argument('--port', type=int, default=8501, 
                       help='Port number (default: 8501)')
    parser.add_argument('--host', default='0.0.0.0', 
                       help='Host address (default: 0.0.0.0)')
    parser.add_argument('--debug', action='store_true',
                       help='Enable debug mode')
    parser.add_argument('--no-browser', action='store_true',
                       help='Do not open browser automatically')
    
    args = parser.parse_args()
    
    # Check dependencies
    if not check_dependencies():
        sys.exit(1)
    
    # Get project directory
    project_dir = Path(__file__).parent
    dashboard_file = project_dir / "dashboard.py"
    
    if not dashboard_file.exists():
        print(f"❌ Dashboard file not found: {dashboard_file}")
        sys.exit(1)
    
    # Build streamlit command
    cmd = [
        sys.executable, '-m', 'streamlit', 'run',
        str(dashboard_file),
        '--server.port', str(args.port),
        '--server.address', args.host,
        '--server.headless', 'true' if args.no_browser else 'false',
    ]
    
    # Add HTTPS configuration
    if args.https:
        cert_dir = project_dir / 'certs'
        cert_file = cert_dir / 'cert.pem'
        key_file = cert_dir / 'key.pem'
        
        if cert_file.exists() and key_file.exists():
            cmd.extend([
                '--server.sslCertFile', str(cert_file),
                '--server.sslKeyFile', str(key_file)
            ])
            protocol = "https"
            print("🔒 HTTPS mode enabled")
        else:
            print("❌ SSL certificates not found!")
            print(f"   Expected: {cert_file}")
            print(f"   Expected: {key_file}")
            print("")
            print("   Generate certificates first:")
            if os.name == 'nt':
                print("   .\\scripts\\generate_ssl.ps1")
            else:
                print("   bash scripts/generate_ssl.sh")
            print("")
            print("   Or run without --https for HTTP mode")
            sys.exit(1)
    else:
        protocol = "http"
    
    # Print startup info
    print("")
    print("=" * 50)
    print("🚀 Starting Operator Dashboard")
    print("=" * 50)
    print(f"   URL: {protocol}://{args.host}:{args.port}")
    print(f"   Mode: {'HTTPS (Secure)' if args.https else 'HTTP'}")
    print(f"   Debug: {'Enabled' if args.debug else 'Disabled'}")
    print("=" * 50)
    print("")
    print("Press Ctrl+C to stop the server")
    print("")
    
    # Set environment for debug mode
    env = os.environ.copy()
    if args.debug:
        env['STREAMLIT_LOG_LEVEL'] = 'debug'
    
    # Run streamlit
    try:
        subprocess.run(cmd, env=env, cwd=str(project_dir))
    except KeyboardInterrupt:
        print("\n\n👋 Dashboard stopped")


if __name__ == '__main__':
    main()
