#!/usr/bin/env python3
"""
UPrinting Automation Framework Configuration
==========================================

Central configuration management for the framework.

Author: AI Assistant
Date: 2025-08-30
"""

import os
import json
from pathlib import Path
from dotenv import load_dotenv
from typing import Dict, List, Optional

# Load environment variables
load_dotenv()

class Config:
    """Configuration management class"""
    
    def __init__(self):
        self.base_dir = Path(__file__).parent
        self.load_config()
    
    def load_config(self):
        """Load all configuration settings"""
        
        # File Paths
        self.products_csv_path = os.getenv('PRODUCTS_CSV_PATH', '../UPrinting_Products_CLEANED.csv')
        self.chrome_mcp_config_path = os.getenv('CHROME_MCP_CONFIG_PATH', 'chrome_mcp_config.json')
        
        # AI API Keys
        self.ai_apis = {
            'gemini': os.getenv('GEMINI_API_KEY'),
            'claude': os.getenv('CLAUDE_API_KEY'),
            'openai': os.getenv('OPENAI_API_KEY')
        }
        
        # Remove None values
        self.ai_apis = {k: v for k, v in self.ai_apis.items() if v}
        
        # UPrinting API
        self.uprinting_api_base_url = os.getenv('UPRINTING_API_BASE_URL', 'https://calculator.uprinting.com/v1')
        self.uprinting_api_auth = os.getenv('UPRINTING_API_AUTH', 'Basic Y2FsY3VsYXRvci5zaXRlOktFZm03NSNYandTTXV4OTJ6VVdEOVQ4QWFmRyF2d1Y2')
        
        # Framework Settings
        self.max_concurrent_requests = int(os.getenv('MAX_CONCURRENT_REQUESTS', '5'))
        self.request_delay_seconds = float(os.getenv('REQUEST_DELAY_SECONDS', '0.02'))
        self.batch_size = int(os.getenv('BATCH_SIZE', '100'))
        self.max_retries = int(os.getenv('MAX_RETRIES', '3'))
        
        # Directory Settings
        self.output_directory = Path(os.getenv('OUTPUT_DIRECTORY', './output'))
        self.logs_directory = Path(os.getenv('LOGS_DIRECTORY', './logs'))
        self.temp_directory = Path(os.getenv('TEMP_DIRECTORY', './temp'))
        
        # Create directories if they don't exist
        for directory in [self.output_directory, self.logs_directory, self.temp_directory]:
            directory.mkdir(exist_ok=True)
        
        # Web Interface Settings
        self.web_host = os.getenv('WEB_HOST', 'localhost')
        self.web_port = int(os.getenv('WEB_PORT', '8080'))
        self.debug_mode = os.getenv('DEBUG_MODE', 'true').lower() == 'true'
        
        # UPrinting Request Headers
        self.uprinting_headers = {
            'Authorization': self.uprinting_api_auth,
            'Content-type': 'application/json',
            'Referer': 'https://www.uprinting.com/',
            'sec-ch-ua': '"Not;A=Brand";v="99", "Google Chrome";v="139", "Chromium";v="139"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36'
        }
    
    def get_chrome_mcp_config(self) -> Optional[Dict]:
        """Load Chrome MCP configuration if available"""
        try:
            config_path = self.base_dir / self.chrome_mcp_config_path
            if config_path.exists():
                with open(config_path, 'r') as f:
                    return json.load(f)
        except Exception as e:
            print(f"Warning: Could not load Chrome MCP config: {e}")
        return None
    
    def get_available_ai_apis(self) -> List[str]:
        """Get list of available AI APIs"""
        return list(self.ai_apis.keys())
    
    def get_ai_api_key(self, api_name: str) -> Optional[str]:
        """Get API key for specific AI service"""
        return self.ai_apis.get(api_name)
    
    def validate_config(self) -> Dict[str, bool]:
        """Validate configuration settings"""
        validation = {
            'products_csv_exists': Path(self.products_csv_path).exists(),
            'has_ai_apis': len(self.ai_apis) > 0,
            'directories_created': all([
                self.output_directory.exists(),
                self.logs_directory.exists(),
                self.temp_directory.exists()
            ]),
            'uprinting_api_configured': bool(self.uprinting_api_auth)
        }
        return validation

# Global configuration instance
config = Config()

# Export commonly used settings
OUTPUT_DIR = config.output_directory
LOGS_DIR = config.logs_directory
TEMP_DIR = config.temp_directory
UPRINTING_HEADERS = config.uprinting_headers
UPRINTING_API_BASE = config.uprinting_api_base_url
