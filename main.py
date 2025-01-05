import shutil
import requests
from bs4 import BeautifulSoup
import os
from svglib.svglib import svg2rlg
from reportlab.pdfgen import canvas
from reportlab.graphics import renderPDF
from art import tprint
from colorama import Fore, Style
import getpass

s = requests.Session()

src_dir = os.path.join(os.getcwd(), "src")
if not os.path.exists(src_dir):
    os.makedirs(src_dir)

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Origin": "https://digi4school.at",
    "Referer": "https://digi4school.at/",
}

ebook_headers = {
    "User-Agent": headers["User-Agent"],
    "Referer": "https://digi4school.at/ebooks",
    "Origin": "https://digi4school.at",
}

def get_login(email, password):
    payload = {
        "email": email,
        "password": password
    }

    try:
        login_response = s.post("https://digi4school.at/br/xhr/login", data=payload, headers=headers)
        login_response.raise_for_status()
    except requests.RequestException as e:
        print(Fore.RED + "Error while logging in: " + str(e) + Style.RESET_ALL)
        return None

    if login_response.status_code != 200:
        print(Fore.RED + "Login failed: Invalid credentials or server error." + Style.RESET_ALL)
        return None

    return True

def get_book_arr():
    try:
        ebooks_response = s.get("https://digi4school.at/ebooks", headers=ebook_headers)
        ebooks_response.raise_for_status()
    except requests.RequestException as e:
        print(Fore.RED + "Error fetching book list: " + str(e) + Style.RESET_ALL)
        return []

    soup = BeautifulSoup(ebooks_response.text, 'html.parser')
    shelf = soup.find('div', id='shelf')

    if not shelf:
        print(Fore.YELLOW + "No books found in your account." + Style.RESET_ALL)
        return []

    books = shelf.find_all('a', class_='bag')
    book_details = []
    for book in books:
        url = book.get('href', '#')
        name = book.find('h1').text.strip() if book.find('h1') else "Unnamed Book"
        book_details.append({'name': name, 'url': url})

    return book_details

def handle_redirect(response):
    try:
        soup = BeautifulSoup(response.text, 'html.parser')
        form = soup.find('form', {'id': 'lti'})
        if form:
            action_url = form['action']
            form_data = {input_tag['name']: input_tag['value'] for input_tag in form.find_all('input')}
            next_response = s.post(action_url, data=form_data)
            return handle_redirect(next_response)
        else:
            return response.url, response.text
    except Exception as e:
        print(Fore.RED + "Error during redirection: " + str(e) + Style.RESET_ALL)
        return None, None

def get_svgs(base_url, length):
    svg_paths = []
    error_count = 0
    max_errors = 10
    use_alternative_url = False

    for i in range(length):
        try:
            current_base_url = f"{base_url.rstrip('/')}/" if not use_alternative_url else f"{base_url.rstrip('/')}/{i + 1}/"

            svg_url = f"{current_base_url}{i + 1}.svg"
            response = s.get(svg_url)

            if response.status_code != 200:
                current_base_url = f"{base_url.rstrip('/')}/{i + 1}/" if not use_alternative_url else f"{base_url.rstrip('/')}/"
                svg_url = f"{current_base_url}{i + 1}.svg"
                response = s.get(svg_url)

                if response.status_code != 200:
                    raise Exception(f"Failed to fetch SVG from {svg_url}")

                use_alternative_url = not use_alternative_url

            svg_path = os.path.join(src_dir, f"{i + 1}.svg")
            with open(svg_path, "w", encoding="utf-8") as file:
                file.write(response.text)

            embed_imgs(response.text, current_base_url)

            svg_paths.append(svg_path)

            display_progress_bar(i + 1, length, "Downloading")

            error_count = 0

        except Exception as e:
            print(f"Error downloading SVG {i + 1}: {e}")
            error_count += 1
            if error_count > max_errors:
                print("Max error limit reached. Stopping downloads.")
                break

    return svg_paths

def embed_imgs(xml_string, base_url):
    soup = BeautifulSoup(xml_string, 'xml')
    images = soup.find_all('image')

    for image in images:
        if 'xlink:href' in image.attrs:
            image_url = image['xlink:href']
            full_url = f"{base_url.rstrip('/')}/{image_url.lstrip('/')}"
            local_file_path = os.path.join(src_dir, image_url.replace("/", os.sep))

            try:
                os.makedirs(os.path.dirname(local_file_path), exist_ok=True)
                img_response = s.get(full_url)
                img_response.raise_for_status()
                with open(local_file_path, "wb") as out_file:
                    out_file.write(img_response.content)
            except (requests.RequestException, IOError) as e:
                print(Fore.RED + f"Error embedding image {image_url}: " + str(e) + Style.RESET_ALL)

def convert_pdf(svg_paths, output_pdf):
    pdf_canvas = canvas.Canvas(output_pdf + ".pdf")

    pdf_canvas.setAuthor("digi4school2PDF")
    pdf_canvas.setTitle(output_pdf)

    for count, svg_file in enumerate(svg_paths):
        try:
            drawing = svg2rlg(svg_file)
            pdf_canvas.setPageSize((drawing.width, drawing.height))
            renderPDF.draw(drawing, pdf_canvas, 0, 0)
            pdf_canvas.showPage()
            display_progress_bar(count + 1, len(svg_paths), "converting")
        except Exception as e:
            print(Fore.RED + f"Error converting SVG {svg_file} to PDF: " + str(e) + Style.RESET_ALL)
            continue

    try:
        pdf_canvas.save()
    except IOError as e:
        print(Fore.RED + "Error saving PDF: " + str(e) + Style.RESET_ALL)

    return output_pdf

