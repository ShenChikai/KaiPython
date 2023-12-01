import os 
import re
from sys import stderr
import getpass
from user_agent import generate_user_agent
from playwright.sync_api import sync_playwright

# single page browser wrapped on PlayWright
class PWBrowser:
    def __init__(self, chrome_path=str, headless=True) -> None:
        self.chrome_path= chrome_path if isinstance(chrome_path, str) and os.path.exists(chrome_path) \
            else f"C:\\Users\\{getpass.getuser()}\\AppData\\Local\\Google\\Chrome\\User Data"
        self.pw         = sync_playwright().start() # playwright enter
        self.browser    = self.pw.chromium.launch_persistent_context(
            user_data_dir   = self.chrome_path,
            user_agent      = generate_user_agent(os=('mac', 'win')),
            headless        = headless
        )
        self.page       = self.browser.new_page()

    def get_title(self,url=str):
        if not self.__check_url_validity(url=url):
            print("Invalid url format.", file=stderr)
            return None
        self.page.goto(url=url)
        return self.page.title()

    def intercept_network_traffic(self, url=str, keyword=False):
        if not self.__check_url_validity(url=url):
            print("Invalid url format.", file=stderr)
            return None
        
        response_list, request_list = [], []
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
        self.page.goto(url=url)

        if not keyword: return {"response_list": response_list, 
                                "request_list": request_list} 
        
        # TODO: Filter traffic on keyword
    
        
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

# test
pwb = PWBrowser()
pwb.intercept_network_traffic("https://javopen.co/video/abf-051-airi-suzumura/")
print(pwb.page.title())
