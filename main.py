from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from seleniumrequests import Chrome
from svglib.svglib import svg2rlg
from reportlab.pdfgen import canvas
from reportlab.graphics import renderPDF
from art import tprint
from colorama import Fore, Style
import os
import shutil
import threading
import queue

chrome_options = Options()
chrome_options.add_argument("--disable-gpu")
chrome_options.add_argument("--log-level=1")
# chrome_options.add_argument("--headless")
os.environ['WDM_LOG'] = "false"

driver = Chrome()

src_dir = os.path.join(os.getcwd(), "src")
if not os.path.exists(src_dir):
    os.makedirs(src_dir)

download_queue = queue.Queue()

def embed_imgs(base_url):
    imgs = driver.find_elements(By.TAG_NAME, "image")
    print(f"Found {len(imgs)} images in {driver.current_url}")
    
    if imgs:
        for img in imgs:
            try:
                url = img.get_attribute("xlink:href")
                if url:
                    full_url = f"{base_url}/{url}".replace("//", "/")
                    
                    local_file_path = os.path.join(src_dir, url.replace("/", os.sep))
                    local_dir = os.path.dirname(local_file_path)
                    
                    if not os.path.exists(local_dir):
                        os.makedirs(local_dir)
                    
                    driver.execute_script("window.open();")
                    driver.switch_to.window(driver.window_handles[-1])
                    driver.get(full_url)
                    
                    image_element = driver.find_element(By.TAG_NAME, "img")
                    image_element.screenshot(local_file_path)
                    
                    driver.close()
                    driver.switch_to.window(driver.window_handles[0])
            except Exception as e:
                print(f"Error embedding image: {e}")
    else:
        print("No images to embed.")

def download_and_enqueue(length, base_url):
    for i in range(length):
        svg_url = f"{base_url}/{i + 1}.svg"
        driver.get(svg_url)
        
        svg_element = driver.find_element(By.TAG_NAME, "svg")
        svg_content = svg_element.get_attribute('outerHTML')

        svg_path = os.path.join(src_dir, f"{i + 1}.svg")
        with open(svg_path, "w", encoding="utf-8") as file:
            file.write(svg_content)

        embed_imgs(base_url)
        print(f"Saved Page {i + 1} in {svg_path}")

        download_queue.put(svg_path)

    download_queue.put(None)

def convert_to_pdf(output_pdf):
    pdf_canvas = canvas.Canvas(output_pdf+".pdf")

    while True:
        svg_file = download_queue.get()
        if svg_file is None:  
            break

        drawing = svg2rlg(svg_file)
        pdf_canvas.setPageSize((drawing.width, drawing.height))
        renderPDF.draw(drawing, pdf_canvas, 0, 0)
        pdf_canvas.showPage()
        print(f"Added '{svg_file}' to '{output_pdf}.pdf'")

    pdf_canvas.save()
    print(f'Saved {output_pdf}.pdf')

def getBookData():
    try:
        driver.switch_to.window(driver.window_handles[-1])

        opened_url = driver.current_url
        base_url = opened_url[:opened_url.rfind("/")]
        pageCount = driver.find_element(By.ID, "pgCount")

        length = int(pageCount.get_attribute("innerText").replace("/", ""))

        fileName = driver.find_element(By.TAG_NAME, "title").get_attribute("innerText")

        driver.close()
        driver.switch_to.window(driver.window_handles[0])

        return base_url, length, fileName
    except Exception as e:
        print(f"Error getting book data: {e}")
        return None, None, None

def display_cli_intro():
    os.system('cls' if os.name == 'nt' else 'clear')
    print(Style.RESET_ALL+""+Fore.MAGENTA)
    tprint("digi4school2PDF")
    print("")
    print("📕 Convert Digi4School E-Books to PDF files")
    print("🌍 github.com/lorenz1e | v1")
    print("")
    print("⚠️  Google Chrome 130.0 or higher is required")
    print("")
    print(Style.RESET_ALL+"")

def getLogin():
    print("Login to your Digi4School account...\n")

    while True:
        if driver.current_url == "https://digi4school.at/ebooks":
            return        

def main():
    while True:
        display_cli_intro()
        
        driver.get('https://digi4school.at')
                
        getLogin()
                
        os.system('cls' if os.name == 'nt' else 'clear')
        display_cli_intro()
        print("1. Open the book you want to download in the browser.")
        print("2. Press the RETURN key here to start downloading the book.\n")
        input("Press RETURN to proceed...")
        
        base_url, length, file_name = getBookData()
        if not base_url or not length or not file_name:
            print("Failed to retrieve book data")
            driver.quit()
            return
        
        driver.minimize_window();

        download_thread = threading.Thread(target=download_and_enqueue, args=(length, base_url))
        pdf_thread = threading.Thread(target=convert_to_pdf, args=(file_name,))

        download_thread.start()
        pdf_thread.start()

        download_thread.join()
        pdf_thread.join()

        driver.quit()
        shutil.rmtree("src")
        
        os.system('cls' if os.name == 'nt' else 'clear')
        display_cli_intro()
        print(f"\nBook '{file_name}' has been downloaded and saved as a PDF\n")
        break

if __name__ == "__main__":
    main()
