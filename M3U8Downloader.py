import os
import re
from sys import exit
import m3u8
import requests
from urllib.parse import urlparse
from user_agent import generate_user_agent
from joblib import Parallel, delayed
from tqdm.contrib.concurrent import thread_map
import concurrent.futures
import subprocess
import shutil
import time

from KaiPython.RequestsWrapper import vanilla_download, vanilla_download_with_dict, session_downloads

class M3U8Downloader:
    def __init__(self, url=str, referer=str, out_dir=str, out_name='output', skip_fail=False, num_downloaders=4, progress_bar=False, verbose=False) -> None:
        self.opt_v          = verbose
        self.timer_set      = False
        self.out_dir        = out_dir
        self.out_name       = out_name
        self.tmp_dir        = os.path.join(out_dir, 'm3u8_dir_'+str(time.time()).replace('.',''))
        self.playlist_url   = url
        self.host_path      = self.__host_path()
        self.middle_path    = ''
        self.referer        = referer
        self.header         = {'referer': referer, 'user-agent': generate_user_agent(os=('mac', 'win'),)}
        self.num_jobs       = num_downloaders
        self.progress_bar   = progress_bar
        self.num_tasks      = None
        self.num_tasks_left = None
        self.report_freq    = 0.05         # report frequency = every 5%
        self.__resolve_if_master_playlist()

        # Skip the ones failed to be downloaded
        self.skip_fail      = skip_fail

        if not os.path.exists( self.tmp_dir ):
                os.mkdir( self.tmp_dir )
        
        
    def __resolve_if_master_playlist(self) -> None:
        r = requests.get( url=self.playlist_url, headers=self.header )

        if r.ok:
            # Parse the master M3U8 playlist
            if self.opt_v: 
                m3u8_text_to_print = "".join([s for s in r.text.strip().splitlines(True) if s.strip()][:15])
                print('='*80, '\n', m3u8_text_to_print, '\n', '='*80, sep='')
            m3u8_content = m3u8.loads(r.text)
            if m3u8_content.is_variant:
                if self.opt_v: print("Master m3u8 detected")
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

                    # check for middle path (relative path of the m3u8 playlist)
                    if '/' in max_reso_url:
                        middle_path_comps = max_reso_url.split('/')
                        self.middle_path  = '/'.join(middle_path_comps[:-1]) + '/'
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
        ts_hash_list, idx = [], 0    # [(url, dir, file_name)...]
        if r.ok:
            # Save to tmp dir for reference
            with open(os.path.join(self.tmp_dir, 'playlist.m3u8'), 'wb') as f:
                f.write(r.content)
            f.close
            # URL dir to ts files
            ts_dir_url = self.host_path + self.middle_path
            # Iterate the m3u8 playlist to get the files
            m3u8_content = m3u8.loads(r.text)
            for playlist in m3u8_content.segments:
                if not urlparse(playlist.uri).scheme:
                    # no http in front
                    ts_hash_list.append( 
                                        {
                                            'url':  ts_dir_url + playlist.uri, 
                                            'dir':  self.tmp_dir,
                                            'name': f"{idx}.ts"
                                        } 
                                    )
                else:
                    ts_hash_list.append(
                                        {
                                            'url':  playlist.uri,
                                            'dir':  self.tmp_dir, 
                                            'name': f"{idx}.ts"
                                        } 
                                    ) 
                idx += 1
            
            if self.opt_v: print(f"Num files to download: {len(ts_hash_list)}")
            
            if self.progress_bar:
                self.__parallel_download_with_progress_bar(ts_hash_list=ts_hash_list)
            else:
                self.__parallel_download_with_joblib(ts_hash_list=ts_hash_list)
            # self.__parallel_session_download(ts_hash_list=ts_hash_list)    # this is slow, not sure why
        else:
            raise ValueError("Unable to reach playlist url when getting ts files")
        
        return ts_hash_list
        
    def __parallel_session_download(self, ts_hash_list=list, num_jobs=4) -> None:
        self.timer("Para-session download")

        # split tasklets evenly for jobs
        task_per_job = len(ts_hash_list) // num_jobs
        assignments  = [ ( ts_hash_list[i:i+task_per_job] if (i == num_jobs) else ts_hash_list[i:]) for i in range(num_jobs)]

        # Multi-threading
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(session_downloads, assignments[n], self.header) for n in range(num_jobs)]
            # Wait for all tasks to complete
            concurrent.futures.wait(futures)

        self.timer("Para-session download")

    # ts_hash_list = [(url, dir, file_name)...]
    def __parallel_download_with_joblib(self, ts_hash_list=list) -> None:
        '''With Joblib'''
        # fname = re.search(r'\/([^\/\?]+)(\?[^\/]*)?$', url).group(1) 
        self.timer("Para download")
        print(f"Num of downloaders: {self.num_jobs}")

        tasks = [ \
                    delayed(self.__vanilla_download_with_progress) \
                    ( url=x['url'], header=self.header, out_path=os.path.join(x['dir'],x['name']), suppress_fail=self.skip_fail ) \
                    for x in ts_hash_list \
                ]
        self.num_tasks = len(tasks)
        self.num_tasks_left = len(tasks)
        print("Progress: " + "=" * int(1/self.report_freq + 2) + ">")
        print("          ", end="")

        skip_list = Parallel(n_jobs=self.num_jobs, backend='threading', require="sharedmem")(tasks)
        print("")

        self.skip_set = set( [i for i in skip_list if i is not None] )

        if self.opt_v or self.skip_fail:
            for skip in self.skip_set: print(f"  {skip}")
            print("Download Failures =", len(self.skip_set))

            # check skip tolerance 5% hardcoded
            if len(self.skip_set) > self.num_tasks * 0.05:
                print("Exceed download failure tolerance 5%\nExiting...")
                exit()

        self.timer("Para download")

    # Helper_method to provide progress bar like functionality (not refreshing terminal)
    def __vanilla_download_with_progress(self, url=str, header=dict, out_path=os.path or str, 
                     suppress_fail=False, retry=3, timeout=3):
        rc = vanilla_download(url=url, header=header, out_path=out_path, suppress_fail=suppress_fail)
        self.num_tasks_left -= 1
        if (self.num_tasks - self.num_tasks_left) % int(self.num_tasks * self.report_freq) == 0:   # report every 10%
            print("=", end="")
        return rc

    # ts_hash_list = [(url, dir, file_name)...]
    def __parallel_download_with_progress_bar(self, ts_hash_list=list) -> None:
        '''With tqdm thread_map'''
        # fname = re.search(r'\/([^\/\?]+)(\?[^\/]*)?$', url).group(1) 
        self.timer("Para download")
        print(f"Number of downloaders: {self.num_jobs}")

        kargs_list = [ { 'url':x['url'], 'header':self.header, 'out_path':os.path.join(x['dir'],x['name']), 'suppress_fail':self.skip_fail } for x in ts_hash_list ]
        skip_list = thread_map(vanilla_download_with_dict, kargs_list)
        
        self.skip_set = set( [i for i in skip_list if i is not None] )
        if self.opt_v or self.skip_fail:
            print("Download Failures =", len(self.skip_set))
            for skip in self.skip_set: print(f"  {skip}")

        self.timer("Para download")

    def __concat_ts(self, ts_paths=list, ts_comb_path=str) -> None:
        self.timer("Concat ts files") 
        
        with open(ts_comb_path, 'wb') as wfd:
            for f in ts_paths:
                if self.skip_fail and f in self.skip_set:
                    pass
                else:
                    with open(f, 'rb') as fd:
                        shutil.copyfileobj(fd, wfd)

        self.timer("Concat ts files") 

    def __transcode(self, ts_path=os.path, mp4_path=os.path) -> None:
        self.timer("Transcode ts file") 

        command = f'ffmpeg -i {ts_path} -acodec copy -vcodec copy {mp4_path}'

        # check if output file name exist
        if os.path.exists(mp4_path):
            print("WARN! Output mp4 file name already exists, consider running ffmpeg by hand:")
            print(command)
            print(f"When done, clean up {self.tmp_dir}.\nExiting...")
            exit()

        result = subprocess.run(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        if result.returncode == 0:
            self.timer("Transcode ts file") 
            if self.opt_v: print("Transcode complete.")
        else:
            print("Transcode failed with return code:", result.returncode)
            print("Standard Error:")
            print(result.stderr)
            exit()

    def download_merge_transcode(self) -> None:
        if not os.path.exists( self.tmp_dir ):
            os.mkdir( self.tmp_dir )

        if self.opt_v: 
            print("Host base URL:", self.host_path)
            print("Host mddl URL:", self.middle_path)
        # Get .ts files
        ts_hash_list = self.__get_ts()
        # Concat .ts files
        ts_paths     = [os.path.join(x['dir'],x['name']) for x in ts_hash_list]
        ts_comb_path = os.path.join( self.tmp_dir, 'combined.ts')
        self.__concat_ts(ts_paths=ts_paths, ts_comb_path=ts_comb_path)
        # Transcode .ts to .mp4
        mp4_path = os.path.join( self.out_dir, self.out_name+'.mp4' )
        self.__transcode(ts_comb_path, mp4_path)
        # Clean up
        if self.opt_v: print('Cleaning up tmp dir', self.tmp_dir, '...')
        shutil.rmtree(self.tmp_dir)

    def timer(self, task_name=str) -> None:
        if self.timer_set:
            run_time = round(time.time() - self.timer_cnt, 2)
            print(f"--- {task_name: <30} {run_time}seconds ---")
            self.timer_set  = False
        else:
            self.timer_cnt  = time.time()
            self.timer_set  = True
            
        