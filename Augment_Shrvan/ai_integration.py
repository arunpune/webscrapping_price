#!/usr/bin/env python3
"""
AI Integration Module
====================

Handles AI API integration with fallback support for multiple providers.

Author: AI Assistant
Date: 2025-08-30
"""

import json
import time
from typing import Dict, List, Optional, Any
from config import config
from loguru import logger

class AIManager:
    """Manages AI API calls with fallback support"""
    
    def __init__(self):
        self.current_api = None
        self.api_usage = {}
        self.initialize_apis()
    
    def initialize_apis(self):
        """Initialize available AI APIs"""
        self.available_apis = config.get_available_ai_apis()
        
        for api_name in self.available_apis:
            self.api_usage[api_name] = {
                'requests_made': 0,
                'errors': 0,
                'last_used': None,
                'exhausted': False
            }
        
        if self.available_apis:
            self.current_api = self.available_apis[0]
            logger.info(f"AI Manager initialized with {len(self.available_apis)} APIs: {self.available_apis}")
        else:
            logger.warning("No AI APIs configured")
    
    def switch_to_next_api(self):
        """Switch to the next available AI API"""
        if not self.available_apis:
            return False
        
        current_index = self.available_apis.index(self.current_api) if self.current_api else -1
        next_index = (current_index + 1) % len(self.available_apis)
        
        # Find next non-exhausted API
        for i in range(len(self.available_apis)):
            api_name = self.available_apis[(next_index + i) % len(self.available_apis)]
            if not self.api_usage[api_name]['exhausted']:
                self.current_api = api_name
                logger.info(f"Switched to AI API: {api_name}")
                return True
        
        logger.error("All AI APIs are exhausted")
        return False
    
    def make_ai_request(self, prompt: str, context: str = "", max_retries: int = 3) -> Optional[str]:
        """Make AI request with fallback support"""
        
        if not self.current_api:
            logger.error("No AI API available")
            return None
        
        for attempt in range(max_retries):
            try:
                response = self._call_ai_api(self.current_api, prompt, context)
                
                if response:
                    self.api_usage[self.current_api]['requests_made'] += 1
                    self.api_usage[self.current_api]['last_used'] = time.time()
                    return response
                
            except Exception as e:
                logger.error(f"AI API {self.current_api} error (attempt {attempt + 1}): {e}")
                self.api_usage[self.current_api]['errors'] += 1
                
                # If quota exceeded or similar, mark as exhausted and switch
                if "quota" in str(e).lower() or "limit" in str(e).lower():
                    self.api_usage[self.current_api]['exhausted'] = True
                    if not self.switch_to_next_api():
                        break
                
                time.sleep(2 ** attempt)  # Exponential backoff
        
        return None
    
    def _call_ai_api(self, api_name: str, prompt: str, context: str) -> Optional[str]:
        """Call specific AI API"""
        
        api_key = config.get_ai_api_key(api_name)
        if not api_key:
            raise Exception(f"No API key for {api_name}")
        
        full_prompt = f"{context}\n\n{prompt}" if context else prompt
        
        if api_name == 'gemini':
            return self._call_gemini(api_key, full_prompt)
        elif api_name == 'claude':
            return self._call_claude(api_key, full_prompt)
        elif api_name == 'openai':
            return self._call_openai(api_key, full_prompt)
        else:
            raise Exception(f"Unknown AI API: {api_name}")
    
    def _call_gemini(self, api_key: str, prompt: str) -> Optional[str]:
        """Call Google Gemini API"""
        try:
            import google.generativeai as genai
            
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel('gemini-1.5-flash')
            
            response = model.generate_content(prompt)
            return response.text
            
        except ImportError:
            raise Exception("google-generativeai package not installed")
        except Exception as e:
            raise Exception(f"Gemini API error: {e}")
    
    def _call_claude(self, api_key: str, prompt: str) -> Optional[str]:
        """Call Anthropic Claude API"""
        try:
            import anthropic
            
            client = anthropic.Anthropic(api_key=api_key)
            
            response = client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=4000,
                messages=[{"role": "user", "content": prompt}]
            )
            
            return response.content[0].text
            
        except ImportError:
            raise Exception("anthropic package not installed")
        except Exception as e:
            raise Exception(f"Claude API error: {e}")
    
    def _call_openai(self, api_key: str, prompt: str) -> Optional[str]:
        """Call OpenAI API"""
        try:
            import openai
            
            client = openai.OpenAI(api_key=api_key)
            
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=4000
            )
            
            return response.choices[0].message.content
            
        except ImportError:
            raise Exception("openai package not installed")
        except Exception as e:
            raise Exception(f"OpenAI API error: {e}")
    
    def analyze_product_options(self, html_content: str, product_url: str) -> Dict[str, Any]:
        """Use AI to analyze product options from HTML"""
        
        prompt = f"""
        Analyze this UPrinting product page HTML and extract all product options with their IDs.
        
        Product URL: {product_url}
        
        Please identify:
        1. All dropdown options (size, paper, quantity, etc.)
        2. Their corresponding IDs from data-value attributes
        3. The product ID from the form
        4. Any hidden input attributes (attr1, attr2, etc.)
        
        Return the analysis in JSON format with this structure:
        {{
            "product_id": "16",
            "options": {{
                "Size": [
                    {{"id": "644", "text": "3.5\\" x 5\\""}},
                    {{"id": "645", "text": "4\\" x 6\\""}}
                ],
                "Paper": [...]
            }},
            "attribute_mappings": {{
                "Size": "attr3",
                "Paper": "attr1"
            }}
        }}
        
        HTML Content (truncated):
        {html_content[:5000]}...
        """
        
        context = """
        You are analyzing UPrinting product pages to extract pricing options.
        Focus on finding dropdown menus, their data-value attributes, and form structure.
        Be precise with IDs and option names.
        """
        
        response = self.make_ai_request(prompt, context)
        
        if response:
            try:
                # Extract JSON from response
                json_start = response.find('{')
                json_end = response.rfind('}') + 1
                if json_start >= 0 and json_end > json_start:
                    json_str = response[json_start:json_end]
                    return json.loads(json_str)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse AI response as JSON: {e}")
        
        return None
    
    def get_usage_stats(self) -> Dict[str, Any]:
        """Get usage statistics for all APIs"""
        return {
            'current_api': self.current_api,
            'api_usage': self.api_usage,
            'available_apis': self.available_apis
        }

# Global AI manager instance
ai_manager = AIManager()
