#!/usr/bin/env python3
"""
Automatic setup for ITR Family Workspace.
Handles database creation, environment configuration, and initialization.
Portable across systems - just run: python setup.py
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path
from getpass import getpass

# Color output
class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    END = '\033[0m'


def print_header(msg):
    print(f"\n{Colors.BLUE}{'='*60}")
    print(f"{msg}")
    print(f"{'='*60}{Colors.END}\n")


def print_success(msg):
    print(f"{Colors.GREEN}✓ {msg}{Colors.END}")


def print_warning(msg):
    print(f"{Colors.YELLOW}⚠ {msg}{Colors.END}")


def print_error(msg):
    print(f"{Colors.RED}✗ {msg}{Colors.END}")


def find_psql():
    """Find PostgreSQL psql binary."""
    print_header("Step 1: Locating PostgreSQL")
    
    # Common paths
    common_paths = [
        "/opt/homebrew/bin/psql",  # Homebrew on Apple Silicon
        "/usr/local/bin/psql",      # Homebrew on Intel
        "/usr/bin/psql",            # System
        "/Applications/Postgres.app/Contents/Versions/latest/bin/psql",  # Postgres.app
    ]
    
    # Try 'which' first
    try:
        result = subprocess.run(["which", "psql"], capture_output=True, text=True)
        if result.returncode == 0:
            psql = result.stdout.strip()
            print_success(f"Found psql at: {psql}")
            return psql
    except:
        pass
    
    # Try common paths
    for path in common_paths:
        if Path(path).exists():
            print_success(f"Found psql at: {path}")
            return path
    
    # Try brew to find it
    try:
        result = subprocess.run(["brew", "list", "postgresql"], capture_output=True, text=True)
        if result.returncode == 0:
            result = subprocess.run(["brew", "--prefix", "postgresql"], capture_output=True, text=True)
            prefix = result.stdout.strip()
            psql = os.path.join(prefix, "bin", "psql")
            if Path(psql).exists():
                print_success(f"Found psql at: {psql}")
                return psql
    except:
        pass
    
    print_error("PostgreSQL not found!")
    print("Please install PostgreSQL 18+:")
    print("  brew install postgresql@18")
    print("  brew services start postgresql@18")
    sys.exit(1)


def test_pg_connection(psql_path):
    """Test if PostgreSQL is running."""
    print_header("Step 2: Testing PostgreSQL Connection")
    
    try:
        result = subprocess.run(
            [psql_path, "-U", "postgres", "-c", "SELECT version();"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            version = result.stdout.strip().split('\n')[0]
            print_success(f"PostgreSQL is running: {version}")
            return True
    except subprocess.TimeoutExpired:
        pass
    except Exception as e:
        pass
    
    print_error("Cannot connect to PostgreSQL!")
    print("Please ensure PostgreSQL is running:")
    print("  brew services start postgresql@18")
    sys.exit(1)


def get_db_credentials():
    """Get database credentials from user or environment."""
    print_header("Step 3: Database Credentials")
    
    # Check for env variables
    db_user = os.getenv("ITR_DB_USER")
    db_name = os.getenv("ITR_DB_NAME")
    db_password = os.getenv("ITR_DB_PASSWORD")
    db_hint = os.getenv("ITR_DB_HINT")
    
    if not db_user:
        print("Enter database credentials:")
        db_user = input(f"  Database user [{Colors.YELLOW}India_ITR_User{Colors.END}]: ").strip()
        db_user = db_user or "India_ITR_User"
    
    if not db_name:
        db_name = input(f"  Database name [{Colors.YELLOW}India_ITR_Family{Colors.END}]: ").strip()
        db_name = db_name or "India_ITR_Family"
    
    if not db_password:
        db_password = getpass(f"  Database password: ")
        if not db_password:
            print_error("Password cannot be empty!")
            sys.exit(1)
    
    if not db_hint:
        db_hint = input("  Password hint (optional): ").strip()
    
    print_success(f"User: {db_user}")
    print_success(f"Database: {db_name}")
    print_success(f"Password: {'*' * len(db_password)}")
    if db_hint:
        print_success(f"Hint: {db_hint}")
    
    return db_user, db_name, db_password, db_hint


def create_db_user_and_database(psql_path, db_user, db_name, db_password):
    """Create PostgreSQL user and database."""
    print_header("Step 4: Creating Database User and Database")
    
    # Create user (ignore if exists)
    sql_create_user = f'CREATE USER "{db_user}" WITH PASSWORD \'{db_password}\';'
    result = subprocess.run(
        [psql_path, "-U", "postgres", "-c", sql_create_user],
        capture_output=True,
        text=True
    )
    if result.returncode == 0:
        print_success(f"User '{db_user}' created (or already exists)")
    elif "already exists" in result.stderr:
        print_warning(f"User '{db_user}' already exists")
    else:
        print_error(f"Failed to create user: {result.stderr}")
        sys.exit(1)
    
    # Create database
    sql_create_db = f'CREATE DATABASE "{db_name}" OWNER "{db_user}";'
    result = subprocess.run(
        [psql_path, "-U", "postgres", "-c", sql_create_db],
        capture_output=True,
        text=True
    )
    if result.returncode == 0:
        print_success(f"Database '{db_name}' created")
    elif "already exists" in result.stderr:
        print_warning(f"Database '{db_name}' already exists")
    else:
        print_error(f"Failed to create database: {result.stderr}")
        sys.exit(1)
    
    # Grant privileges
    privs = [
        f'GRANT CONNECT ON DATABASE "{db_name}" TO "{db_user}";',
        f'ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO "{db_user}";',
        f'ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO "{db_user}";',
    ]
    
    for priv in privs:
        subprocess.run(
            [psql_path, "-U", "postgres", "-d", db_name, "-c", priv],
            capture_output=True
        )
    
    print_success("Privileges granted")


def create_env_file(db_user, db_name, db_password, db_hint):
    """Create .env file with database configuration."""
    print_header("Step 5: Creating .env Configuration")
    
    env_path = Path(".env")
    
    env_content = f"""# ITR Family Workspace Configuration
