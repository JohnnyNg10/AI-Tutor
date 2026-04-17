#!/usr/bin/env python3
"""
AI Tutor Project Startup Script
Handles encoding issues and provides clear startup instructions
"""

import os
import sys
import subprocess
import platform


def print_step(step_num, message):
    """Print formatted step message"""
    print(f"\n{'='*60}")
    print(f"Step {step_num}: {message}")
    print('='*60)


def check_python_version():
    """Check Python version"""
    print_step(1, "Checking Python Version")
    version = sys.version_info
    print(f"Python version: {version.major}.{version.minor}.{version.micro}")
    
    if version.major < 3 or (version.major == 3 and version.minor < 10):
        print("ERROR: Python 3.10+ required")
        return False
    
    print("OK: Python version is compatible")
    return True


def setup_environment():
    """Setup virtual environment"""
    print_step(2, "Setting up Virtual Environment")
    
    venv_path = os.path.join(os.path.dirname(__file__), 'venv')
    
    if os.path.exists(venv_path):
        print(f"Virtual environment already exists: {venv_path}")
    else:
        print("Creating virtual environment...")
        subprocess.run([sys.executable, '-m', 'venv', 'venv'], check=True)
        print("Virtual environment created")
    
    # Return activation command
    if platform.system() == 'Windows':
        activate_cmd = os.path.join(venv_path, 'Scripts', 'activate')
        pip_cmd = os.path.join(venv_path, 'Scripts', 'pip')
        python_cmd = os.path.join(venv_path, 'Scripts', 'python')
    else:
        activate_cmd = os.path.join(venv_path, 'bin', 'activate')
        pip_cmd = os.path.join(venv_path, 'bin', 'pip')
        python_cmd = os.path.join(venv_path, 'bin', 'python')
    
    return activate_cmd, pip_cmd, python_cmd


def install_dependencies(pip_cmd):
    """Install dependencies with error handling"""
    print_step(3, "Installing Dependencies")
    
    backend_dir = os.path.join(os.path.dirname(__file__), 'backend')
    req_file = os.path.join(backend_dir, 'requirements.txt')
    
    # Set environment variables for pip
    env = os.environ.copy()
    env['PYTHONIOENCODING'] = 'utf-8'
    
    # Install with trusted hosts to avoid SSL issues
    cmd = [
        pip_cmd, 'install',
        '--trusted-host', 'pypi.org',
        '--trusted-host', 'files.pythonhosted.org',
        '-r', req_file
    ]
    
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, env=env)
    
    if result.returncode != 0:
        print("\nWARNING: Some packages may have failed to install")
        print("You may need to:")
        print("1. Check your internet connection")
        print("2. Configure proxy settings if behind a firewall")
        print("3. Install packages manually")
        return False
    
    return True


def create_env_file(backend_dir):
    """Create .env file if not exists"""
    print_step(4, "Checking Environment Configuration")
    
    env_file = os.path.join(backend_dir, '.env')
    env_example = os.path.join(os.path.dirname(__file__), '.env.example')
    
    if os.path.exists(env_file):
        print(f"Environment file exists: {env_file}")
        return True
    
    # Create default .env
    default_env = """# AI Tutor Environment Configuration

# Database (SQLite for development)
DATABASE_URL=sqlite+aiosqlite:///./ai_tutor.db

# Redis
REDIS_URL=redis://localhost:6379/0

# LLM API Keys (add your keys here)
OPENAI_API_KEY=your_openai_key_here
DASHSCOPE_API_KEY=your_dashscope_key_here
SILICONFLOW_API_KEY=your_siliconflow_key_here

# App Settings
APP_NAME=AI Tutor
APP_VERSION=3.0.0
DEBUG=true
LOG_LEVEL=INFO

# CORS
CORS_ORIGINS=["http://localhost:3000","http://localhost:8080","http://localhost:5173"]

# File Paths
LOG_DIR=logs
UPLOAD_DIR=uploads
CHROMA_PERSIST_DIR=chroma_db
KG_PERSIST_DIR=knowledge_graph
"""
    
    with open(env_file, 'w', encoding='utf-8') as f:
        f.write(default_env)
    
    print(f"Created default environment file: {env_file}")
    print("IMPORTANT: Please edit this file and add your API keys!")
    return True


def print_startup_instructions(python_cmd, backend_dir):
    """Print final startup instructions"""
    print_step(5, "Startup Instructions")
    
    print("\nTo start the AI Tutor backend server:")
    print("\n1. Activate virtual environment:")
    if platform.system() == 'Windows':
        print(f"   venv\\Scripts\\activate")
    else:
        print(f"   source venv/bin/activate")
    
    print("\n2. Start the server (choose one):")
    print(f"\n   Option A - Using start.py:")
    print(f"   cd backend")
    print(f"   {python_cmd} start.py")
    
    print(f"\n   Option B - Using uvicorn directly:")
    print(f"   cd backend")
    print(f"   {python_cmd} -m uvicorn main:app --reload --host 0.0.0.0 --port 8000")
    
    print("\n3. Access the API:")
    print("   API Docs: http://localhost:8000/docs")
    print("   Health Check: http://localhost:8000/health")
    
    print("\n4. Before starting, make sure to:")
    print("   - Edit backend/.env and add your API keys")
    print("   - Start Redis server (if using Redis)")
    print("   - Initialize the database (done automatically on first run)")


def main():
    """Main setup function"""
    print("\n" + "="*60)
    print("AI Tutor Project Setup")
    print("="*60)
    
    # Check Python version
    if not check_python_version():
        sys.exit(1)
    
    # Setup virtual environment
    activate_cmd, pip_cmd, python_cmd = setup_environment()
    
    # Install dependencies
    install_dependencies(pip_cmd)
    
    # Create env file
    backend_dir = os.path.join(os.path.dirname(__file__), 'backend')
    create_env_file(backend_dir)
    
    # Print instructions
    print_startup_instructions(python_cmd, backend_dir)
    
    print("\n" + "="*60)
    print("Setup Complete!")
    print("="*60 + "\n")


if __name__ == "__main__":
    main()
