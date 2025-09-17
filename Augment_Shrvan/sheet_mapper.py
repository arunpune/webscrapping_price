#!/usr/bin/env python3
"""
Sheet Mapper Module
==================

Intelligent mapping between extracted CSV data and user-provided Excel/CSV sheets.
Handles different naming conventions and formats.

Author: AI Assistant
Date: 2025-08-30
"""

import pandas as pd
import numpy as np
import re
import json
from typing import Dict, List, Tuple, Optional, Any
from pathlib import Path
from loguru import logger
from difflib import SequenceMatcher
import google.generativeai as genai
from config import config

class SheetMapper:
    """Intelligent mapper for CSV and Excel sheets"""
    
    def __init__(self):
        self.similarity_threshold = 0.6
        self.manual_mappings = {}

        # Initialize Gemini AI
        try:
            genai.configure(api_key=config.gemini_api_key)
            self.model = genai.GenerativeModel('gemini-1.5-flash')
            self.ai_enabled = True
            logger.info("Gemini AI initialized for intelligent mapping")
        except Exception as e:
            logger.warning(f"Gemini AI not available: {e}")
            self.ai_enabled = False
        
    def analyze_sheets(self, extracted_csv_path: str, target_sheet_path: str) -> Dict[str, Any]:
        """Analyze both sheets and suggest mappings"""
        
        logger.info(f"Analyzing sheets: {extracted_csv_path} and {target_sheet_path}")
        
        try:
            # Load extracted CSV data
            df_extracted = pd.read_csv(extracted_csv_path)
            
            # Load target sheet (Excel or CSV) with smart header detection
            if target_sheet_path.endswith('.xlsx') or target_sheet_path.endswith('.xls'):
                df_target = self._load_excel_with_smart_headers(target_sheet_path)
            else:
                df_target = self._load_csv_with_smart_headers(target_sheet_path)
            
            logger.info(f"Extracted CSV shape: {df_extracted.shape}")
            logger.info(f"Target sheet shape: {df_target.shape}")
            
            # Analyze structure
            extracted_analysis = self._analyze_sheet_structure(df_extracted, "extracted")
            target_analysis = self._analyze_sheet_structure(df_target, "target")
            
            # Create intelligent mappings using AI if available
            if self.ai_enabled:
                option_mappings = self._create_ai_option_mappings(extracted_analysis, target_analysis)
                quantity_mappings = self._create_ai_quantity_mappings(extracted_analysis, target_analysis)
            else:
                option_mappings = self._create_option_mappings(extracted_analysis, target_analysis)
                quantity_mappings = self._create_quantity_mappings(extracted_analysis, target_analysis)
            
            return {
                'extracted_analysis': extracted_analysis,
                'target_analysis': target_analysis,
                'option_mappings': option_mappings,
                'quantity_mappings': quantity_mappings,
                'mapping_confidence': self._calculate_confidence(option_mappings, quantity_mappings)
            }
            
        except Exception as e:
            logger.error(f"Error analyzing sheets: {e}")
            return {'error': str(e)}

    def _load_excel_with_smart_headers(self, file_path: str) -> pd.DataFrame:
        """Load Excel file with smart header detection"""

        logger.info(f"Loading Excel file with smart header detection: {file_path}")

        # Try different header rows (0, 1, 2)
        for header_row in [0, 1, 2]:
            try:
                df = pd.read_excel(file_path, header=header_row)

                # Check if this looks like a valid header row
                if self._is_valid_header_row(df):
                    logger.info(f"Found valid headers at row {header_row}")
                    return df

            except Exception as e:
                logger.debug(f"Failed to read with header row {header_row}: {e}")
                continue

        # Fallback to default
        logger.warning("Could not detect headers, using default (row 0)")
        return pd.read_excel(file_path, header=0)

    def _load_csv_with_smart_headers(self, file_path: str) -> pd.DataFrame:
        """Load CSV file with smart header detection"""

        logger.info(f"Loading CSV file with smart header detection: {file_path}")

        # Try different header rows (0, 1, 2)
        for header_row in [0, 1, 2]:
            try:
                df = pd.read_csv(file_path, header=header_row)

                # Check if this looks like a valid header row
                if self._is_valid_header_row(df):
                    logger.info(f"Found valid headers at row {header_row}")
                    return df

            except Exception as e:
                logger.debug(f"Failed to read with header row {header_row}: {e}")
                continue

        # Fallback to default
        logger.warning("Could not detect headers, using default (row 0)")
        return pd.read_csv(file_path, header=0)

    def _is_valid_header_row(self, df: pd.DataFrame) -> bool:
        """Check if the current header row looks valid"""

        if df.empty:
            return False

        # Check for unnamed columns (indicates wrong header row)
        unnamed_count = sum(1 for col in df.columns if str(col).startswith('Unnamed:'))
        unnamed_ratio = unnamed_count / len(df.columns)

        # If more than 50% columns are unnamed, probably wrong header row
        if unnamed_ratio > 0.5:
            logger.debug(f"Too many unnamed columns ({unnamed_ratio:.1%}), trying next row")
            return False

        # Check for numeric-only column names (might indicate data row used as header)
        numeric_count = sum(1 for col in df.columns if str(col).replace('.', '').replace('-', '').isdigit())
        numeric_ratio = numeric_count / len(df.columns)

        # If more than 70% columns are numeric, probably data row
        if numeric_ratio > 0.7:
            logger.debug(f"Too many numeric column names ({numeric_ratio:.1%}), trying next row")
            return False

        # Check for meaningful text in column names
        text_columns = sum(1 for col in df.columns if len(str(col).strip()) > 2 and not str(col).startswith('Unnamed:'))
        text_ratio = text_columns / len(df.columns)

        # Need at least 30% meaningful text columns
        if text_ratio < 0.3:
            logger.debug(f"Not enough meaningful column names ({text_ratio:.1%}), trying next row")
            return False

        logger.debug(f"Header validation: unnamed={unnamed_ratio:.1%}, numeric={numeric_ratio:.1%}, text={text_ratio:.1%}")
        return True
    
    def _analyze_sheet_structure(self, df: pd.DataFrame, sheet_type: str) -> Dict[str, Any]:
        """Analyze the structure of a sheet"""
        
        analysis = {
            'columns': list(df.columns),
            'shape': df.shape,
            'option_columns': [],
            'quantity_columns': [],
            'price_columns': [],
            'sample_data': {}
        }
        
        for col in df.columns:
            col_data = df[col].dropna()
            
            # Sample data for each column
            analysis['sample_data'][col] = col_data.head(5).tolist()
            
            # Classify column type
            if self._is_option_column(col, col_data):
                analysis['option_columns'].append(col)
            elif self._is_quantity_column(col, col_data):
                analysis['quantity_columns'].append(col)
            elif self._is_price_column(col, col_data):
                analysis['price_columns'].append(col)
        
        logger.info(f"{sheet_type} analysis: {len(analysis['option_columns'])} options, "
                   f"{len(analysis['quantity_columns'])} quantities, {len(analysis['price_columns'])} prices")
        
        return analysis
    
    def _is_option_column(self, col_name: str, col_data: pd.Series) -> bool:
        """Determine if a column contains option data"""
        
        # Check column name patterns
        option_keywords = ['paper', 'size', 'format', 'page', 'binding', 'bundling', 'material', 'finish']
        if any(keyword in col_name.lower() for keyword in option_keywords):
            return True
        
        # Check data patterns
        if col_data.dtype == 'object':
            unique_values = col_data.unique()
            if len(unique_values) < len(col_data) * 0.5:  # Less than 50% unique values
                return True
        
        return False
    
    def _is_quantity_column(self, col_name: str, col_data: pd.Series) -> bool:
        """Determine if a column contains quantity data"""
        
        # Check column name patterns
        if 'quantity' in col_name.lower() or col_name.isdigit():
            return True
        
        # Check if column name is a number
        try:
            int(col_name)
            return True
        except ValueError:
            pass
        
        # Check header row for quantity values
        if col_data.dtype in ['int64', 'float64']:
            return True
        
        return False
    
    def _is_price_column(self, col_name: str, col_data: pd.Series) -> bool:
        """Determine if a column contains price data"""
        
        if 'price' in col_name.lower():
            return True
        
        # Check for currency symbols or price patterns
        if col_data.dtype == 'object':
            sample_values = col_data.dropna().head(10)
            price_pattern = re.compile(r'[\$£€]?\d+\.?\d*')
            if any(price_pattern.match(str(val)) for val in sample_values):
                return True
        
        return False
    
    def _create_option_mappings(self, extracted_analysis: Dict, target_analysis: Dict) -> Dict[str, Dict]:
        """Create mappings between option columns"""
        
        mappings = {}
        
        extracted_options = extracted_analysis['option_columns']
        target_options = target_analysis['option_columns']
        
        for extracted_col in extracted_options:
            best_match = None
            best_score = 0
            
            for target_col in target_options:
                # Calculate similarity score
                score = self._calculate_column_similarity(
                    extracted_col, target_col,
                    extracted_analysis['sample_data'][extracted_col],
                    target_analysis['sample_data'][target_col]
                )
                
                if score > best_score and score > self.similarity_threshold:
                    best_score = score
                    best_match = target_col
            
            if best_match:
                mappings[extracted_col] = {
                    'target_column': best_match,
                    'confidence': best_score,
                    'value_mappings': self._create_value_mappings(
                        extracted_analysis['sample_data'][extracted_col],
                        target_analysis['sample_data'][best_match]
                    )
                }
        
        return mappings

    def _create_ai_option_mappings(self, extracted_analysis: Dict, target_analysis: Dict) -> Dict[str, Dict]:
        """Create option mappings using Gemini AI"""

        if not self.ai_enabled:
            return self._create_option_mappings(extracted_analysis, target_analysis)

        try:
            # Prepare data for AI analysis
            extracted_columns = extracted_analysis['option_columns']
            target_columns = target_analysis['option_columns']

            # Get sample data for context
            extracted_samples = {col: extracted_analysis['sample_data'][col][:3] for col in extracted_columns}
            target_samples = {col: target_analysis['sample_data'][col][:3] for col in target_columns}

            prompt = f"""
            You are an expert data mapper. I need to map columns between two datasets for a printing company.

            EXTRACTED DATA COLUMNS (from price scraping):
            {json.dumps(extracted_samples, indent=2)}

            TARGET SHEET COLUMNS (user's sheet to populate):
            {json.dumps(target_samples, indent=2)}

            Please analyze and create mappings between these columns. Consider:
            1. Similar meanings (e.g., "Paper Type" matches "Material")
            2. Similar values (e.g., "Glossy", "Matte" values)
            3. Printing industry terminology

            Return ONLY a JSON object with this structure:
            {{
                "extracted_column_name": {{
                    "target_column": "target_column_name",
                    "confidence": 0.95,
                    "reason": "explanation"
                }}
            }}

            Only include mappings with confidence > 0.7.
            """

            response = self.model.generate_content(prompt)
            ai_mappings = json.loads(response.text.strip())

            # Convert AI response to our format
            mappings = {}
            for extracted_col, mapping_info in ai_mappings.items():
                if mapping_info['confidence'] > 0.7:
                    mappings[extracted_col] = {
                        'target_column': mapping_info['target_column'],
                        'confidence': mapping_info['confidence'],
                        'value_mappings': self._create_value_mappings(
                            extracted_analysis['sample_data'][extracted_col],
                            target_analysis['sample_data'][mapping_info['target_column']]
                        )
                    }
                    logger.info(f"AI mapped: {extracted_col} → {mapping_info['target_column']} ({mapping_info['confidence']:.1%})")

            return mappings

        except Exception as e:
            logger.warning(f"AI mapping failed, falling back to traditional method: {e}")
            return self._create_option_mappings(extracted_analysis, target_analysis)

    def _create_quantity_mappings(self, extracted_analysis: Dict, target_analysis: Dict) -> Dict[str, str]:
        """Create mappings between quantity columns"""
        
        mappings = {}
        
        extracted_quantities = extracted_analysis['quantity_columns']
        target_quantities = target_analysis['quantity_columns']
        
        for extracted_col in extracted_quantities:
            # Try to find matching quantity in target
            extracted_qty = self._extract_quantity_from_column(extracted_col)
            
            for target_col in target_quantities:
                target_qty = self._extract_quantity_from_column(target_col)
                
                if extracted_qty and target_qty and extracted_qty == target_qty:
                    mappings[extracted_col] = target_col
                    break
        
        return mappings
    
    def _calculate_column_similarity(self, col1: str, col2: str, data1: List, data2: List) -> float:
        """Calculate similarity between two columns"""
        
        # Name similarity
        name_similarity = SequenceMatcher(None, col1.lower(), col2.lower()).ratio()
        
        # Data similarity
        data_similarity = 0
        if data1 and data2:
            common_values = set(str(v).lower() for v in data1) & set(str(v).lower() for v in data2)
            total_values = set(str(v).lower() for v in data1) | set(str(v).lower() for v in data2)
            data_similarity = len(common_values) / len(total_values) if total_values else 0
        
        # Combined score
        return (name_similarity * 0.4) + (data_similarity * 0.6)
    
    def _create_value_mappings(self, extracted_values: List, target_values: List) -> Dict[str, str]:
        """Create mappings between individual values"""
        
        mappings = {}
        
        for extracted_val in extracted_values:
            best_match = None
            best_score = 0
            
            for target_val in target_values:
                score = SequenceMatcher(None, str(extracted_val).lower(), str(target_val).lower()).ratio()
                
                if score > best_score and score > 0.7:
                    best_score = score
                    best_match = target_val
            
            if best_match:
                mappings[str(extracted_val)] = str(best_match)
        
        return mappings
    
    def _extract_quantity_from_column(self, col_name: str) -> Optional[int]:
        """Extract quantity number from column name"""
        
        # Try direct conversion
        try:
            return int(col_name)
        except ValueError:
            pass
        
        # Extract numbers from string
        numbers = re.findall(r'\d+', col_name)
        if numbers:
            return int(numbers[0])
        
        return None
    
    def _calculate_confidence(self, option_mappings: Dict, quantity_mappings: Dict) -> float:
        """Calculate overall mapping confidence"""
        
        if not option_mappings and not quantity_mappings:
            return 0.0
        
        total_confidence = 0
        total_mappings = 0
        
        for mapping in option_mappings.values():
            total_confidence += mapping['confidence']
            total_mappings += 1
        
        # Quantity mappings get full confidence if found
        total_confidence += len(quantity_mappings) * 1.0
        total_mappings += len(quantity_mappings)
        
        return total_confidence / total_mappings if total_mappings > 0 else 0.0
    
    def apply_mappings(self, extracted_csv_path: str, target_sheet_path: str, 
                      mappings: Dict[str, Any], manual_mappings: Dict[str, str] = None) -> pd.DataFrame:
        """Apply mappings and populate target sheet with prices"""
        
        logger.info("Applying mappings to populate target sheet")
        
        try:
            # Load data
            df_extracted = pd.read_csv(extracted_csv_path)
            
            if target_sheet_path.endswith('.xlsx') or target_sheet_path.endswith('.xls'):
                df_target = self._load_excel_with_smart_headers(target_sheet_path)
            else:
                df_target = self._load_csv_with_smart_headers(target_sheet_path)
            
            # Apply manual mappings if provided
            if manual_mappings:
                mappings['option_mappings'].update(manual_mappings)
            
            # Create result dataframe
            df_result = df_target.copy()
            
            # Populate prices
            populated_count = 0
            
            for target_idx, target_row in df_target.iterrows():
                # Build filter for extracted data
                filters = {}
                
                for extracted_col, mapping in mappings['option_mappings'].items():
                    target_col = mapping['target_column']
                    target_value = target_row[target_col]
                    
                    # Find corresponding extracted value
                    value_mappings = mapping['value_mappings']
                    extracted_value = None
                    
                    for ext_val, tgt_val in value_mappings.items():
                        if str(tgt_val).lower() == str(target_value).lower():
                            extracted_value = ext_val
                            break
                    
                    if extracted_value:
                        filters[extracted_col] = extracted_value
                
                # Find matching row in extracted data
                extracted_match = df_extracted
                for filter_col, filter_val in filters.items():
                    extracted_match = extracted_match[extracted_match[filter_col] == filter_val]
                
                if len(extracted_match) > 0:
                    # Populate quantity columns with prices
                    for extracted_qty_col, target_qty_col in mappings['quantity_mappings'].items():
                        if target_qty_col in df_result.columns:
                            qty_match = extracted_match[extracted_match['quantity'] == extracted_qty_col]
                            if len(qty_match) > 0:
                                price = qty_match.iloc[0]['price']
                                df_result.at[target_idx, target_qty_col] = price
                                populated_count += 1
            
            logger.success(f"Populated {populated_count} price cells")
            return df_result
            
        except Exception as e:
            logger.error(f"Error applying mappings: {e}")
            raise