# Auto-generated by setup.py

# PostgreSQL Connection
DATABASE_URL=postgresql+psycopg://{db_user}:{db_password}@localhost:5432/{db_name}

# Data Directory
ITR_DATA_DIR=./private_data

# Database Password Hint (for reference only)
ITR_DB_HINT={db_hint}
"""
    
    if env_path.exists():
        print_warning(f".env already exists, backing up to .env.bak")
        shutil.copy(env_path, ".env.bak")
    
    with open(env_path, "w") as f:
        f.write(env_content)
    
    os.chmod(env_path, 0o600)  # Restrict permissions
    print_success(".env created with restricted permissions (600)")


def setup_python_env():
    """Create Python virtual environment and install dependencies."""
    print_header("Step 6: Setting Up Python Environment")
    
    venv_path = Path(".venv")
    
    if venv_path.exists():
        print_warning("Virtual environment already exists")
    else:
        print("Creating virtual environment...")
        result = subprocess.run([sys.executable, "-m", "venv", ".venv"], capture_output=True)
        if result.returncode == 0:
            print_success("Virtual environment created")
        else:
            print_error(f"Failed to create venv: {result.stderr.decode()}")
            sys.exit(1)
    
    # Determine pip path
    if sys.platform == "darwin" or sys.platform == "linux":
        pip_path = ".venv/bin/pip"
    else:
        pip_path = ".venv\\Scripts\\pip"
    
    # Install requirements
    print("Installing dependencies...")
    result = subprocess.run([pip_path, "install", "-r", "requirements.txt"], capture_output=True, text=True)
    if result.returncode == 0:
        print_success("Dependencies installed")
    else:
        print_error(f"Failed to install dependencies: {result.stderr}")
        sys.exit(1)


def initialize_database():
    """Initialize database tables and seed data."""
    print_header("Step 7: Initializing Database")
    
    # Activate venv and run seed
    if sys.platform == "darwin" or sys.platform == "linux":
        activate_cmd = "source .venv/bin/activate &&"
    else:
        activate_cmd = ".venv\\Scripts\\activate &&"
    
    print("Creating database tables and seeding data...")
    cmd = f"{activate_cmd} python -m itr_workspace.seed"
    
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.returncode == 0:
        print_success("Database initialized with seed data")
        if result.stdout:
            print(result.stdout)
    else:
        print_warning(f"Seed script output: {result.stdout}")
        if result.stderr:
            print(f"Warnings: {result.stderr}")


def verify_setup():
    """Verify the setup is complete."""
    print_header("Step 8: Verifying Setup")
    
    checks = []
    
    # Check .env
    if Path(".env").exists():
        print_success(".env file exists")
        checks.append(True)
    else:
        print_error(".env file not found")
        checks.append(False)
    
    # Check venv
    if Path(".venv").exists():
        print_success("Virtual environment exists")
        checks.append(True)
    else:
        print_error("Virtual environment not found")
        checks.append(False)
    
    # Check private_data
    if Path("private_data").exists():
        print_success("Data directory exists")
        checks.append(True)
    else:
        print_warning("Data directory not yet created (will be created on first upload)")
        checks.append(True)
    
    # Check requirements
    req_file = Path("requirements.txt")
    if req_file.exists():
        print_success("requirements.txt found")
        checks.append(True)
    else:
        print_error("requirements.txt not found")
        checks.append(False)
    
    return all(checks)


def print_next_steps():
    """Print next steps for running the application."""
    print_header("Setup Complete! 🎉")
    
    print(f"""{Colors.GREEN}Next Steps:{Colors.END}

