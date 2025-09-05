"""
Quantity Matrix Scraper - based on working js_scraper.py
For each combination of non-quantity options, iterate through all quantity options 
and create one CSV row with prices for each quantity.
"""
import csv
import itertools
import re
from typing import Optional
from playwright.sync_api import sync_playwright, TimeoutError

def handle_overlays(page):
    """Close popups and overlays."""
    try:
        cookie_button = page.locator('.btn.btn-primary:text("Accept All Cookies")')
        if cookie_button.is_visible():
            cookie_button.click(timeout=10000)
            print("✅ Cookie banner closed.")
    except TimeoutError:
        print("-> No cookie banner found.")
    except Exception:
        print("-> Cookie banner: unknown error.")

    try:
        close_button = page.locator('.email-subscribe-modal .close')
        if close_button.is_visible():
            close_button.click(timeout=10000)
            print("✅ Subscription pop-up closed.")
    except TimeoutError:
        print("-> No subscription pop-up found.")
    except Exception:
        print("-> Subscription pop-up: unknown error.")

def get_dropdown_info(page):
    """Get dropdown information using JavaScript."""
    js_code = """
    () => {
        const dropdowns = [];
        const calcAttrs = document.querySelectorAll('div.calc-attr');
        
        calcAttrs.forEach((attr, index) => {
            const button = attr.querySelector('button.dropdown-toggle');
            const label = attr.querySelector('label.calculator-label');
            const menu = attr.querySelector('ul.dropdown-menu');
            
            if (button && menu) {
                const labelText = label ? label.textContent.replace(':', '').trim() : `Dropdown ${index + 1}`;
                const options = menu.querySelectorAll('a.attr-value');
                
                // Check if this is a quantity dropdown
                const isQuantity = /quantity|qty|pieces|amount|count/i.test(labelText);
                
                dropdowns.push({
                    index: index,
                    label: labelText,
                    buttonElement: index,
                    optionCount: options.length,
                    isQuantity: isQuantity,
                    options: Array.from(options).map((opt, i) => ({
                        index: i,
                        text: opt.textContent.trim(),
                        value: opt.getAttribute('data-attribute-value') || opt.textContent.trim()
                    }))
                });
            }
        });
        
        return dropdowns;
    }
    """
    
    return page.evaluate(js_code)

def select_option_js(page, dropdown_index: int, option_index: int) -> bool:
    """Select option using JavaScript execution."""
    js_code = f"""
    () => {{
        try {{
            const calcAttrs = document.querySelectorAll('div.calc-attr');
            if ({dropdown_index} >= calcAttrs.length) return false;
            
            const attr = calcAttrs[{dropdown_index}];
            const button = attr.querySelector('button.dropdown-toggle');
            const menu = attr.querySelector('ul.dropdown-menu');
            
            if (!button || !menu) return false;
            
            // Open dropdown
            button.click();
            
            // Wait a bit for menu to appear
            setTimeout(() => {{
                const options = menu.querySelectorAll('a.attr-value');
                if ({option_index} >= options.length) return false;
                
                const option = options[{option_index}];
                option.click();
                
                // Close any remaining dropdowns
                document.addEventListener('click', (e) => {{
                    if (!e.target.closest('.dropdown')) {{
                        document.querySelectorAll('.dropdown-menu').forEach(m => m.style.display = 'none');
                    }}
                }});
                
            }}, 200);
            
            return true;
        }} catch (e) {{
            console.error('Selection error:', e);
            return false;
        }}
    }}
    """
    
    try:
        result = page.evaluate(js_code)
        page.wait_for_timeout(500)  # Wait for selection to process
        return result
    except Exception as e:
        print(f"   -> ⚠️ JS selection error: {e}")
        return False

