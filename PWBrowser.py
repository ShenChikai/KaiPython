import os 
import re
from sys import stderr
import getpass
from time import sleep
from user_agent import generate_user_agent
from playwright.sync_api import sync_playwright

# single page browser wrapped on PlayWright
class PWBrowser:
    def __init__(self, chrome_path=str, user_agent=generate_user_agent(os=('mac', 'win')), headless=True, verbose=False) -> None:
        self.verbose = verbose
        if self.verbose: print(f"Launching playwright single page browser wrapper...\nuser_agent: {user_agent}")
        self.chrome_path= chrome_path if isinstance(chrome_path, str) and os.path.exists(chrome_path) \
            else f"C:\\Users\\{getpass.getuser()}\\AppData\\Local\\Google\\Chrome\\User Data"
         # "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
        self.pw         = sync_playwright().start() # playwright enter
        self.browser    = self.pw.chromium.launch_persistent_context(
            user_data_dir   = self.chrome_path,
            user_agent      = user_agent,
            headless        = headless,
            is_mobile       = True,
            bypass_csp      = True,
            channel         = "chrome",
        )
        self.page       = self.browser.new_page()
        if self.verbose: print(f"Launched from {self.chrome_path}")

    def goto(self,url=str):
        if not self.__check_url_validity(url=url):
            print("Invalid url format.")
            return
        self.page.goto(url=url)

    def get_title(self):
        return self.page.title()

    def intercept_network_traffic(self, url=str, keyword=False, sleep_time=3):
        if not self.__check_url_validity(url=url):
            print("Invalid url format.")
            return None
        
        if self.verbose: print("Intercepting network traffic...")
        request_list, response_list  = [], []
        self.page.on("request", lambda request: 
                     request_list.append({
                         "method": request.method, 
                         "url": request.url,
                         "headers": request.all_headers()
                         }))
        self.page.on("response", lambda response:
                     response_list.append({
                         "status": response.status,
                         "url": response.url,
                         "headers": response.all_headers()
                         }))
        self.page.goto(url=url, wait_until="networkidle")
        sleep(sleep_time)
        print(f"requests: {len(request_list)}, responses: {len(response_list)}")

        if not keyword: return {"request_list": request_list,
                                "response_list": response_list}
        
        # TODO: Filter traffic on keyword in url
        if self.verbose: print(f"Filtering requests with keyword \"{keyword}\"...")

        filtered_request_list = [r for r in request_list if keyword in r["url"]]
        filtered_response_list = [r for r in response_list if keyword in r["url"]]
        return {"request_list": filtered_request_list,
                "response_list": filtered_response_list}
        
    def destory(self):
        self.browser.close()
        self.pw.stop()

    '''class helper methods'''
    def __check_url_validity(self, url=str):
        valid_url_regex = re.compile(
            r'^(?:http|ftp)s?://' # http:// or https://
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|' #domain...
            r'localhost|' #localhost...
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})' # ...or ip
            r'(?::\d+)?' # optional port
            r'(?:/?|[/?]\S+)$', re.IGNORECASE)
        return re.match(valid_url_regex, url) is not None   
