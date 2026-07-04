"""Generate a bcrypt password hash for .streamlit/auth.yaml.

Usage:  python scripts/make_hash.py "my-password"
"""
import sys

import bcrypt

if len(sys.argv) < 2:
    print('Usage: python scripts/make_hash.py "your-password"')
    raise SystemExit(1)

pwd = sys.argv[1].encode("utf-8")
print(bcrypt.hashpw(pwd, bcrypt.gensalt()).decode())