1. {Colors.YELLOW}Activate the virtual environment:{Colors.END}
   source .venv/bin/activate

2. {Colors.YELLOW}Start the Streamlit application:{Colors.END}
   streamlit run app.py

3. {Colors.YELLOW}Open in your browser:{Colors.END}
   http://localhost:8501

4. {Colors.YELLOW}First-use sequence:{Colors.END}
   • Profile: Enter last 4 digits of PAN
   • Residency: Complete worksheet
   • Documents: Upload AIS, TIS, 26AS, bank statements, etc.
   • Income: Enter gross income amounts
   • Tax credits: Enter TDS from 26AS
   • Reconciliation: Three-way matching
   • Review: Resolve blocking issues
   • Export: Generate filing package

{Colors.BLUE}Need help?{Colors.END}
   See README.md for detailed documentation
   
{Colors.BLUE}Database Info:{Colors.END}
   Backup: pg_dump -Fc India_ITR_Family > backup.sql
   Restore: pg_restore -d India_ITR_Family < backup.sql
""")


def main():
    """Main setup orchestration."""
    print(f"\n{Colors.BLUE}{'='*60}")
    print("ITR Family Workspace - Automatic Setup")
    print(f"{'='*60}{Colors.END}\n")
    
    # Check if running from correct directory
    if not Path("app.py").exists():
        print_error("app.py not found! Please run from itr_family_workspace directory")
        sys.exit(1)
    
    try:
        # Steps
        psql_path = find_psql()
        test_pg_connection(psql_path)
        db_user, db_name, db_password, db_hint = get_db_credentials()
        create_db_user_and_database(psql_path, db_user, db_name, db_password)
        create_env_file(db_user, db_name, db_password, db_hint)
        setup_python_env()
        initialize_database()
        
        # Verify
        if verify_setup():
            print_next_steps()
        else:
            print_warning("Some setup checks failed. Please review above.")
    
    except KeyboardInterrupt:
        print_error("\nSetup interrupted by user")
        sys.exit(1)
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
