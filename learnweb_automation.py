import os
import json
import difflib
import logging
from datetime import datetime
from typing import List
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import NoSuchElementException

load_dotenv()

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_DIR = os.getenv("LOG_DIR", "logs")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
LOG_FILENAME = os.path.join(LOG_DIR, f"learnweb_{LOG_TIMESTAMP}.log")

logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOG_FILENAME, encoding="utf-8"),
    ],
)

def driver_wait_until(by, input_name):
    return WebDriverWait(driver, 10).until(
        EC.visibility_of_element_located((by, input_name)))

def login(driver, login_url):
    username = os.getenv('LOGIN')
    password = os.getenv('PASSWORD')

    driver.get(login_url)

    try:
        username_field = driver_wait_until(By.ID, "username")
        username_field.clear()
        username_field.send_keys(username)

        password_field = driver_wait_until(By.ID, "password")
        password_field.clear()
        password_field.send_keys(password)

        login_button = driver_wait_until(By.NAME, "submitBtn")
        login_button.click()

        driver_wait_until(By.TAG_NAME, "h1")

        logging.info("Logged in successfully.")
    except Exception as e:
        logging.exception("Login failed")
        raise

def extract_activity_name(driver) -> List[str]:
    activity_names = []
    
    try:
        sections = driver.find_elements(By.CSS_SELECTOR, "[id^='section-']")

        for section in sections:
            uls = section.find_elements(By.CSS_SELECTOR, "ul.section.m-0.p-0.img-text.d-block")
            
            for ul in uls:
                for li in ul.find_elements(By.TAG_NAME, "li"):
                    
                    try:
                        div = li.find_element(By.TAG_NAME, "div")
                        if activity_name := div.get_attribute("data-activityname"):
                            activity_names.append(activity_name)
                    
                    except NoSuchElementException:
                        continue
        
        return activity_names

    except Exception as e:
        logging.exception("Failed to save activity names")
        raise

def write_to_file(activity_names, course_name, output_dir="file") -> None:
    os.makedirs(output_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = os.path.join(output_dir, f"{course_name}_{timestamp}.txt")

    try:
        with open(filename, "w", encoding="utf-8") as file:
            for activity_name in activity_names:
                file.write(f"{activity_name}\n")    
        
    except Exception as e:
        logging.exception("Error writing to file")
        raise

def are_files_identical(current, previous) -> bool:
    """Check if file contents are identical"""
    try:
        with open(current, 'r') as f1, open(previous, 'r') as f2:
            return f1.read() == f2.read()
    except Exception as e:
        logging.exception("File comparison failed")
        raise
    
def print_file_difference(current_path, previous_path) -> None:
    with open(current_path, 'r') as current, open(previous_path, 'r') as previous:
        current_lines = current.readlines()
        previous_lines = previous.readlines()

    diff = difflib.unified_diff(
        previous_lines, current_lines, 
        fromfile=previous_path, 
        tofile=current_path, 
        lineterm=''
    )

    for line in diff:
        if line.startswith("+") and not line.startswith("+++"):
            logging.info("\t" + line.strip())
        elif line.startswith("-") and not line.startswith("---"):
            logging.info("\t" + line.strip())

def get_last_saved_files(course_name, spacing, output_dir="file"):
    files = sorted([f for f in os.listdir(output_dir) 
                    if f.startswith(course_name)], reverse=True)

    if len(files) >= 2:
        return os.path.join(output_dir, files[0]), os.path.join(output_dir, files[1])
    elif len(files) == 1:
        logging.warning(f"{spacing}\tWARNING: get_last_saved_files has only 1 file.")
        return os.path.join(output_dir, files[0]), None
    else:
        return None, None

def load_config(path):
    try:
        with open(path, 'r') as f:
            return json.load(f)[SEMESTER]
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logging.error(f"Config loading failed: {str(e)}")
        raise

if __name__ == "__main__":
    SEMESTER = "winter_2025_2026"

    options = Options()
    options.add_argument('--headless')
    driver = webdriver.Chrome(options=options)
    wait = WebDriverWait(driver, 10)

    course_data = load_config(path="course.json")
    login_url = course_data.pop("LOGIN_URL")

    login(driver, login_url)

    longest = max(len(name) for name in course_data)

    for course_name, url in course_data.items():
        spacing = (longest - len(course_name)) * ' '
        logging.info(f"[{course_name}]")
        try:
            driver.get(url)

            activity_name = extract_activity_name(driver=driver)
            write_to_file(activity_name, course_name)

            current, previous = get_last_saved_files(course_name, spacing)
            if not previous:
                continue

            if are_files_identical(current, previous):
                logging.info(f"No changes detected.")
            else:
                logging.info(f"Changes detected")
                print_file_difference(current, previous)
        except Exception as e:
            logging.exception(f"ERROR processing {course_name}: {e}")
            continue

    driver.quit()
