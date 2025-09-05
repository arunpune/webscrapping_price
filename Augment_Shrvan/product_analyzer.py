#!/usr/bin/env python3
"""
Product Analyzer Module
======================

Analyzes UPrinting products to extract options, IDs, and API endpoints.

Author: AI Assistant
Date: 2025-08-30
"""

import requests
import re
import json
import time
from bs4 import BeautifulSoup
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
from loguru import logger

from config import config, UPRINTING_HEADERS
from ai_integration import ai_manager

class ProductAnalyzer:
    """Analyzes UPrinting products to extract options and pricing structure"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(UPRINTING_HEADERS)
        
    def analyze_product(self, product_url: str, product_name: str) -> Dict[str, Any]:
        """Analyze a single product to extract all options and structure"""
        
        logger.info(f"Analyzing product: {product_name}")
        logger.info(f"URL: {product_url}")
        
        try:
            # Fetch product page
            response = self.session.get(product_url, timeout=30)
            response.raise_for_status()
            
            # Parse HTML
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Extract basic product info
            product_info = self._extract_basic_info(soup, product_url)
            
            # Extract options using multiple methods
            options = self._extract_options_comprehensive(soup)
            
            # Extract attribute mappings
            attr_mappings = self._extract_attribute_mappings(soup)
            
            # Use AI for additional analysis if needed
            if not options or len(options) < 3:
                logger.info("Using AI for additional option analysis")
                ai_analysis = ai_manager.analyze_product_options(str(soup), product_url)
                if ai_analysis:
                    options.update(ai_analysis.get('options', {}))
                    attr_mappings.update(ai_analysis.get('attribute_mappings', {}))
            
            # Test API endpoint
            api_test_result = self._test_api_endpoint(product_info['product_id'], options, attr_mappings)
            
            result = {
                'product_name': product_name,
                'product_url': product_url,
                'product_id': product_info['product_id'],
                'form_id': product_info['form_id'],
                'options': options,
                'attribute_mappings': attr_mappings,
                'api_test': api_test_result,
                'analysis_timestamp': time.time(),
                'total_combinations': self._calculate_combinations(options),
                'status': 'success'
            }
            
            logger.success(f"Successfully analyzed {product_name}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to analyze {product_name}: {e}")
            return {
                'product_name': product_name,
                'product_url': product_url,
                'error': str(e),
                'status': 'failed',
                'analysis_timestamp': time.time()
            }
    
    def _extract_basic_info(self, soup: BeautifulSoup, product_url: str) -> Dict[str, str]:
        """Extract basic product information"""
        
        # Find calculator form
        calculator_form = soup.find('form', {'id': re.compile(r'calculator_\d+')})
        
        if calculator_form:
            form_id = calculator_form.get('id', '')
            product_id_match = re.search(r'calculator_(\d+)', form_id)
            product_id = product_id_match.group(1) if product_id_match else None
        else:
            form_id = None
            product_id = None
            
            # Try to find product ID in other places
            scripts = soup.find_all('script')
            for script in scripts:
                if script.string and 'product_id' in script.string:
                    match = re.search(r'product_id["\']?\s*:\s*["\']?(\d+)', script.string)
                    if match:
                        product_id = match.group(1)
                        break
        
        return {
            'product_id': product_id,
            'form_id': form_id
        }
    
    def _extract_options_comprehensive(self, soup: BeautifulSoup) -> Dict[str, List[Dict[str, str]]]:
        """Extract options using multiple methods"""
        
        options = {}
        
        # Method 1: Dropdown containers
        dropdown_containers = soup.find_all('div', class_='dropdown')
        
        for container in dropdown_containers:
            option_data = self._extract_dropdown_options(container)
            if option_data:
                option_name, option_values = option_data
                if option_values:
                    options[option_name] = option_values
        
        # Method 2: Select elements
        select_elements = soup.find_all('select')
        for select in select_elements:
            option_data = self._extract_select_options(select)
            if option_data:
                option_name, option_values = option_data
                if option_values:
                    options[option_name] = option_values
        
        # Method 3: Radio button groups
        radio_groups = self._extract_radio_options(soup)
        options.update(radio_groups)
        
        return options
    
    def _extract_dropdown_options(self, container) -> Optional[Tuple[str, List[Dict[str, str]]]]:
        """Extract options from dropdown container"""
        
        try:
            # Find label
            label_elem = container.find_previous('label')
            if not label_elem:
                label_elem = container.find('label')
            
            if not label_elem:
                return None
            
            option_name = label_elem.get_text(strip=True).replace(':', '').strip()
            
            # Find dropdown menu
            dropdown_menu = container.find('ul', class_='dropdown-menu')
            if not dropdown_menu:
                return None
            
            menu_items = dropdown_menu.find_all('li')
            option_values = []
            
            for item in menu_items:
                link = item.find('a')
                if link:
                    value = link.get('data-value')
                    text = link.get('data-display') or link.get_text(strip=True)
                    
                    if value and text and text not in ['', 'Select...']:
                        option_values.append({
                            'id': str(value),
                            'text': text.strip()
                        })
            
            return option_name, option_values
            
        except Exception as e:
            logger.debug(f"Error extracting dropdown options: {e}")
            return None
    
    def _extract_select_options(self, select_elem) -> Optional[Tuple[str, List[Dict[str, str]]]]:
        """Extract options from select element"""
        
        try:
            # Find associated label
            select_id = select_elem.get('id', '')
            label_elem = None
            
            if select_id:
                label_elem = select_elem.find_previous('label', {'for': select_id})
            
            if not label_elem:
                label_elem = select_elem.find_previous('label')
            
            if not label_elem:
                return None
            
            option_name = label_elem.get_text(strip=True).replace(':', '').strip()
            
            # Extract options
            option_elements = select_elem.find_all('option')
            option_values = []
            
            for option in option_elements:
                value = option.get('value')
                text = option.get_text(strip=True)
                
                if value and text and text not in ['', 'Select...', 'Choose...']:
                    option_values.append({
                        'id': str(value),
                        'text': text.strip()
                    })
            
            return option_name, option_values
            
        except Exception as e:
            logger.debug(f"Error extracting select options: {e}")
            return None
    
    def _extract_radio_options(self, soup: BeautifulSoup) -> Dict[str, List[Dict[str, str]]]:
        """Extract radio button options"""
        
        radio_groups = {}
        
        try:
            radio_inputs = soup.find_all('input', type='radio')
            
            # Group by name attribute
            groups = {}
            for radio in radio_inputs:
                name = radio.get('name', '')
                if name:
                    if name not in groups:
                        groups[name] = []
                    groups[name].append(radio)
            
            # Process each group
            for group_name, radios in groups.items():
                option_values = []
                
                for radio in radios:
                    value = radio.get('value')
                    radio_id = radio.get('id', '')
                    
                    # Find associated label
                    label_elem = None
                    if radio_id:
                        label_elem = soup.find('label', {'for': radio_id})
                    
                    if not label_elem:
                        label_elem = radio.find_next('label')
                    
                    if label_elem:
                        text = label_elem.get_text(strip=True)
                    else:
                        text = value
                    
                    if value and text:
                        option_values.append({
                            'id': str(value),
                            'text': text.strip()
                        })
                
                if option_values:
                    # Clean up group name
                    clean_name = group_name.replace('_', ' ').title()
                    radio_groups[clean_name] = option_values
        
        except Exception as e:
            logger.debug(f"Error extracting radio options: {e}")
        
        return radio_groups
    
    def _extract_attribute_mappings(self, soup: BeautifulSoup) -> Dict[str, str]:
        """Extract attribute mappings from hidden inputs and data attributes"""
        
        mappings = {}
        
        try:
            # Method 1: Hidden inputs
            calculator_form = soup.find('form', {'id': re.compile(r'calculator_\d+')})
            if calculator_form:
                hidden_inputs = calculator_form.find_all('input', type='hidden')
                
                for hidden_input in hidden_inputs:
                    name = hidden_input.get('name', '')
                    if 'attr' in name and name.startswith('attr'):
                        # Try to find corresponding option name
                        # This is complex and may need AI assistance
                        pass
            
            # Method 2: Data attributes on dropdown buttons
            dropdown_buttons = soup.find_all('button', class_='dropdown-toggle')
            for button in dropdown_buttons:
                data_attr = button.get('data-attr')
                if data_attr:
                    # Find associated label
                    container = button.find_parent('div', class_='dropdown')
                    if container:
                        label_elem = container.find_previous('label')
                        if label_elem:
                            option_name = label_elem.get_text(strip=True).replace(':', '').strip()
                            mappings[option_name] = f"attr{data_attr}"
        
        except Exception as e:
            logger.debug(f"Error extracting attribute mappings: {e}")
        
        return mappings
    
    def _test_api_endpoint(self, product_id: str, options: Dict, attr_mappings: Dict) -> Dict[str, Any]:
        """Test API endpoint with sample data"""

        if not product_id or not options:
            return {'success': False, 'error': 'Missing product ID or options'}

        try:
            # Create sample payload with better logic
            payload = {'product_id': product_id}

            # Add sample values for each option with better mapping
            for option_name, option_list in options.items():
                if option_list and attr_mappings.get(option_name):
                    attr_name = attr_mappings[option_name]
                    # Use first available option
                    payload[attr_name] = option_list[0]['id']
                elif option_list:
                    # Try to guess attribute mapping if not found
                    if 'quantity' in option_name.lower():
                        payload['attr5'] = option_list[0]['id']
                    elif 'size' in option_name.lower():
                        payload['attr3'] = option_list[0]['id']
                    elif 'paper' in option_name.lower():
                        payload['attr1'] = option_list[0]['id']
                    elif 'page' in option_name.lower() or 'side' in option_name.lower():
                        payload['attr4'] = option_list[0]['id']

            logger.info(f"Testing API with payload: {payload}")

            # Make test API call
            api_url = f"{config.uprinting_api_base_url}/computePrice?website_code=UP"
            response = self.session.post(api_url, json=payload, timeout=15)

            logger.info(f"API Response Status: {response.status_code}")
            logger.info(f"API Response: {response.text[:500]}")

            if response.status_code == 200:
                data = response.json()
                price = data.get('price', 'N/A')
                logger.success(f"API Test Success: Price = ${price}")

                return {
                    'success': True,
                    'price': price,
                    'payload': payload,
                    'response_sample': {k: v for k, v in data.items() if k in ['price', 'total_price', 'unit_price', 'qty']},
                    'full_response': data
                }
            else:
                error_msg = f"HTTP {response.status_code}: {response.text[:200]}"
                logger.error(f"API Test Failed: {error_msg}")
                return {
                    'success': False,
                    'error': error_msg,
                    'payload': payload,
                    'response': response.text[:500]
                }

        except Exception as e:
            logger.error(f"API Test Exception: {e}")
            return {
                'success': False,
                'error': str(e),
                'payload': payload if 'payload' in locals() else None
            }

    def find_option_ids(self, product_url: str, option_name: str, option_values: List[str]) -> Dict[str, str]:
        """Find IDs for manually added option values"""

        logger.info(f"Finding IDs for {option_name}: {option_values}")

        try:
            # Re-fetch the product page
            response = self.session.get(product_url, timeout=30)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'html.parser')

            # Look for dropdown options that match the values
            found_ids = {}

            # Search in all dropdown menus
            dropdown_containers = soup.find_all('div', class_='dropdown')

            for container in dropdown_containers:
                dropdown_menu = container.find('ul', class_='dropdown-menu')
                if not dropdown_menu:
                    continue

                menu_items = dropdown_menu.find_all('li')

                for item in menu_items:
                    link = item.find('a')
                    if link:
                        value_id = link.get('data-value')
                        text = link.get('data-display') or link.get_text(strip=True)

                        # Check if this text matches any of our target values
                        for target_value in option_values:
                            if (text.lower().strip() == target_value.lower().strip() or
                                target_value.lower().strip() in text.lower().strip() or
                                text.lower().strip() in target_value.lower().strip()):
                                found_ids[target_value] = value_id
                                logger.success(f"Found ID for '{target_value}': {value_id}")

            return found_ids

        except Exception as e:
            logger.error(f"Error finding option IDs: {e}")
            return {}
    
    def _calculate_combinations(self, options: Dict[str, List]) -> int:
        """Calculate total possible combinations"""
        
        total = 1
        for option_list in options.values():
            if option_list:
                total *= len(option_list)
        return total
    
    def save_analysis(self, analysis_result: Dict[str, Any], output_dir: Path) -> Path:
        """Save analysis result to file"""
        
        product_name = analysis_result.get('product_name', 'unknown')
        safe_name = re.sub(r'[^\w\s-]', '', product_name).strip()
        safe_name = re.sub(r'[-\s]+', '_', safe_name)
        
        filename = f"{safe_name}_analysis.json"
        filepath = output_dir / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(analysis_result, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Saved analysis to: {filepath}")
        return filepath
