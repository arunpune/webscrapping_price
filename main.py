#!/usr/bin/env python3
"""
UPrinting Automation Framework - Main Entry Point
================================================

Main entry point for the UPrinting Automation Framework.
Provides both CLI and web interface options.

Author: AI Assistant
Date: 2025-08-30
"""

import sys
import argparse
from pathlib import Path
from loguru import logger

# Add current directory to path for imports
sys.path.append(str(Path(__file__).parent))

from config import config
from web_interface import run_web_interface
from product_analyzer import ProductAnalyzer
from price_extractor import PriceExtractor

def setup_logging():
    """Setup logging configuration"""
    
    # Remove default logger
    logger.remove()
    
    # Add console logger
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level="INFO"
    )
    
    # Add file logger
    log_file = config.logs_directory / "uprinting_automation.log"
    logger.add(
        log_file,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        level="DEBUG",
        rotation="10 MB",
        retention="7 days"
    )

def validate_environment():
    """Validate environment and configuration"""
    
    logger.info("Validating environment...")
    
    validation = config.validate_config()
    
    for check, status in validation.items():
        if status:
            logger.success(f"✅ {check}")
        else:
            logger.warning(f"⚠️ {check}")
    
    if not validation['products_csv_exists']:
        logger.error(f"Products CSV not found at: {config.products_csv_path}")
        logger.info("Please ensure the CSV file exists or update the path in .env")
        return False
    
    if not validation['has_ai_apis']:
        logger.warning("No AI APIs configured. AI-assisted analysis will be disabled.")
    
    return True

def run_cli_mode():
    """Run in CLI mode for batch processing"""
    
    logger.info("Starting CLI mode...")
    
    # TODO: Implement CLI batch processing
    # This would allow running the framework without the web interface
    # for automated batch processing of all products
    
    logger.info("CLI mode not yet implemented. Use web interface instead.")
    logger.info(f"Run: python main.py --web")

def run_web_mode():
    """Run web interface mode"""
    
    logger.info("Starting web interface mode...")
    logger.info(f"Web interface will be available at: http://{config.web_host}:{config.web_port}")
    
    try:
        run_web_interface()
    except KeyboardInterrupt:
        logger.info("Web interface stopped by user")
    except Exception as e:
        logger.error(f"Error running web interface: {e}")
        raise

def main():
    """Main entry point"""
    
    parser = argparse.ArgumentParser(
        description="UPrinting Automation Framework",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py --web                 # Start web interface (default)
  python main.py --cli                 # Run in CLI mode (batch processing)
  python main.py --validate           # Validate configuration only
        """
    )
    
    parser.add_argument(
        '--web',
        action='store_true',
        default=True,
        help='Run web interface (default)'
    )
    
    parser.add_argument(
        '--cli',
        action='store_true',
        help='Run in CLI mode for batch processing'
    )
    
    parser.add_argument(
        '--validate',
        action='store_true',
        help='Validate configuration and exit'
    )
    
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug logging'
    )
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging()
    
    if args.debug:
        logger.remove()
        logger.add(sys.stdout, level="DEBUG")
    
    logger.info("🚀 UPrinting Automation Framework Starting...")
    logger.info(f"📁 Working directory: {Path.cwd()}")
    logger.info(f"📄 Products CSV: {config.products_csv_path}")
    logger.info(f"🤖 AI APIs available: {len(config.ai_apis)}")
    
    # Validate environment
    if not validate_environment():
        logger.error("Environment validation failed. Please fix the issues above.")
        sys.exit(1)
    
    if args.validate:
        logger.success("✅ Environment validation completed successfully!")
        sys.exit(0)
    
    try:
        if args.cli:
            run_cli_mode()
        else:
            run_web_mode()
            
    except Exception as e:
        logger.error(f"💥 Fatal error: {e}")
        import traceback
        logger.debug(traceback.format_exc())
        sys.exit(1)

if __name__ == "__main__":
    main()
