#!/usr/bin/env python3
"""
Price Extractor Module
=====================

Extracts prices for all combinations of product options using UPrinting API.

Author: AI Assistant
Date: 2025-08-30
"""

import requests
import pandas as pd
import time
import json
from itertools import product
from typing import Dict, List, Optional, Any, Callable
from pathlib import Path
from datetime import datetime
from loguru import logger

from config import config, OUTPUT_DIR, UPRINTING_HEADERS

class PriceExtractor:
    """Extracts prices for all product option combinations"""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(UPRINTING_HEADERS)
        self.api_base_url = config.uprinting_api_base_url
        self.should_pause = False
        self.is_paused = False

    def pause_extraction(self):
        """Pause the extraction process"""
        self.should_pause = True
        logger.info("Extraction pause requested")

    def resume_extraction(self):
        """Resume the extraction process"""
        self.should_pause = False
        self.is_paused = False
        logger.info("Extraction resumed")
        
    def extract_all_prices(self,
                          analysis_result: Dict[str, Any],
                          exclude_options: List[str] = None,
                          suboptions_to_exclude: Dict[str, List[str]] = None,
                          progress_callback: Optional[Callable] = None) -> Dict[str, Any]:
        """Extract prices for all combinations of product options"""
        
        if exclude_options is None:
            exclude_options = []
        if suboptions_to_exclude is None:
            suboptions_to_exclude = {}

        product_name = analysis_result['product_name']
        product_id = analysis_result['product_id']
        options = analysis_result['options']
        attr_mappings = analysis_result['attribute_mappings']

        logger.info(f"Starting price extraction for {product_name}")
        logger.info(f"Excluding options: {exclude_options}")
        logger.info(f"Excluding sub-options: {suboptions_to_exclude}")

        # Filter out excluded options and sub-options
        filtered_options = {}
        for name, values in options.items():
            if name not in exclude_options:
                # Filter out excluded sub-options
                if name in suboptions_to_exclude:
                    excluded_ids = suboptions_to_exclude[name]
                    filtered_values = [v for v in values if v['id'] not in excluded_ids]
                    if filtered_values:  # Only include if there are remaining values
                        filtered_options[name] = filtered_values
                        logger.info(f"Option '{name}': excluded {len(excluded_ids)} sub-options, kept {len(filtered_values)}")
                else:
                    filtered_options[name] = values
        
        # Calculate total combinations
        total_combinations = 1
        for option_list in filtered_options.values():
            if option_list:
                total_combinations *= len(option_list)
        
        logger.info(f"Total combinations to extract: {total_combinations:,}")
        
        if progress_callback:
            progress_callback(0, total_combinations, "Starting extraction...")
        
        # Generate all combinations
        results = []
        combination_count = 0
        error_count = 0
        
        option_names = list(filtered_options.keys())
        option_values = [filtered_options[name] for name in option_names]
        
        for combination in product(*option_values):
            combination_count += 1

            # Check for pause request
            if self.should_pause:
                self.is_paused = True
                logger.info("⏸️ Extraction paused by user")
                if progress_callback:
                    progress_callback(
                        combination_count,
                        total_combinations,
                        "⏸️ Extraction paused - waiting for resume..."
                    )

                # Wait until resumed
                while self.should_pause:
                    time.sleep(1)

                self.is_paused = False
                logger.info("▶️ Extraction resumed")

            # Create options dictionary
            options_dict = {}
            option_labels = {}

            for i, option_name in enumerate(option_names):
                option_id, option_label = combination[i]['id'], combination[i]['text']
                options_dict[option_name] = option_id
                option_labels[option_name] = option_label

            # Progress update
            if combination_count % 25 == 0 and progress_callback:
                progress_callback(
                    combination_count,
                    total_combinations,
                    f"Processing combination {combination_count:,}/{total_combinations:,}"
                )

            # Make API call
            api_result = self._make_api_call(product_id, options_dict, attr_mappings)
            
            if api_result['success']:
                result = {
                    'combination_id': combination_count,
                    'product_name': product_name,
                    **option_labels,  # Add all option labels as columns
                    'price': f"${api_result['price']}",
                    'total_price': f"${api_result['total_price']}",
                    'unit_price': api_result['unit_price'],
                    'qty_pieces': api_result['qty'],
                    'turnaround_days': api_result['turnaround'],
                    **{f"{name}_id": options_dict[name] for name in option_names},  # Add IDs
                    'timestamp': datetime.now().isoformat(),
                    'notes': 'Extracted using real API endpoints'
                }
                
                results.append(result)
            else:
                error_count += 1
                logger.debug(f"API error for combination {combination_count}: {api_result.get('error')}")
            
            # Small delay to be respectful to the API
            time.sleep(config.request_delay_seconds)
        
        # Create formatted CSV
        formatted_csv_path = self._create_formatted_csv(results, product_name, filtered_options)
        
        # Create raw CSV
        raw_csv_path = self._create_raw_csv(results, product_name)
        
        extraction_result = {
            'product_name': product_name,
            'total_combinations': total_combinations,
            'total_extracted': len(results),
            'error_count': error_count,
            'success_rate': len(results) / total_combinations * 100 if total_combinations > 0 else 0,
            'formatted_csv_path': str(formatted_csv_path.name),
            'raw_csv_path': str(raw_csv_path.name),
            'extraction_timestamp': datetime.now().isoformat(),
            'options_used': list(filtered_options.keys()),
            'options_excluded': exclude_options
        }
        
        if progress_callback:
            progress_callback(
                len(results), 
                total_combinations, 
                f"Extraction completed: {len(results)} successful, {error_count} errors"
            )
        
        logger.success(f"Price extraction completed for {product_name}")
        logger.info(f"Success rate: {extraction_result['success_rate']:.1f}%")
        
        return extraction_result
    
    def _make_api_call(self, product_id: str, options_dict: Dict[str, str], attr_mappings: Dict[str, str]) -> Dict[str, Any]:
        """Make API call to get price for specific combination"""

        # Build payload with correct attribute mappings
        payload = {'product_id': product_id}

        for option_name, option_id in options_dict.items():
            attr_name = attr_mappings.get(option_name)
            if attr_name:
                payload[attr_name] = option_id
            else:
                # Try to guess attribute mapping if not found
                if 'quantity' in option_name.lower():
                    payload['attr5'] = option_id
                elif 'size' in option_name.lower():
                    payload['attr3'] = option_id
                elif 'paper' in option_name.lower():
                    payload['attr1'] = option_id
                elif 'page' in option_name.lower() or 'side' in option_name.lower():
                    payload['attr4'] = option_id
                elif 'bundling' in option_name.lower():
                    payload['attr400'] = option_id

        logger.debug(f"API Call Payload: {payload}")

        try:
            # Call computePrice endpoint
            price_url = f"{self.api_base_url}/computePrice?website_code=UP"
            response = self.session.post(
                price_url,
                json=payload,
                timeout=15
            )

            logger.debug(f"API Response Status: {response.status_code}")
            logger.debug(f"API Response: {response.text[:200]}")

            if response.status_code == 200:
                data = response.json()
                price = data.get('price', 'N/A')

                if price != 'N/A' and price != '20':  # Check for the $20 default issue
                    logger.info(f"✅ API Success: ${price} for combination {options_dict}")
                else:
                    logger.warning(f"⚠️ Suspicious price: ${price} for combination {options_dict}")

                return {
                    'success': True,
                    'price': price,
                    'total_price': data.get('total_price', 'N/A'),
                    'qty': data.get('qty', 'N/A'),
                    'turnaround': data.get('turnaround', 'N/A'),
                    'unit_price': data.get('unit_price', 'N/A'),
                    'payload': payload,
                    'full_response': data
                }
            else:
                error_msg = f'HTTP {response.status_code}: {response.text[:200]}'
                logger.error(f"❌ API Error: {error_msg}")
                return {
                    'success': False,
                    'error': error_msg,
                    'payload': payload
                }

        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Network Error: {e}")
            return {
                'success': False,
                'error': str(e),
                'payload': payload
            }
        except json.JSONDecodeError as e:
            logger.error(f"❌ JSON Error: {e}")
            return {
                'success': False,
                'error': f'JSON decode error: {e}',
                'payload': payload
            }
    
    def _create_formatted_csv(self, results: List[Dict], product_name: str, options: Dict[str, List]) -> Path:
        """Create formatted CSV with options as columns and quantities as rows"""
        
        if not results:
            return None
        
        # Create DataFrame
        df = pd.DataFrame(results)
        
        # Find quantity column (usually contains numbers)
        quantity_col = None
        for col in df.columns:
            if col.lower() in ['quantity', 'qty'] or 'quantity' in col.lower():
                quantity_col = col
                break
        
        if quantity_col:
            # Pivot table with quantities as rows and other options as columns
            option_cols = [col for col in df.columns if col not in [
                'combination_id', 'product_name', 'price', 'total_price', 
                'unit_price', 'qty_pieces', 'turnaround_days', 'timestamp', 'notes'
            ] and not col.endswith('_id') and col != quantity_col]
            
            # Create multi-level columns
            if len(option_cols) > 0:
                # Group by non-quantity options and create pivot
                grouped = df.groupby(option_cols + [quantity_col])['price'].first().unstack(quantity_col)
                
                # Clean up the result
                formatted_df = grouped.fillna('N/A')
                
                # Save formatted CSV
                safe_name = self._safe_filename(product_name)
                filename = f"{safe_name}_Formatted_Prices.csv"
                filepath = OUTPUT_DIR / filename
                
                formatted_df.to_csv(filepath)
                logger.info(f"Created formatted CSV: {filepath}")
                
                return filepath
        
        # Fallback: create simple formatted version
        return self._create_raw_csv(results, product_name)
    
    def _create_raw_csv(self, results: List[Dict], product_name: str) -> Path:
        """Create raw CSV with all data"""
        
        if not results:
            return None
        
        df = pd.DataFrame(results)
        
        # Save raw CSV
        safe_name = self._safe_filename(product_name)
        filename = f"{safe_name}_Raw_Prices.csv"
        filepath = OUTPUT_DIR / filename
        
        df.to_csv(filepath, index=False)
        logger.info(f"Created raw CSV: {filepath}")
        
        return filepath
    
    def _safe_filename(self, name: str) -> str:
        """Create safe filename from product name"""
        import re
        safe_name = re.sub(r'[^\w\s-]', '', name).strip()
        safe_name = re.sub(r'[-\s]+', '_', safe_name)
        return safe_name[:50]  # Limit length
