import os
import time
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