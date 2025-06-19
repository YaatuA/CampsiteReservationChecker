import time
import requests
import os
from dotenv import load_dotenv

# --- SELENIUM IMPORTS ---
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from webdriver_manager.chrome import ChromeDriverManager

# --- CONFIGURATION ---
load_dotenv()
TARGET_URL = os.getenv("TARGET_URL")
PUSHOVER_API_TOKEN = os.getenv("PUSHOVER_API_TOKEN")
PUSHOVER_USER_KEY = os.getenv("PUSHOVER_USER_KEY")

# --- SCRIPT SETTINGS ---
CHECK_INTERVAL_SECONDS = 5
MAX_CONSECUTIVE_FAILURES = 3
HEADLESS_MODE = True

# --- ROBUST LOCATORS ---
PAGE_LOAD_CONFIRMATION_ID = "arrival-date-field" # The ID of the main search form
LIST_VIEW_BUTTON_ID = "list-view-button-button"        # The unique ID of the 'List' button
NO_SITES_MESSAGE_XPATH = "//h2[contains(text(), 'No Available Sites')]" # A content-based XPath


def send_pushover_notification(message, title="Campsite Available!"):
    """Sends a notification to your device via the Pushover service."""
    if not PUSHOVER_API_TOKEN or not PUSHOVER_USER_KEY:
        print("Pushover credentials are not set. Skipping notification.")
        return
    try:
        payload = {
            "token": PUSHOVER_API_TOKEN, "user": PUSHOVER_USER_KEY,
            "message": message, "title": title, "priority": 1
        }
        if "book it now" in message:
            payload["url"], payload["url_title"] = TARGET_URL, "Book Now!"
        requests.post("https://api.pushover.net/1/messages.json", data=payload, timeout=10)
        print("Notification sent successfully!")
    except requests.RequestException as e:
        print(f"An error occurred while sending the Pushover notification: {e}")


def check_availability():
    """Main function to check for site availability using robust Selenium locators."""
    if not TARGET_URL:
        print("TARGET_URL is not set in the .env file. Cannot proceed.")
        return 'FAILURE'

    # --- SELENIUM BROWSER SETUP ---
    options = webdriver.ChromeOptions()
    # These arguments are crucial for running in a container like Render
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument(f'user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36')
    if HEADLESS_MODE:
        options.add_argument("--headless")
        options.add_argument("--disable-gpu")

    # Use webdriver-manager to handle the chromedriver automatically
    # Note: On Render, this uses the pre-installed Chrome.
    service = ChromeService(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    
    try:
        print("Navigating to reservation page with Selenium...")
        driver.get(TARGET_URL)
        
        # Step 1: Wait for the main search component to be visible. This is our reliable "page loaded" check.
        wait = WebDriverWait(driver, 45) # Give it extra time to load
        print(f"Waiting for main page component (ID: {PAGE_LOAD_CONFIRMATION_ID}) to load...")
        wait.until(EC.visibility_of_element_located((By.ID, PAGE_LOAD_CONFIRMATION_ID)))
        print("Main component loaded successfully.")

        # Step 2: Click the 'List' view button using its unique ID.
        print("Switching to List View...")
        wait.until(EC.element_to_be_clickable((By.ID, LIST_VIEW_BUTTON_ID)))
        list_view_button = driver.find_element(By.ID, LIST_VIEW_BUTTON_ID)
        driver.execute_script("arguments[0].click();", list_view_button)
        print("List view button clicked successfully.")
        
        # Step 3: Check for the "No Available Sites" message.
        print("Checking for 'No Available Sites' message...")
        try:
            # Wait for up to 10 seconds for the message to appear.
            short_wait = WebDriverWait(driver, 10)
            short_wait.until(EC.visibility_of_element_located((By.XPATH, NO_SITES_MESSAGE_XPATH)))
            
            # If the wait succeeds, the element was found.
            print("No sites available.")
            return 'SUCCESS_NOT_FOUND'
        except TimeoutException:
            # If the wait times out, the element was NOT found. This is our success case!
            print("SITES FOUND! The 'No Available Sites' message is gone!")
            return 'SUCCESS_FOUND'

    except TimeoutException:
        print("A timeout occurred. The page or a key component did not load in time.")
        driver.save_screenshot("error_screenshot.png")
        return 'FAILURE'
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        driver.save_screenshot("error_screenshot.png")
        return 'FAILURE'
    finally:
        # Ensure the browser is always closed to prevent resource leaks.
        driver.quit()

if __name__ == "__main__":
    print("--- Starting Campsite Availability Checker (Selenium Version) ---")
    print(f"To stop, press Ctrl+C")
    
    consecutive_failures = 0
    while True:
        try:
            status = check_availability()
            if status == 'FAILURE':
                consecutive_failures += 1
                print(f"!!! Failure count: {consecutive_failures}/{MAX_CONSECUTIVE_FAILURES}")
                if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                    print(f"!!! Reached {MAX_CONSECUTIVE_FAILURES} consecutive failures. Stopping script.")
                    failure_message = f"Campsite script stopped after {MAX_CONSECUTIVE_FAILURES} failed attempts."
                    send_pushover_notification(failure_message, title="Campsite Script Error")
                    break
            else:
                consecutive_failures = 0

            if status == 'SUCCESS_FOUND':
                notification_message = "A site may be available for your selected dates! Go book it now!"
                send_pushover_notification(notification_message)

            print(f"--- Waiting for {CHECK_INTERVAL_SECONDS} seconds before the next check...")
            time.sleep(CHECK_INTERVAL_SECONDS)
        except KeyboardInterrupt:
            print("\n--- Script stopped by user. ---")
            break