#!/usr/bin/env python3
"""
Web Interface Module
===================

Flask-based web interface for the UPrinting Automation Framework.

Author: AI Assistant
Date: 2025-08-30
"""

import json
import pandas as pd
from flask import Flask, render_template, request, jsonify, send_file
from flask_cors import CORS
from flask_socketio import SocketIO, emit
from pathlib import Path
import threading
import time
from datetime import datetime

from config import config, OUTPUT_DIR
from product_analyzer import ProductAnalyzer
from price_extractor import PriceExtractor
from loguru import logger

app = Flask(__name__)
app.config['SECRET_KEY'] = 'uprinting_automation_secret_key'
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# Global state
current_analysis = None
current_extraction = None
current_extractor = None
progress_data = {
    'current_step': 'idle',
    'progress': 0,
    'total': 0,
    'message': 'Ready',
    'errors': [],
    'is_paused': False
}

@app.route('/')
def index():
    """Main dashboard"""
    return render_template('index.html')

@app.route('/api/products')
def get_products():
    """Get list of products from CSV"""
    try:
        df = pd.read_csv(config.products_csv_path)
        products = df.to_dict('records')
        return jsonify({
            'success': True,
            'products': products,
            'total': len(products)
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/api/products/search')
def search_products():
    """Search products by name"""
    try:
        query = request.args.get('q', '').lower()
        if not query:
            return get_products()

        df = pd.read_csv(config.products_csv_path)

        # Filter products that match the search query
        filtered_df = df[df['Product Name'].str.lower().str.contains(query, na=False)]
        products = filtered_df.to_dict('records')

        return jsonify({
            'success': True,
            'products': products,
            'total': len(products),
            'query': query
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/api/analyze/<int:product_index>')
def analyze_product(product_index):
    """Analyze a specific product"""
    try:
        df = pd.read_csv(config.products_csv_path)
        
        if product_index >= len(df):
            return jsonify({
                'success': False,
                'error': 'Product index out of range'
            })
        
        product = df.iloc[product_index]
        product_name = product['Product Name']
        product_url = product['URL']
        
        # Start analysis in background
        def run_analysis():
            global current_analysis, progress_data
            
            progress_data.update({
                'current_step': 'analyzing',
                'progress': 0,
                'total': 1,
                'message': f'Analyzing {product_name}...'
            })
            socketio.emit('progress_update', progress_data)
            
            analyzer = ProductAnalyzer()
            result = analyzer.analyze_product(product_url, product_name)
            
            current_analysis = result
            
            progress_data.update({
                'current_step': 'completed',
                'progress': 1,
                'total': 1,
                'message': 'Analysis completed'
            })
            socketio.emit('analysis_complete', result)
            socketio.emit('progress_update', progress_data)
        
        thread = threading.Thread(target=run_analysis)
        thread.start()
        
        return jsonify({
            'success': True,
            'message': 'Analysis started'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/api/analysis/current')
def get_current_analysis():
    """Get current analysis result"""
    global current_analysis
    
    if current_analysis:
        return jsonify({
            'success': True,
            'analysis': current_analysis
        })
    else:
        return jsonify({
            'success': False,
            'error': 'No analysis available'
        })

@app.route('/api/analysis/update', methods=['POST'])
def update_analysis():
    """Update analysis with user modifications"""
    global current_analysis

    try:
        data = request.get_json()

        if not current_analysis:
            return jsonify({
                'success': False,
                'error': 'No analysis to update'
            })

        # Update options
        if 'options' in data:
            current_analysis['options'] = data['options']

        # Update attribute mappings
        if 'attribute_mappings' in data:
            current_analysis['attribute_mappings'] = data['attribute_mappings']

        # Recalculate combinations
        total_combinations = 1
        for option_list in current_analysis['options'].values():
            if option_list:
                total_combinations *= len(option_list)

        current_analysis['total_combinations'] = total_combinations
        current_analysis['user_modified'] = True
        current_analysis['modification_timestamp'] = time.time()

        return jsonify({
            'success': True,
            'analysis': current_analysis
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/api/analysis/add_option', methods=['POST'])
def add_manual_option():
    """Add a manual option to the analysis"""
    global current_analysis

    try:
        data = request.get_json()

        if not current_analysis:
            return jsonify({
                'success': False,
                'error': 'No analysis available'
            })

        option_name = data.get('option_name')
        option_values = data.get('option_values', [])
        attribute_mapping = data.get('attribute_mapping')

        if not option_name or not option_values:
            return jsonify({
                'success': False,
                'error': 'Option name and values are required'
            })

        # Try to find IDs for the option values
        analyzer = ProductAnalyzer()
        found_ids = analyzer.find_option_ids(
            current_analysis['product_url'],
            option_name,
            option_values
        )

        # Create option entries
        option_entries = []
        for value in option_values:
            option_entries.append({
                'id': found_ids.get(value, f'manual_{len(option_entries)}'),
                'text': value
            })

        # Add to analysis
        current_analysis['options'][option_name] = option_entries

        if attribute_mapping:
            current_analysis['attribute_mappings'][option_name] = attribute_mapping

        # Recalculate combinations
        total_combinations = 1
        for option_list in current_analysis['options'].values():
            if option_list:
                total_combinations *= len(option_list)

        current_analysis['total_combinations'] = total_combinations
        current_analysis['user_modified'] = True
        current_analysis['modification_timestamp'] = time.time()

        return jsonify({
            'success': True,
            'analysis': current_analysis,
            'found_ids': found_ids
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/api/analysis/add_suboption', methods=['POST'])
def add_manual_suboption():
    """Add a manual sub-option to an existing option"""
    global current_analysis

    try:
        data = request.get_json()

        if not current_analysis:
            return jsonify({
                'success': False,
                'error': 'No analysis available'
            })

        option_name = data.get('option_name')
        suboption_value = data.get('suboption_value')

        if not option_name or not suboption_value:
            return jsonify({
                'success': False,
                'error': 'Option name and sub-option value are required'
            })

        if option_name not in current_analysis['options']:
            return jsonify({
                'success': False,
                'error': f'Option "{option_name}" not found'
            })

        # Try to find ID for the sub-option value
        analyzer = ProductAnalyzer()
        found_ids = analyzer.find_option_ids(
            current_analysis['product_url'],
            option_name,
            [suboption_value]
        )

        # Add sub-option
        new_suboption = {
            'id': found_ids.get(suboption_value, f'manual_{len(current_analysis["options"][option_name])}'),
            'text': suboption_value
        }

        current_analysis['options'][option_name].append(new_suboption)

        # Recalculate combinations
        total_combinations = 1
        for option_list in current_analysis['options'].values():
            if option_list:
                total_combinations *= len(option_list)

        current_analysis['total_combinations'] = total_combinations
        current_analysis['user_modified'] = True
        current_analysis['modification_timestamp'] = time.time()

        return jsonify({
            'success': True,
            'analysis': current_analysis,
            'found_id': found_ids.get(suboption_value)
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/api/extract/start', methods=['POST'])
def start_extraction():
    """Start price extraction for current analysis"""
    global current_analysis, current_extraction, current_extractor

    try:
        if not current_analysis:
            return jsonify({
                'success': False,
                'error': 'No analysis available for extraction'
            })

        data = request.get_json()
        options_to_exclude = data.get('exclude_options', [])
        suboptions_to_exclude = data.get('exclude_suboptions', {})

        # Start extraction in background
        def run_extraction():
            global current_extraction, current_extractor, progress_data

            progress_data.update({
                'current_step': 'extracting',
                'progress': 0,
                'total': current_analysis['total_combinations'],
                'message': 'Starting price extraction...',
                'is_paused': False
            })
            socketio.emit('progress_update', progress_data)

            current_extractor = PriceExtractor()

            # Set up progress callback
            def progress_callback(current, total, message):
                progress_data.update({
                    'progress': current,
                    'total': total,
                    'message': message,
                    'is_paused': current_extractor.is_paused if current_extractor else False
                })
                socketio.emit('progress_update', progress_data)

            result = current_extractor.extract_all_prices(
                current_analysis,
                exclude_options=options_to_exclude,
                suboptions_to_exclude=suboptions_to_exclude,
                progress_callback=progress_callback
            )

            current_extraction = result

            progress_data.update({
                'current_step': 'completed',
                'progress': result.get('total_extracted', 0),
                'total': result.get('total_combinations', 0),
                'message': 'Extraction completed',
                'is_paused': False
            })
            socketio.emit('extraction_complete', result)
            socketio.emit('progress_update', progress_data)

        thread = threading.Thread(target=run_extraction)
        thread.start()

        return jsonify({
            'success': True,
            'message': 'Extraction started'
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/api/extract/pause', methods=['POST'])
def pause_extraction():
    """Pause the current extraction"""
    global current_extractor, progress_data

    try:
        if current_extractor:
            current_extractor.pause_extraction()
            progress_data['is_paused'] = True
            socketio.emit('progress_update', progress_data)
            return jsonify({
                'success': True,
                'message': 'Extraction paused'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'No active extraction to pause'
            })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/api/extract/resume', methods=['POST'])
def resume_extraction():
    """Resume the paused extraction"""
    global current_extractor, progress_data

    try:
        if current_extractor:
            current_extractor.resume_extraction()
            progress_data['is_paused'] = False
            socketio.emit('progress_update', progress_data)
            return jsonify({
                'success': True,
                'message': 'Extraction resumed'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'No active extraction to resume'
            })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/api/extraction/current')
def get_current_extraction():
    """Get current extraction result"""
    global current_extraction
    
    if current_extraction:
        return jsonify({
            'success': True,
            'extraction': current_extraction
        })
    else:
        return jsonify({
            'success': False,
            'error': 'No extraction available'
        })

@app.route('/api/download/<filename>')
def download_file(filename):
    """Download generated CSV file"""
    try:
        filepath = OUTPUT_DIR / filename
        
        if not filepath.exists():
            return jsonify({
                'success': False,
                'error': 'File not found'
            })
        
        return send_file(
            filepath,
            as_attachment=True,
            download_name=filename
        )
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/api/progress')
def get_progress():
    """Get current progress status"""
    return jsonify(progress_data)

@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    emit('progress_update', progress_data)
    logger.info('Client connected to WebSocket')

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    logger.info('Client disconnected from WebSocket')

def run_web_interface():
    """Run the web interface"""
    logger.info(f"Starting web interface on {config.web_host}:{config.web_port}")
    
    socketio.run(
        app,
        host=config.web_host,
        port=config.web_port,
        debug=config.debug_mode
    )

if __name__ == '__main__':
    run_web_interface()
