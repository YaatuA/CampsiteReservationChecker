import time
import requests
import os
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

# --- CONFIGURATION ---
# Load environment variables from a .env file in the same directory
load_dotenv()

# Retrieve configuration from environment variables
TARGET_URL = os.getenv("TARGET_URL")
PUSHOVER_API_TOKEN = os.getenv("PUSHOVER_API_TOKEN")
PUSHOVER_USER_KEY = os.getenv("PUSHOVER_USER_KEY")

# --- SCRIPT SETTINGS ---
CHECK_INTERVAL_SECONDS = 5
MAX_CONSECUTIVE_FAILURES = 3
# Set to False to see the browser window, or True to run in the background.
HEADLESS_MODE = True


def send_pushover_notification(message, title="Campsite Available!"):
    """
    Sends a notification to your device via the Pushover service.
    """
    if not PUSHOVER_API_TOKEN or not PUSHOVER_USER_KEY:
        print("Pushover credentials are not set in the .env file. Skipping notification.")
        return

    try:
        payload = {
            "token": PUSHOVER_API_TOKEN, "user": PUSHOVER_USER_KEY,
            "message": message, "title": title, "priority": 1
        }
        if "book it now" in message:
            payload["url"], payload["url_title"] = TARGET_URL, "Book Now!"
        response = requests.post("https://api.pushover.net/1/messages.json", data=payload, timeout=10)
        if response.status_code == 200:
            print("Notification sent successfully!")
        else:
            print(f"Failed to send notification. Status: {response.status_code}, Response: {response.text}")
    except requests.RequestException as e:
        print(f"An error occurred while sending the Pushover notification: {e}")


def check_availability():
    """
    Main function to check for site availability using robust Playwright locators.
    """
    if not TARGET_URL:
        print("TARGET_URL is not set in the .env file. Cannot proceed.")
        return 'FAILURE'

    with sync_playwright() as p:
        print("Launching browser...")
        browser = p.chromium.launch(headless=HEADLESS_MODE)
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36',
            viewport={'width': 1920, 'height': 1080}
        )
        page = context.new_page()

        try:
            print("Navigating to reservation page...")
            page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=90000)

            print("Waiting for page content to load by verifying date fields are visible...")
            page.get_by_label("Arrival").wait_for(state="visible", timeout=30000)
            page.get_by_label("Departure").wait_for(state="visible", timeout=15000)
            print("Dates verified successfully.")
            
            print("Switching to List View...")
            page.get_by_label("List view of results").click()
            
            print("Checking for 'No Available Sites' message...")
            try:
                no_sites_locator = page.get_by_text("No Available Sites", exact=True)
                no_sites_locator.wait_for(state="visible", timeout=10000)
                
                # If the wait succeeds, the element was found.
                print("No sites available. Will check again later.")
                context.close()
                return 'SUCCESS_NOT_FOUND'
            except PlaywrightTimeoutError:
                # If the wait times out, the element was NOT found. This is our success case!
                print("SITES FOUND! The 'No Available Sites' text was not found.")
                context.close()
                return 'SUCCESS_FOUND'

        except PlaywrightTimeoutError:
            print("A timeout occurred. The page or a key element did not load in time.")
            page.screenshot(path="error_screenshot.png")
            context.close()
            return 'FAILURE'
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            page.screenshot(path="error_screenshot.png")
            context.close()
            return 'FAILURE'

if __name__ == "__main__":
    print("--- Starting Campsite Availability Checker ---")
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
                    failure_message = f"Campsite script stopped after {MAX_CONSECUTIVE_FAILURES} failed attempts to access the website."
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