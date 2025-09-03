#!/usr/bin/env python3
"""
UPrinting Automation Framework Setup Script
==========================================

Setup script to install dependencies and configure the framework.

Author: AI Assistant
Date: 2025-08-30
"""

import os
import sys
import subprocess
from pathlib import Path

def run_command(command, description):
    """Run a command and handle errors"""
    print(f"🔄 {description}...")
    
    try:
        result = subprocess.run(
            command,
            shell=True,
            check=True,
            capture_output=True,
            text=True
        )
        print(f"✅ {description} completed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} failed:")
        print(f"   Command: {command}")
        print(f"   Error: {e.stderr}")
        return False

def install_dependencies():
    """Install Python dependencies"""
    
    print("📦 Installing Python dependencies...")
    
    # Check if pip is available
    if not run_command("pip --version", "Checking pip availability"):
        print("❌ pip is not available. Please install Python with pip.")
        return False
    
    # Install requirements
    if not run_command("pip install -r requirements.txt", "Installing requirements"):
        print("❌ Failed to install requirements. Please check the error above.")
        return False
    
    return True

def create_directories():
    """Create necessary directories"""
    
    print("📁 Creating directories...")
    
    directories = [
        "output",
        "logs", 
        "temp",
        "static",
        "static/css",
        "static/js"
    ]
    
    for directory in directories:
        dir_path = Path(directory)
        dir_path.mkdir(exist_ok=True)
        print(f"   ✅ Created: {directory}")
    
    return True

def setup_environment():
    """Setup environment file"""
    
    print("⚙️ Setting up environment...")
    
    env_example = Path(".env.example")
    env_file = Path(".env")
    
    if not env_file.exists() and env_example.exists():
        # Copy example to .env
        with open(env_example, 'r') as f:
            content = f.read()
        
        with open(env_file, 'w') as f:
            f.write(content)
        
        print("   ✅ Created .env file from .env.example")
        print("   ⚠️ Please edit .env file with your configuration")
    elif env_file.exists():
        print("   ✅ .env file already exists")
    else:
        print("   ❌ .env.example not found")
        return False
    
    return True

def check_csv_file():
    """Check if products CSV file exists"""
    
    print("📄 Checking products CSV file...")
    
    # Check common locations
    csv_paths = [
        "../UPrinting_Products_CLEANED.csv",
        "UPrinting_Products_CLEANED.csv",
        "../UPrinting_All_Products.csv"
    ]
    
    for csv_path in csv_paths:
        if Path(csv_path).exists():
            print(f"   ✅ Found products CSV: {csv_path}")
            return True
    
    print("   ⚠️ Products CSV not found in expected locations:")
    for csv_path in csv_paths:
        print(f"      - {csv_path}")
    print("   Please update PRODUCTS_CSV_PATH in .env file")
    
    return False

def create_chrome_mcp_config():
    """Create Chrome MCP configuration file"""
    
    print("🌐 Creating Chrome MCP configuration...")
    
    config_content = {
        "server": {
            "command": "npx",
            "args": ["@modelcontextprotocol/server-chrome"],
            "env": {}
        },
        "client": {
            "timeout": 30000,
            "retries": 3
        }
    }
    
    import json
    
    config_file = Path("chrome_mcp_config.json")
    with open(config_file, 'w') as f:
        json.dump(config_content, f, indent=2)
    
    print("   ✅ Created chrome_mcp_config.json")
    print("   ℹ️ This is optional and only needed if using Chrome MCP integration")
    
    return True

def main():
    """Main setup function"""
    
    print("🚀 UPrinting Automation Framework Setup")
    print("=" * 50)
    
    # Check Python version
    if sys.version_info < (3, 8):
        print("❌ Python 3.8 or higher is required")
        sys.exit(1)
    
    print(f"✅ Python version: {sys.version}")
    
    # Run setup steps
    steps = [
        ("Creating directories", create_directories),
        ("Installing dependencies", install_dependencies),
        ("Setting up environment", setup_environment),
        ("Checking CSV file", check_csv_file),
        ("Creating Chrome MCP config", create_chrome_mcp_config)
    ]
    
    success_count = 0
    
    for step_name, step_function in steps:
        print(f"\n📋 {step_name}...")
        if step_function():
            success_count += 1
        else:
            print(f"⚠️ {step_name} had issues (see above)")
    
    print(f"\n🎉 Setup completed: {success_count}/{len(steps)} steps successful")
    
    if success_count == len(steps):
        print("\n✅ All setup steps completed successfully!")
        print("\n🚀 Next steps:")
        print("   1. Edit .env file with your configuration")
        print("   2. Add AI API keys if you have them")
        print("   3. Run: python main.py --web")
    else:
        print("\n⚠️ Some setup steps had issues. Please review the messages above.")
        print("   The framework may still work, but some features might be limited.")
    
    print(f"\n📚 For more information, see README.md")

if __name__ == "__main__":
    main()
