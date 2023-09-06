import os
import re
import requests
from urllib.parse import urlparse
from user_agent import generate_user_agent
import m3u8
from joblib import Parallel, delayed
import time

from KaiPython.Misc import vanilla_download

class M3U8Downloader:
    def __init__(self, url=str, referer=str, out_dir=str, verbose=False) -> None:
        self.opt_v          = verbose
        self.out_dir        = out_dir
        self.tmp_dir        = os.path.join(out_dir, r'm3u8_tmp')
        self.playlist_url   = url
        self.host_path      = self.__host_path()
        self.referer        = referer
        self.header         = {'referer': referer, 'user-agent': generate_user_agent(os=('mac', 'win'))}
        self.__resolve_if_master_playlist()

        if not os.path.exists( self.tmp_dir ):
                os.mkdir( self.tmp_dir )
        
        
    def __resolve_if_master_playlist(self) -> None:
        r = requests.get( url=self.playlist_url, headers=self.header )

        if r.ok:
            # Parse the master M3U8 playlist
            if self.opt_v: print(r.text)
            m3u8_content = m3u8.loads(r.text)
            if m3u8_content.is_variant:
                # Find the highest resolution stream
                max_reso_url = None
                max_width = 0
                for playlist in m3u8_content.playlists:
                    if playlist.stream_info.resolution and playlist.stream_info.resolution[0] > max_width:
                        max_width = playlist.stream_info.resolution[0]
                        max_reso_url = playlist.uri
                # Set the playlist url to highest resolution available
                if max_reso_url:
                    if not urlparse(max_reso_url).scheme:
                        self.playlist_url = self.host_path + max_reso_url
                    else:
                        self.playlist_url = max_reso_url
                else:
                    raise ValueError(f"Unable to parse max resolution, m3u8 content:\nr.text")
        else:
            raise ValueError("Unable to reach playlist url")

    def __host_path(self) -> str:
        ## Hostname
        # parsed_url = urlparse(self.playlist_url)
        # rel_path = parsed_url.scheme + '://' + parsed_url.hostname
        ## Relative path assume .m3u8 at the end
        # rel_path = r'/'.join(self.playlist_url.split(r'/')[:-1]) + r'/'
        ## Advanced regex
        rel_path =  re.sub(r'[^\/]+\.m3u8.*$', '', self.playlist_url)
        return rel_path
    
    def __get_ts(self) -> None:
        r = requests.get( url=self.playlist_url, headers=self.header )
        file_urls = []
        if r.ok:
            # Save to tmp dir for reference
            with open(os.path.join(self.tmp_dir, 'playlist.m3u8'), 'wb') as f:
                f.write(r.content)
            f.close
            # Iterate the m3u8 playlist to get the files
            m3u8_content = m3u8.loads(r.text)
            for playlist in m3u8_content.segments:
                if not urlparse(playlist.uri).scheme:
                    file_urls.append( self.host_path + playlist.uri )
                else:
                    file_urls.append( playlist.uri )
            
            if self.opt_v: print(f"Number of files to download {len(file_urls)}")
            
            self.__parallel_download(file_urls=file_urls)
        else:
            raise ValueError("Unable to reach playlist url when getting ts files")
        
    def __parallel_download(self, file_urls=list) -> None:
        # fname = re.search(r'\/([^\/\?]+)(\?[^\/]*)?$', url).group(1) 
        # Performance Analysis
        performance_start_time = time.time() 

        tasks = [delayed(vanilla_download)
                    (v, self.header, os.path.join( self.tmp_dir, f"{i}.ts" ) ) 
                 for i, v in enumerate(file_urls)]
        Parallel(n_jobs=-1, backend='threading', require="sharedmem")(tasks)

        # Performance Analysis
        print("--- %s seconds ---" % (time.time() - performance_start_time))

    
    def download_and_merge(self):
        self.__get_ts()