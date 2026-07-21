#!/usr/bin/env python3
"""
Interactive setup prompt for ITR Family Workspace.
Creates .env file from environment or prompts interactively.
Used by setup.py to gather database credentials.
"""

import os
from pathlib import Path


def create_setup_prompt():
    """
    Interactive setup that can be run as:
    python setup_prompt.py
    
    Or non-interactively with environment variables:
    ITR_DB_USER=... ITR_DB_NAME=... ITR_DB_PASSWORD=... python setup_prompt.py
    """
    
    print("\n" + "="*60)
    print("ITR Family Workspace - Setup Configuration")
    print("="*60 + "\n")
    
    # Check if credentials are in environment
    db_user = os.getenv("ITR_DB_USER")
    db_name = os.getenv("ITR_DB_NAME")
    db_password = os.getenv("ITR_DB_PASSWORD")
    db_hint = os.getenv("ITR_DB_HINT", "")
    
    # If any are missing, prompt
    if not db_user:
        print("Database User Setup:")
        db_user = input("  Enter database username [India_ITR_User]: ").strip()
        db_user = db_user or "India_ITR_User"
    
    if not db_name:
        print("\nDatabase Name Setup:")
        db_name = input("  Enter database name [India_ITR_Family]: ").strip()
        db_name = db_name or "India_ITR_Family"
    
    if not db_password:
        from getpass import getpass
        print("\nDatabase Password Setup:")
        db_password = getpass("  Enter password (will not be echoed): ")
        if not db_password:
            raise ValueError("Password cannot be empty")
    
    if not db_hint:
        print("\nPassword Hint (optional):")
        db_hint = input("  Enter hint for password reminder: ").strip()
    
    # Create .env
    env_path = Path(".env")
    if env_path.exists():
        backup = Path(".env.bak")
        print(f"\nBacking up existing .env to .env.bak")
        import shutil
        shutil.copy(env_path, backup)
    
    env_content = f"""# ITR Family Workspace Configuration
DATABASE_URL=postgresql+psycopg://{db_user}:{db_password}@localhost:5432/{db_name}
ITR_DATA_DIR=./private_data
ITR_DB_HINT={db_hint}
"""
    
    env_path.write_text(env_content)
    os.chmod(env_path, 0o600)
    
    print(f"\n✓ .env created successfully")
    print(f"  User: {db_user}")
    print(f"  Database: {db_name}")
    print(f"  File: {env_path.resolve()}")
    
    return db_user, db_name, db_password, db_hint


if __name__ == "__main__":
    create_setup_prompt()
