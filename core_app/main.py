"""
core_app/main.py
Main application entry point. Imports and exposes 'app' from app.py.
Ensures both 'python3 app.py' and 'python3 main.py' execute identically without divergence.
"""
import os
import sys

# Ensure current and parent dirs are on sys.path
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db, Document, User, Contact, KeepAlive  # noqa: F401

if __name__ == "__main__":
    from sqlalchemy import true
    app.run(debug=true, host="0.0.0.0", port=5010)