def check_subdir(html):
    soup = BeautifulSoup(html, 'html.parser')
    content = soup.find('div', {'id': 'content'})

    if not content:
        return []

    files = []
    for anchor in content.find_all('a'):
        href = anchor.get('href', '')
        if href.endswith('.html'):
            book_name = anchor.find('h1').text if anchor.find('h1') else 'Unnamed Book'
            files.append({'name': book_name, 'url': href})

    return files

def display_cli_intro():
    os.system('cls' if os.name == 'nt' else 'clear')

    print(Style.RESET_ALL+""+Fore.CYAN+Style.BRIGHT)
    tprint("digi4school2PDF")
    print("")
    print("📕 Convert Digi4School E-Books to PDF files")
    print("🌍 github.com/lorenz1e/digi4school2PDF")
    print("" + Style.RESET_ALL)

def display_progress_bar(cur_page, length, msg):
    os.system('cls' if os.name == 'nt' else 'clear')

    display_cli_intro()

    fill_char = "═"
    space_char = "═"

    cur_val = 100 / (length / cur_page)

    fill = fill_char * int(cur_val / 5)
    if cur_val <= 10:
        fill = fill_char

    space = space_char * (20 - len(fill))

    print(f"Currently {msg}: {Style.BRIGHT}{Fore.CYAN}{current_book}{Style.RESET_ALL}")
    print("")
    print(f"{round(cur_val, 1)}%  [{Style.RESET_ALL}{Style.BRIGHT}{Fore.LIGHTCYAN_EX}{fill} {Style.DIM}{Fore.WHITE}{space}{Style.RESET_ALL}]  {cur_page}/{length}")

def main():
    display_cli_intro()

    print(Style.BRIGHT+"Please login to your Digi4School Account")
    print("")

    email = input("E-Mail: "+Fore.CYAN)
    
    password = getpass.getpass(prompt=Fore.WHITE+"Password: ")
    

    if not get_login(email=email, password=password):
        return

    book_arr = get_book_arr()

    if not book_arr:
        print(Fore.RED + "No books available to download." + Style.RESET_ALL)
        return

    display_cli_intro()
    print(Fore.CYAN+Style.BRIGHT+"Avialable books: "+Style.RESET_ALL)


    for count, book in enumerate(book_arr):
        print(f"{Fore.WHITE}{count}. {book['name']}")

    while True:
        
        try:
            print("")
            selected_index = int(input(f"{Fore.CYAN}{Style.BRIGHT}Select a book you want to download (0 - {len(book_arr) - 1}): "))
            if 0 <= selected_index < len(book_arr):
                break
            else:
                print(Fore.RED + "Please enter a valid number!" + Style.RESET_ALL)
        except ValueError:
            print(Fore.RED + "Please enter a valid number!" + Style.RESET_ALL)

    global current_book
    current_book = str(book_arr[selected_index]['name'])
    url = "https://digi4school.at" + book_arr[selected_index]['url']

    try:
        p = s.get(url, headers=ebook_headers)
        p.raise_for_status()
    except requests.RequestException as e:
        print(Fore.RED + "Error fetching book details: " + str(e) + Style.RESET_ALL)
        return

    base_url, viewer_html = handle_redirect(p)

    if not base_url or not viewer_html:
        print(Fore.RED + "Failed to fetch book content." + Style.RESET_ALL)
        return

    subdir = check_subdir(viewer_html)

    if subdir:
        print("")
        print(Fore.CYAN+Style.BRIGHT+"Avialable sub-books: "+Style.RESET_ALL)
        for count, book in enumerate(subdir):
            print(f"{count}. {book['name']}")

        while True:
            try:
                print("")
                selected_index = int(input(f"{Fore.CYAN}{Style.BRIGHT}Select a sub-book (0 - {len(subdir) - 1}): "))
                if 0 <= selected_index < len(subdir):
                    break
                else:
                    print(Fore.RED + "Please enter a valid number!" + Style.RESET_ALL)
            except ValueError:
                print(Fore.RED + "Please enter a valid number!" + Style.RESET_ALL)

        dir_url = base_url
        base_url = f"{dir_url}{subdir[selected_index]['url'].replace('/index.html','')}/"
        current_book = subdir[selected_index]['name']

    print(base_url)

    try:
        length = int(input("Enter the number of pages in the selected book: "))
    except ValueError:
        print(Fore.RED + "Invalid length input." + Style.RESET_ALL)
        return
    
    svg_paths = get_svgs(base_url, length)

    pdf_name = convert_pdf(svg_paths=svg_paths, output_pdf=current_book)

    os.system('cls' if os.name == 'nt' else 'clear')

    display_cli_intro()
    print(f"Saved {Style.BRIGHT}{Fore.CYAN}{pdf_name}{Style.RESET_ALL}")
    shutil.rmtree("src")

if __name__ == "__main__":
    while True:
        main()
