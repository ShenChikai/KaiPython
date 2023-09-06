import os
import re
import requests
from pathlib import Path # Auto Download path lookup
from googletrans import Translator # Translator for non-english system

def default_download_path():
    translator = Translator()
    downloads = "Downloads"
    downloads_path = str(Path.home() / downloads)

    if str(downloads_path.split("\\")[-1]) != downloads:
        en_path = translator.translate(str(downloads_path.split("\\")[-1]), dest="en")
        if en_path.text == "downloads" or en_path.text == "Downloads":
            downloads_path = str(Path.home() / str(en_path.text))
    return downloads_path

def get_parent_dir( path=str ):
    return Path( path ).parent.absolute()

def get_file_barename( path=str ):
    return os.path.splitext( os.path.basename( path ) )[0]

def vanilla_download(url=str, header=dict, out_file=os.path or str, retry=3):
    for attempt in range(retry):
        r = requests.get(url=url, headers=header)
        if r.ok:
            # save to path
            with open(out_file, 'wb') as f:
                f.write(r.content)
            f.close
            break
        else:
            if attempt == retry - 1:
                raise Exception(f"Failed to download:\n  {url}\n  to {out_file}")
        r.close