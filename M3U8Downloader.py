import os
import re
import m3u8
import requests
from urllib.parse import urlparse
from user_agent import generate_user_agent
from joblib import Parallel, delayed
import subprocess
import shutil
import time

from KaiPython.Misc import vanilla_download

class M3U8Downloader:
    def __init__(self, url=str, referer=str, out_dir=str, verbose=False) -> None:
        self.opt_v          = verbose
        self.out_dir        = out_dir
        self.tmp_dir        = os.path.join(out_dir, str(time.time()).replace('.',''))
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
            if self.opt_v: print('='*80, '\n', r.text.replace(r'\n\n', r'\n'), '\n', '='*80, sep='')
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
    
    def __get_ts(self) -> list:
        r = requests.get( url=self.playlist_url, headers=self.header )
        ts_tuples, idx = [], 0    # [(url, path)...]
        if r.ok:
            # Save to tmp dir for reference
            with open(os.path.join(self.tmp_dir, 'playlist.m3u8'), 'wb') as f:
                f.write(r.content)
            f.close
            # Iterate the m3u8 playlist to get the files
            m3u8_content = m3u8.loads(r.text)
            for playlist in m3u8_content.segments:
                if not urlparse(playlist.uri).scheme:
                    ts_tuples.append( ( self.host_path + playlist.uri,
                                      os.path.join( self.tmp_dir, f"{idx}.ts" ) ) )
                else:
                    ts_tuples.append( ( playlist.uri,
                                     os.path.join( self.tmp_dir, f"{idx}.ts" ) ) )
                idx += 1
            
            if self.opt_v: print(f"Number of files to download {len(ts_tuples)}")
            
            self.__parallel_download(ts_tuples=ts_tuples)
        else:
            raise ValueError("Unable to reach playlist url when getting ts files")
        
        return ts_tuples
        
    def __parallel_download(self, ts_tuples=list) -> None:
        # fname = re.search(r'\/([^\/\?]+)(\?[^\/]*)?$', url).group(1) 
        # Performance Analysis
        performance_start_time = time.time() 

        tasks = [delayed(vanilla_download)(tup[0], self.header, tup[1] ) for tup in ts_tuples]
        Parallel(n_jobs=4, backend='threading', require="sharedmem")(tasks)

        # Performance Analysis
        print("--- Parallel Download    %s seconds ---" % round(time.time() - performance_start_time, 2))

    def __concat_ts(self, ts_paths=list, ts_comb_path=str) -> None:
        # Performance Analysis
        performance_start_time = time.time() 

        with open(ts_comb_path, 'wb') as wfd:
            for f in ts_paths:
                with open(f, 'rb') as fd:
                    shutil.copyfileobj(fd, wfd)

        # Performance Analysis
        print("--- Concat Files         %s seconds ---" % round(time.time() - performance_start_time, 2))

    def __transcode(self, ts_path=os.path, mp4_path=os.path) -> None:
        # Performance Analysis
        performance_start_time = time.time() 

        command = f'ffmpeg -i {ts_path} -acodec copy -vcodec copy {mp4_path}'
        result = subprocess.run(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        if result.returncode == 0:
            # Performance Analysis
            print("--- Transcode            %s seconds ---" % round(time.time() - performance_start_time, 2))
            if self.opt_v: print("Transcode complete.")
        else:
            print("Transcode failed with return code:", result.returncode)
            print("Standard Error:")
            print(result.stderr)

    def download_merge_transcode(self) -> None:
        if not os.path.exists( self.tmp_dir ):
            os.mkdir( self.tmp_dir )
        # Get .ts files
        ts_tuples = self.__get_ts()
        # Concat .ts files
        ts_paths     = [tup[1] for tup in ts_tuples]
        ts_comb_path = os.path.join( self.tmp_dir, 'combined.ts')
        self.__concat_ts(ts_paths=ts_paths, ts_comb_path=ts_comb_path)
        # Transcode .ts to .mp4
        mp4_path = os.path.join( self.out_dir, 'output.mp4' )
        self.__transcode(ts_comb_path, mp4_path)
        # Clean up
        if self.opt_v: print('Cleaning up tmp dir', self.tmp_dir, '...')
        shutil.rmtree(self.tmp_dir)