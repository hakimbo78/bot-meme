#!/bin/bash
# Generate self-signed SSL certificate for dashboard
# Usage: bash scripts/generate_ssl.sh

set -e

CERT_DIR="./certs"
DAYS_VALID=365

echo "🔐 Generating SSL certificates for Dashboard"
echo "============================================"

# Create certs directory
mkdir -p $CERT_DIR

# Generate private key
echo "📝 Generating private key..."
openssl genrsa -out $CERT_DIR/key.pem 2048

# Generate self-signed certificate
echo "📜 Generating certificate..."
openssl req -new -x509 \
    -key $CERT_DIR/key.pem \
    -out $CERT_DIR/cert.pem \
    -days $DAYS_VALID \
    -subj "/C=ID/ST=Jakarta/L=Jakarta/O=MemeBot/CN=dashboard.local"

# Set permissions
chmod 600 $CERT_DIR/key.pem
chmod 644 $CERT_DIR/cert.pem

echo ""
echo "✅ SSL certificates generated successfully!"
echo "   📁 Directory: $CERT_DIR/"
echo "   📄 Certificate: $CERT_DIR/cert.pem"
echo "   🔑 Private Key: $CERT_DIR/key.pem"
echo "   📅 Valid for: $DAYS_VALID days"
echo ""
echo "To enable HTTPS, update .streamlit/config.toml:"
echo "   sslCertFile = \"$CERT_DIR/cert.pem\""
echo "   sslKeyFile = \"$CERT_DIR/key.pem\""
echo ""
echo "Or run: python run_dashboard.py --https"