def get_both_prices_js(page) -> tuple:
    """Extract both total price and per-unit price using JavaScript."""
    js_code = """
    () => {
        try {
            // Wait for loader to disappear
            const loader = document.querySelector('#compute_price_loader');
            if (loader && !loader.classList.contains('hidden')) {
                return { waiting: true };
            }
            
            let totalPrice = 'N/A';
            let perUnitPrice = 'N/A';
            
            // Get total price from #price element
            const priceElement = document.querySelector('#price');
            if (priceElement && priceElement.textContent) {
                const priceText = priceElement.textContent.trim();
                const match = priceText.match(/\\$\\s*([\\d,]+(?:\\.\\d{1,2})?)/);
                if (match) {
                    totalPrice = match[1].replace(/,/g, '');
                }
            }
            
            // Get per-item price from .calc-price-per-piece first
            const perPieceElement = document.querySelector('.calc-price-per-piece');
            if (perPieceElement && perPieceElement.textContent) {
                const perText = perPieceElement.textContent.trim();
                const match = perText.match(/\\$\\s*([\\d,]+(?:\\.\\d{1,2})?)/);
                if (match) {
                    perUnitPrice = match[1].replace(/,/g, '');
                }
            }
            
            // Fallback: calculate per-unit from total price and quantity
            if (totalPrice !== 'N/A' && perUnitPrice === 'N/A') {
                const buttons = document.querySelectorAll('button.dropdown-toggle');
                for (const btn of buttons) {
                    const text = btn.textContent.trim();
                    const qtyMatch = text.match(/^(\\d{1,3}(?:,\\d{3})*|\\d+)$/);
                    if (qtyMatch) {
                        const qty = parseInt(qtyMatch[1].replace(/,/g, ''));
                        if (qty > 0) {
                            const perUnit = parseFloat(totalPrice) / qty;
                            perUnitPrice = perUnit.toFixed(4);
                        }
                        break;
                    }
                }
            }
            
            return {
                total: totalPrice,
                perUnit: perUnitPrice,
                waiting: false
            };
        } catch (e) {
            console.error('Price extraction error:', e);
            return { total: 'ERROR', perUnit: 'ERROR', waiting: false };
        }
    }
    """
    
    # Try multiple times if waiting for loader
    for attempt in range(8):
        try:
            result = page.evaluate(js_code)
            
            if result.get('waiting'):
                print(f"   -> ⏳ Waiting for price calculation (attempt {attempt + 1}/8)...")
                page.wait_for_timeout(1000)
                continue
                
            total = result.get('total', 'N/A')
            per_unit = result.get('perUnit', 'N/A')
            return total, per_unit
            
        except Exception as e:
            print(f"   -> ⚠️ Price extraction attempt {attempt + 1} failed: {e}")
            if attempt < 7:
                page.wait_for_timeout(500)
    
    return "ERROR", "ERROR"

