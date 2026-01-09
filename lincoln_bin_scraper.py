from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import time

def scrape_lincoln_bins(postcode_or_street):
    print(f"--- Starting Scraper for: {postcode_or_street} ---")
    
    # Setup Chrome options (Headless = runs in background without opening window)
    options = webdriver.ChromeOptions()
    options.add_argument("--headless") # Enabled for web app use
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    # Initialize the "Robot" Browser
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    
    bin_data = [] # List to store results

    try:
        # 1. Go to the Lincoln Council Bin Page
        url = "https://www.lincoln.gov.uk/online/view-bin-collection-days"
        print(f"Loading {url}...")
        driver.get(url)

        # 2. Switch to the Form Iframe
        # The form lives inside a frame, we must 'step inside' it to see the buttons
        wait = WebDriverWait(driver, 15)
        iframe = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "iframe.achieveforms-iframe")))
        driver.switch_to.frame(iframe)
        print("Found the form...")

        # 3. Find the Address Input and Type
        # Firmstep forms often have complex IDs, so we look for the input field generically
        search_input = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "input[type='text']")))
        search_input.clear()
        search_input.send_keys(postcode_or_street)
        print("Entered address...")

        # 4. Click the 'Find address' Button
        # We look for a button that contains the text 'Find address'
        search_btn = driver.find_element(By.XPATH, "//button[contains(., 'Find address')]")
        search_btn.click()
        print("Searching...")

        # 5. Handle the Dropdown Selection
        # Wait for the dropdown to appear after searching
        dropdown = wait.until(EC.element_to_be_clickable((By.TAG_NAME, "select")))
        # Just select the first option for now (Index 1 usually, as 0 is 'Please select')
        # In a real app, you might match the specific house number
        from selenium.webdriver.support.ui import Select
        select = Select(dropdown)
        if len(select.options) > 1:
            select.select_by_index(1) 
            print(f"Selected address: {select.options[1].text}")
        else:
            print("No address results found.")
            return [] # Return empty list if no address found

        # 6. Extract the Bin Dates
        # We wait for the "Black (Refuse)" text to verify results are loaded
        wait.until(EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'Black (Refuse)')]")))
        print("\n--- SCHEDULE FOUND ---\n")

        # Find all info blocks
        page_text = driver.find_element(By.TAG_NAME, "body").text
        lines = page_text.split('\n')
        
        # Simple parser to grab bin name and date
        for i, line in enumerate(lines):
            if "Next Collections" in line:
                # The line before usually contains the Bin Name logic (simplified)
                # We look backwards for the bin name, or just grab the previous line if it looks like a header
                bin_name = lines[i-1] if i > 0 else "Unknown Bin"
                collection_info = line.replace("Next Collections:", "").strip()
                
                bin_data.append({
                    "name": bin_name,
                    "info": collection_info
                })

    except Exception as e:
        print(f"Error occurred: {e}")
        # Save a screenshot if it fails so you can see why
        driver.save_screenshot("error_screenshot.png")
    
    finally:
        print("\nClosing browser...")
        driver.quit()
        
    return bin_data

if __name__ == "__main__":
    # You can change this to your actual postcode
    my_address = "LN6 7RB" 
    results = scrape_lincoln_bins(my_address)
    print(results)