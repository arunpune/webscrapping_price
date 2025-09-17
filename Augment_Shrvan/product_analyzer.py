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
            api_test_result = self._test_api_endpoint(product_info['product_id'], options, attr_mappings, soup)
            
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
            # Method 1: Hidden inputs with default values
            calculator_form = soup.find('form', {'id': re.compile(r'calculator_\d+')})
            if calculator_form:
                hidden_inputs = calculator_form.find_all('input', type='hidden')

                # Create a mapping of attribute numbers to their default values
                attr_defaults = {}
                for hidden_input in hidden_inputs:
                    name = hidden_input.get('name', '')
                    value = hidden_input.get('value', '')
                    if name.startswith('attr') and value:
                        attr_defaults[name] = value

                logger.info(f"Found default attributes: {attr_defaults}")

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

            # Method 3: Common UPrinting patterns (fallback)
            if not mappings:
                logger.warning("No attribute mappings found, using common patterns")
                # These are common UPrinting attribute patterns
                common_mappings = {
                    'Size': 'attr3',
                    'Paper': 'attr1',
                    'Quantity': 'attr5',
                    'Printing Time': 'attr6',
                    'Pages': 'attr4',
                    'Printed Side': 'attr4',
                    'Bundling': 'attr400',
                    'Binding': 'attr400'
                }

                # Try to match option names with common patterns
                for option_name in mappings.keys():
                    for pattern, attr in common_mappings.items():
                        if pattern.lower() in option_name.lower():
                            mappings[option_name] = attr
                            break

        except Exception as e:
            logger.debug(f"Error extracting attribute mappings: {e}")

        return mappings

    def _extract_default_attribute_values(self, soup: BeautifulSoup) -> Dict[str, str]:
        """Extract default attribute values from hidden form inputs"""

        default_values = {}

        try:
            # Find calculator form
            calculator_form = soup.find('form', {'id': re.compile(r'calculator_\d+')})
            if calculator_form:
                # Get all hidden inputs with attribute names
                hidden_inputs = calculator_form.find_all('input', type='hidden')

                for hidden_input in hidden_inputs:
                    name = hidden_input.get('name', '')
                    value = hidden_input.get('value', '')

                    if name.startswith('attr') and value and value.isdigit():
                        default_values[name] = value
                        logger.debug(f"Found default {name}: {value}")

            # Also check for data attributes on the page
            elements_with_data_attrs = soup.find_all(attrs={'data-attr': True})
            for element in elements_with_data_attrs:
                data_attr = element.get('data-attr')
                data_value = element.get('data-value') or element.get('value')

                if data_attr and data_value and data_value.isdigit():
                    attr_name = f"attr{data_attr}"
                    if attr_name not in default_values:
                        default_values[attr_name] = data_value
                        logger.debug(f"Found data attribute {attr_name}: {data_value}")

        except Exception as e:
            logger.debug(f"Error extracting default values: {e}")

        return default_values
    
    def _test_api_endpoint(self, product_id: str, options: Dict, attr_mappings: Dict, soup: BeautifulSoup = None) -> Dict[str, Any]:
        """Test API endpoint with sample data"""

        if not product_id or not options:
            return {'success': False, 'error': 'Missing product ID or options'}

        try:
            # Create sample payload with enhanced validation and error handling
            payload = {'product_id': product_id}

            # First, try to extract default values from the page
            default_values = {}
            if soup:
                default_values = self._extract_default_attribute_values(soup)
                logger.info(f"Found default attribute values: {default_values}")
            else:
                logger.warning("No soup provided for default values extraction")

            # Add sample values for each option with better mapping and validation
            for option_name, option_list in options.items():
                if not option_list:
                    continue

                # Get the first valid option ID
                valid_option = None
                for option in option_list:
                    option_id = option.get('id', '').strip()
                    if option_id and option_id.isdigit() and int(option_id) > 0:
                        valid_option = option
                        break

                if not valid_option:
                    logger.warning(f"No valid option ID found for {option_name}")
                    continue

                option_id = valid_option['id']

                if attr_mappings.get(option_name):
                    attr_name = attr_mappings[option_name]
                    payload[attr_name] = str(option_id)
                else:
                    # Enhanced attribute guessing with validation - order matters!
                    if 'time' in option_name.lower() or 'turnaround' in option_name.lower() or 'rush' in option_name.lower() or 'business' in option_name.lower():
                        payload['attr6'] = str(option_id)
                        logger.info(f"🕒 Printing time mapped: {option_name} = {option_id} → attr6")
                    elif 'quantity' in option_name.lower():
                        payload['attr5'] = str(option_id)
                        logger.info(f"📊 Quantity mapped: {option_name} = {option_id} → attr5")
                    elif 'size' in option_name.lower() or 'format' in option_name.lower():
                        payload['attr3'] = str(option_id)
                    elif 'paper' in option_name.lower() or 'material' in option_name.lower() or 'stock' in option_name.lower():
                        payload['attr1'] = str(option_id)
                    elif 'page' in option_name.lower() or 'side' in option_name.lower() or 'print' in option_name.lower():
                        payload['attr4'] = str(option_id)
                    elif 'bundling' in option_name.lower() or 'binding' in option_name.lower() or 'finish' in option_name.lower():
                        payload['attr400'] = str(option_id)
                    elif any(char.isdigit() for char in valid_option['text']) and 'time' not in option_name.lower():
                        # Only assign to quantity if it's not already assigned and this looks like a quantity
                        if 'attr5' not in payload:
                            payload['attr5'] = str(option_id)
                            logger.info(f"📊 Fallback quantity mapped: {option_name} = {option_id} → attr5")

            # Use default values for missing required attributes (but be careful not to mix them up)
            required_attrs = ['attr1', 'attr3', 'attr4', 'attr6']  # Don't auto-assign attr5 here
            for attr in required_attrs:
                if attr not in payload and attr in default_values:
                    payload[attr] = default_values[attr]
                    logger.info(f"Using default value for {attr}: {default_values[attr]}")

            # Ensure we have minimum required attributes with fallback values
            if 'attr5' not in payload:  # Quantity is critical
                # First try to find a proper quantity option
                quantity_found = False
                for option_name, option_list in options.items():
                    if 'quantity' in option_name.lower() and option_list:
                        for option in option_list:
                            if option['id'].isdigit() and int(option['id']) > 0:
                                payload['attr5'] = str(option['id'])
                                logger.info(f"Using quantity option: {option['text']} (ID: {option['id']})")
                                quantity_found = True
                                break
                        if quantity_found:
                            break

                # If no quantity option found, look for numeric options
                if not quantity_found:
                    for option_name, option_list in options.items():
                        if option_list:
                            for option in option_list:
                                if (any(char.isdigit() for char in option['text']) and
                                    option['id'].isdigit() and int(option['id']) > 0 and
                                    option['id'] not in [v for k, v in default_values.items() if k != 'attr5']):
                                    payload['attr5'] = str(option['id'])
                                    logger.info(f"Using fallback quantity: {option['text']} (ID: {option['id']})")
                                    quantity_found = True
                                    break
                            if quantity_found:
                                break

                # Last resort: use default attr5 if available and not conflicting
                if not quantity_found and 'attr5' in default_values:
                    payload['attr5'] = default_values['attr5']
                    logger.info(f"Using default attr5: {default_values['attr5']}")

            logger.info(f"Testing API with payload: {payload}")

            # Validate payload before sending
            if not self._validate_api_payload(payload):
                return {
                    'success': False,
                    'error': 'Invalid payload: missing required attributes or invalid IDs',
                    'payload': payload
                }

            # Make test API call with retries
            api_url = f"{config.uprinting_api_base_url}/computePrice?website_code=UP"

            for attempt in range(3):  # Try up to 3 times
                try:
                    response = self.session.post(api_url, json=payload, timeout=15)

                    logger.info(f"API Response Status: {response.status_code} (attempt {attempt + 1})")
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
                    elif response.status_code == 412:
                        # Handle specific 412 error
                        error_data = response.json() if response.text else {}
                        error_msg = error_data.get('ErrorMessage', 'Unknown 412 error')

                        if 'Invalid Attribute Value ID' in error_msg:
                            # Try to fix the payload and retry
                            fixed_payload = self._fix_invalid_attribute_payload(payload, error_msg)
                            if fixed_payload != payload:
                                logger.info(f"Retrying with fixed payload: {fixed_payload}")
                                payload = fixed_payload
                                continue

                        logger.error(f"API Test Failed (412): {error_msg}")
                        return {
                            'success': False,
                            'error': f"HTTP 412: {error_msg}",
                            'payload': payload,
                            'response': response.text[:500]
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
                    if attempt == 2:  # Last attempt
                        logger.error(f"API Test Exception: {e}")
                        return {
                            'success': False,
                            'error': str(e),
                            'payload': payload
                        }
                    else:
                        logger.warning(f"API Test attempt {attempt + 1} failed: {e}, retrying...")
                        time.sleep(1)  # Wait before retry

        except Exception as e:
            logger.error(f"API Test Exception: {e}")
            return {
                'success': False,
                'error': str(e),
                'payload': payload if 'payload' in locals() else None
            }

    def _validate_api_payload(self, payload: Dict[str, Any]) -> bool:
        """Validate API payload before sending"""

        # Check required fields
        if not payload.get('product_id'):
            logger.warning("Missing product_id in payload")
            return False

        # Check for at least one attribute
        attr_count = sum(1 for key in payload.keys() if key.startswith('attr'))
        if attr_count == 0:
            logger.warning("No attributes in payload")
            return False

        # Validate attribute values are numeric
        for key, value in payload.items():
            if key.startswith('attr'):
                if not str(value).isdigit():
                    logger.warning(f"Non-numeric attribute value: {key}={value}")
                    return False

        return True

    def _fix_invalid_attribute_payload(self, payload: Dict[str, Any], error_msg: str) -> Dict[str, Any]:
        """Try to fix invalid attribute values in payload"""

        fixed_payload = payload.copy()

        # Extract the invalid ID from error message
        import re
        id_match = re.search(r'Invalid Attribute Value ID (\d+)', error_msg)
        if id_match:
            invalid_id = id_match.group(1)
            logger.info(f"Trying to fix invalid ID: {invalid_id}")

            # Find which attribute has this invalid ID and try to replace it
            for attr_name, attr_value in payload.items():
                if attr_name.startswith('attr') and str(attr_value) == invalid_id:
                    # Try to find a different value for this attribute
                    logger.info(f"Found invalid ID in {attr_name}, trying to fix...")

                    # Remove the problematic attribute for now
                    del fixed_payload[attr_name]
                    logger.info(f"Removed problematic attribute {attr_name}")
                    break

        return fixed_payload

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