def scrape_quantity_matrix(url: str, max_combinations: Optional[int] = 10):
    """Create quantity matrix - one row per option combination with all quantity prices."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/114.0.0.0 Safari/537.36"
            )
        )
        page = context.new_page()
        
        # Block only heavy assets, keep CSS and JS
        page.route("**/*.{png,jpg,jpeg,gif,svg,webp,ico,woff,woff2,ttf,eot}", 
                  lambda route: route.abort())

        print(f"Navigating to page: {url}...")
        try:
            page.goto(url, timeout=120000, wait_until='domcontentloaded')
            page.wait_for_selector('#calculator_handler', state='visible', timeout=60000)
            print("✅ Page loaded.")
        except TimeoutError:
            print("❌ CRITICAL ERROR: Page did not load correctly. Exiting.")
            browser.close()
            return

        handle_overlays(page)
        page.wait_for_timeout(2000)  # Let page settle

        print("\\nDiscovering dropdowns using JavaScript...")
        dropdown_info = get_dropdown_info(page)
        
        if not dropdown_info:
            print("❌ ERROR: No dropdowns detected. Exiting.")
            browser.close()
            return

        # Separate quantity dropdown from other dropdowns
        quantity_dropdown = None
        other_dropdowns = []
        
        for info in dropdown_info:
            if info['isQuantity']:
                quantity_dropdown = info
                print(f"📊 Quantity dropdown: '{info['label']}' - {info['optionCount']} options")
                for opt in info['options']:
                    print(f"     {opt['index']}: {opt['text']}")
            else:
                other_dropdowns.append(info)
                print(f"🔧 Option dropdown: '{info['label']}' - {info['optionCount']} options")

        if not quantity_dropdown:
            print("❌ ERROR: No quantity dropdown found!")
            browser.close()
            return

        # Create CSV headers using actual dropdown labels
        option_headers = []
        for dropdown in other_dropdowns:
            # Clean up label for CSV header - make it Excel-friendly
            clean_label = dropdown['label'].replace(':', '').replace(' ', '_').replace('/', '_').strip()
            # Limit length for Excel compatibility
            if len(clean_label) > 20:
                clean_label = clean_label[:20]
            option_headers.append(clean_label)
        
        # Add quantity option headers from the actual dropdown (both total and per-unit)
        quantity_headers = []
        for opt in quantity_dropdown['options']:
            # Extract number from quantity text (e.g., "25" from "25 pieces")
            qty_match = re.search(r'(\\d+)', opt['text'])
            if qty_match:
                qty_num = qty_match.group(1)
                quantity_headers.append(f"qty_{qty_num}_total")
                quantity_headers.append(f"qty_{qty_num}_per_unit")
            else:
                quantity_headers.append(f"qty_{opt['index']}_total")
                quantity_headers.append(f"qty_{opt['index']}_per_unit")
        
        headers = option_headers + quantity_headers
        print(f"\\n📋 CSV headers ({len(headers)} total): {headers[:3]}... + {len(quantity_headers)} quantity columns")

        # Generate combinations of non-quantity options
        if other_dropdowns:
            option_counts = [info['optionCount'] for info in other_dropdowns]
            index_combos = itertools.product(*[range(count) for count in option_counts])
            index_combos = list(index_combos)
            
            # Process ALL combinations (no limit)
        else:
            index_combos = [()]  # Single empty combination if no other options

        print(f"\\n🎯 Will process {len(index_combos)} option combinations")

        # Create CSV file with proper Excel compatibility
        csv_filename = 'greeting_cards_printing.csv'
        
        with open(csv_filename, 'w', newline='', encoding='utf-8-sig') as csvfile:
            writer = csv.writer(csvfile, delimiter=',')  # Comma-separated for Excel
            writer.writerow(headers)

            processed = 0
            for combo in index_combos:
                processed += 1
                print(f"\\n=== Processing combination {processed}/{len(index_combos)}: {combo} ===")

                # Set the non-quantity options first
                combination_details = {}
                selection_success = True
                
                for dropdown_idx, option_idx in enumerate(combo):
                    dropdown = other_dropdowns[dropdown_idx]
                    option_text = dropdown['options'][option_idx]['text']
                    combination_details[dropdown['label']] = option_text
                    
                    print(f"   -> Setting {dropdown['label']}: {option_text}")
                    if not select_option_js(page, dropdown['index'], option_idx):
                        selection_success = False
                        print(f"   -> ❌ Failed to select {dropdown['label']}")
                        break
                    page.wait_for_timeout(300)

                if not selection_success:
                    print("❌ Skipping this combination due to selection failure")
                    continue

                # Now iterate through all quantity options for this combination
                quantity_prices = {}  # Will store tuples of (total, per_unit)
                
                for qty_opt in quantity_dropdown['options']:
                    qty_index = qty_opt['index']
                    qty_text = qty_opt['text']
                    
                    print(f"   -> Testing quantity: {qty_text}")
                    
                    if select_option_js(page, quantity_dropdown['index'], qty_index):
                        page.wait_for_timeout(800)  # Wait for price calculation
                        total_price, per_unit_price = get_both_prices_js(page)
                        quantity_prices[qty_index] = (total_price, per_unit_price)
                        print(f"      💰 Total: ${total_price} | Per-unit: ${per_unit_price}")
                    else:
                        quantity_prices[qty_index] = ('SELECTION_FAILED', 'SELECTION_FAILED')
                        print(f"      ❌ Failed to select quantity {qty_text}")

                # Build CSV row with actual dropdown values
                row_data = []
                
                # Add combination values in the same order as headers
                for dropdown in other_dropdowns:
                    value = combination_details.get(dropdown['label'], 'N/A')
                    row_data.append(value)
                
                # Add prices for each quantity option (both total and per-unit)
                for i in range(len(quantity_dropdown['options'])):
                    if i in quantity_prices:
                        total, per_unit = quantity_prices[i]
                        row_data.append(total)
                        row_data.append(per_unit)
                    else:
                        row_data.append('N/A')
                        row_data.append('N/A')
                
                writer.writerow(row_data)
                print(f"✅ Combination {processed} written to CSV with {len(quantity_prices)} quantity prices")

        browser.close()
        print(f"\\n✅ Quantity matrix complete! Data saved to poster_quantity_matrix.csv")
        print(f"📊 Processed {processed} combinations × {len(quantity_dropdown['options'])} quantities each")

if __name__ == "__main__":
    target_url = "https://www.uprinting.com/greeting-cards-printing.html"
    scrape_quantity_matrix(target_url)  # Process ALL combinations
