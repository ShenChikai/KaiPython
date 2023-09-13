import os
import re
import requests
from requests.adapters import HTTPAdapter, Retry

def vanilla_download(url=str, header=dict, out_path=os.path or str, suppress_fail=False, retry=3):
    for attempt in range(retry):
        r = requests.get(url=url, headers=header)
        if r.ok:
            # save to path
            with open(out_path, 'wb') as f:
                f.write(r.content)
            break
        else:
            if attempt == retry - 1:
                if suppress_fail:
                    r.close
                    return out_path
                else:
                    raise Exception(f"Failed to download:\n  {url}\n  to {out_path}")
        r.close
        return None

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