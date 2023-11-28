import os
import re
import requests
from requests.adapters import HTTPAdapter, Retry

def vanilla_download(url=str, header=dict, out_path=os.path or str, 
                     suppress_fail=False, retry=3, timeout=3):
    r = False
    while retry != 0:
        try:
            r = requests.get(url=url, headers=header, timeout=(1, timeout-1))
            if r.ok: break
        except:
            pass
        retry -= 1

    if r and r.ok:
        # save to path
        with open(out_path, 'wb') as f:
            f.write(r.content)
        return None
    else:
        # suppress this?
        if suppress_fail:
            return out_path
        else:
            raise Exception("Failed to download", out_path)
    
''' work around with tqdm thread_map '''
def vanilla_download_with_dict(args_dict):
    url=args_dict["url"] 
    header=args_dict["header"]
    out_path=args_dict["out_path"]
    suppress_fail=args_dict["out_path"] if args_dict.get("out_path") else False
    retry=args_dict["retry"] if args_dict.get("retry") else 3
    timeout=args_dict["timeout"] if args_dict.get("timeout") else 3
    
    r = False
    while retry != 0:
        try:
            r = requests.get(url=url, headers=header, timeout=(1, timeout-1))
            if r.ok: break
        except:
            pass
        retry -= 1

    if r and r.ok:
        # save to path
        with open(out_path, 'wb') as f:
            f.write(r.content)
        return None
    else:
        # suppress this?
        if suppress_fail:
            return out_path
        else:
            raise Exception("Failed to download", out_path)

# url_hash_list = [{url:_, dir:_, name:_}...]
def session_downloads(url_hash_list=list, header=dict, retry=3):
    s = requests.Session()
    retry_attr = Retry(total=retry, backoff_factor=1, status_forcelist=[ 502, 503, 504 ])
    s.headers.update( header )
    s.mount('http://', HTTPAdapter(max_retries=retry_attr))
    s.mount('https://', HTTPAdapter(max_retries=retry_attr))

    for url_hash in url_hash_list:
        url, out_dir, file_name = url_hash['url'], url_hash['dir'], url_hash['name']
        out_path = os.path.join(out_dir, file_name)
        for attempt in range(retry):
            r = s.get(url=url)
            if r.ok:
                # save to path
                with open(out_path, 'wb') as f:
                    f.write(r.content)
                break
            else:
                if attempt == retry - 1:
                    raise Exception(f"Failed to download:\n  {url}\n  to {out_path}")
            r.close
