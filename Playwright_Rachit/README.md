# Matrix Scraper - Web Scraping Tool

A powerful web scraping tool that extracts pricing information from UPrinting product pages by testing all combinations of product options and quantities.

## 🚀 Quick Start Guide

### Prerequisites
- Python 3.7 or higher
- Internet connection

### Step 1: Install Dependencies

First, install the required Python packages:

```bash
pip install playwright
```

After installing Playwright, you need to install the browser binaries:

```bash
playwright install chromium
```

**Alternative Installation (if pip doesn't work):**
```bash
python -m pip install playwright
python -m playwright install chromium
```

### Step 2: Download the Script

Make sure you have the `matrix_scraper.py` file in your working directory.

### Step 3: Configure Your Scraping Target

Open `matrix_scraper.py` in any text editor and look for these two lines at the bottom of the file:

```python
if __name__ == "__main__":
    target_url = "https://www.uprinting.com/greeting-cards-printing.html"
    scrape_quantity_matrix(target_url)
```

**To change the product you want to scrape:**

1. **Change the URL:** Replace the URL with the product page you want to scrape
   ```python
   target_url = "https://www.uprinting.com/your-product-page.html"
   ```

2. **Change the output CSV filename:** Find this line in the script (around line 304):
   ```python
   csv_filename = 'greeting_cards_printing.csv'
   ```
   
   Change it to match your product:
   ```python
   csv_filename = 'your_product_name.csv'
   ```

### Step 4: Run the Scraper

Open your terminal/command prompt, navigate to the folder containing the script, and run:

```bash
python matrix_scraper.py
```

**If you get a "python not found" error, try:**
```bash
python3 matrix_scraper.py
```

## 📊 What the Script Does

1. **Opens the product page** in an automated browser
2. **Identifies all dropdown options** (size, color, material, etc.)
3. **Finds the quantity dropdown** automatically
4. **Tests every combination** of non-quantity options
5. **For each combination, tests all quantity options**
6. **Extracts both total price and per-unit price**
7. **Saves everything to a CSV file** with organized columns

## 📁 Output

The script creates a CSV file with:
- **Option columns:** One column for each product option (Size, Material, etc.)
- **Quantity columns:** Two columns for each quantity (Total Price and Per-Unit Price)

Example output structure:
```
Size, Material, Color, qty_25_total, qty_25_per_unit, qty_50_total, qty_50_per_unit, qty_100_total, qty_100_per_unit
Small, Glossy, Red, 15.99, 0.64, 25.99, 0.52, 45.99, 0.46
```

## 🛠️ Customization Options

### Change Browser Behavior

To run the browser in **headless mode** (invisible), change line 212:
```python
browser = p.chromium.launch(headless=True)  # Change False to True
```

### Limit Combinations (for testing)

If a product has too many option combinations, you can limit them by modifying the script around line 302:
```python
# Process only first 5 combinations for testing
index_combos = list(index_combos)[:5]  # Add this line
```

### Change Wait Times

If the script is too fast/slow for a website, adjust wait times:
- Line 113: `page.wait_for_timeout(500)` - Time after selecting options
- Line 346: `page.wait_for_timeout(800)` - Time to wait for price calculation

## 🚨 Troubleshooting

### "No dropdowns detected" Error
- Make sure the URL is correct and the page loads properly
- The script looks for dropdowns with class `calc-attr`
- Try running with `headless=False` to see what's happening

### "No quantity dropdown found" Error
- The script automatically detects quantity dropdowns by looking for keywords like "quantity", "qty", "pieces"
- If it doesn't detect correctly, the dropdown might have an unusual label

### "Page did not load correctly" Error
- Check your internet connection
- The website might be down or blocking automated requests
- Try increasing the timeout on line 226: `timeout=120000` (increase the number)

### Prices show as "N/A" or "ERROR"
- The website might be slow to calculate prices
- Increase wait time on line 346: `page.wait_for_timeout(1000)` (increase from 800)
- The price selectors might have changed on the website

## 📝 Example: Scraping a Different Product

Let's say you want to scrape business cards instead of greeting cards:

1. **Find the product URL:**
   ```
   https://www.uprinting.com/business-cards.html
   ```

2. **Update the script:**
   ```python
   # Change this line:
   target_url = "https://www.uprinting.com/business-cards.html"
   
   # And this line:
   csv_filename = 'business_cards_pricing.csv'
   ```

3. **Run the script:**
   ```bash
   python matrix_scraper.py
   ```

4. **Check your results** in `business_cards_pricing.csv`

## ⚡ Tips for First-Time Users

1. **Test with a simple product first** - Choose a product with few options to make sure everything works
2. **Keep the browser visible** - Don't use headless mode when testing (keep `headless=False`)
3. **Check the CSV file** - Open it in Excel or Google Sheets to see the results
4. **Be patient** - The script needs to test many combinations, so it might take several minutes
5. **One product at a time** - Don't try to scrape multiple products simultaneously

## 📞 Support

If you encounter issues:
1. Make sure all prerequisites are installed correctly
2. Check that the website URL is accessible in your regular browser
3. Try running with fewer combinations first (see Customization section)
4. Look at the console output for specific error messages

---

**Happy Scraping!** 🎉
