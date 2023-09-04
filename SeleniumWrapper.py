from seleniumwire.utils import decode as sw_decode
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from seleniumwire import webdriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.common.by import By
from selenium_stealth import stealth

from user_agent import generate_user_agent 

import time
import re
import sys
import logging

# Selenium wrapper class
class SeleniumWrapper:
    def __init__( self, headless=True, verbose=False )->None:
        # Set option
        self.verbose=verbose
        # log on verbose
        if not self.verbose:
            selenium_logger = logging.getLogger('seleniumwire')
            selenium_logger.setLevel(logging.FATAL)

        # Create the webdriver object and pass the arguments
        options = webdriver.ChromeOptions()

        # Chrome will start in Headless mode
        if headless: options.add_argument("--headless")
    
        # Ignores any certificate errors if there is any
        options.add_argument("--ignore-certificate-errors")
    
        # Enable Performance Logging of Chrome.
        options.set_capability('browserName:chrome',  DesiredCapabilities.CHROME)
        options.set_capability('goog:loggingPrefs', {"performance": "ALL"})

        # Silence Selenium (seems to not work with selenium-wire)
        options.add_experimental_option('excludeSwitches', ['enable-logging'])

        # Add random user-agent
        user_agent = generate_user_agent()
        options.add_argument("user-agent=" + user_agent)
        print('- UserAgent:', user_agent)

        # Start chrome webdriver
        self.driver = webdriver.Chrome(options=options)

        # Max window to get all elements
        #self.driver.maximize_window()
        
        # Activate Stealth
        stealth(self.driver,
            languages=["en-US", "en"],
            vendor="Google Inc.",
            platform="Win32",
            webgl_vendor="Intel Inc.",
            renderer="Intel Iris OpenGL Engine",
            fix_hairline=True,
            )
    
    def quit( self )->None:
        # Quit selenium webdriver
        self.driver.quit()

    def request( self, url=str, load_time=2 )->None:
        # log on verbose
        if not self.verbose:
            selenium_logger = logging.getLogger('seleniumwire')
            selenium_logger.setLevel(logging.FATAL)
        # Send a request to the website and let it load
        print('- Loading page...\n\t', url, file=sys.stderr)

        self.driver.get(url)
    
        # Sleep for page to load through the network request required
        time.sleep(load_time)
        self.driver.implicitly_wait(20)
    
    def clean_network_traffic( self )->None:
        # clean out captured requests
        del self.driver.requests

    def scan_network_traffic( self )->list:

        res = []
        # scan traffic
        for request in self.driver.requests:
            url_received = request.url
            try:
                body = sw_decode(request.response.body, 
                                request.response.headers.get('Content-Encoding', 'identity'))
                try:
                    body = body.decode("utf-8", errors='fatal') #, errors='replace')
                except:
                    try:
                        body = body.decode("unicode-escape", errors='fatal')
                    except:    
                        body = '### Decode Failed ###'
                
                # Try to find the correct referer
                this_referer = ''
                if request.headers.get("referer"):
                    this_referer = request.headers.get("referer") 
                
                # append to res
                res.append({
                    'url': url_received,
                    'header': request.headers.as_string(),
                    'body': body,
                    'referer': this_referer,
                })
            except:
                print('= Warn: error parsing network traffic from:', 
                url_received[:50]+'...', file=sys.stderr)
        
        return res
    
    def am_i_blocked_by_cloudflare( self )->bool:
        # cloudflare support only
        cloudflare = "//iframe[contains(@src, 'cloudflare')]"
        elements = self.driver.find_elements(By.XPATH, cloudflare)
        return True if len(elements) > 0 else False
       
    def get_clickables( self, search_suggestion=None )->(list, list):
        # return ([clickable obj], [WebElement])

        # blocked?
        if self.am_i_blocked():
            print('! Terminated: Request blocked by cloudflare')
            sys.exit(1)

        # search elements
        elements = None # XPATH syntax //tag[@attr="player"]/div/span[2]
        if not search_suggestion:
            elements = self.driver.find_elements(By.XPATH, '//*class') # get all el by xpath *
        else:
            try:    # get by partial class
                search_pattern = "//*[contains(@class, '" + search_suggestion + "')]"
                print('- XPATH search pattern:', search_pattern)
                elements = self.driver.find_elements(By.XPATH, search_pattern)
            except Exception as e:
                print("Error finding element: " + e)
                sys.exit(1)

        # collect elements info
        clickables, click_elements = [], {}
        print('# found elements num:', len(elements))
        my_id = 0
        for el in elements:
            # append clickable
            if el.is_displayed() and el.is_enabled():
                clickables.append({ 
                                'my_id': my_id,
                                'tag': el.tag_name,
                                'class': el.get_attribute("class"),
                                'id': el.get_attribute("id"),
                                'text': el.text,
                                })
                click_elements[my_id] = el
                my_id += 1

        print('# found clickables num:', len(clickables))
        return (clickables, click_elements)

    def click( self, element=WebElement, load_time=2 )->None:
        # print("click", element.tag_name, 'at', element.location)
        self.driver.execute_script("arguments[0].scrollIntoView();", element)
        self.driver.execute_script("arguments[0].click();", element)
        time.sleep(load_time)