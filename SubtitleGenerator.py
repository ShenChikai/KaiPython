import os
from sys import stderr
from pydub import AudioSegment          # for audio extraction from video file
import speech_recognition as sr         # from Google
from googletrans import Translator      # from Google, version can cause issue: pip install googletrans==3.1.0a0
import shutil                           # for cleanup
from joblib import Parallel, delayed    # for parallel execution
import time                             # performance analysis
import subprocess

# KaiPython needs to be added if not in site-packages
    # import sys
    # sys.path.insert(0, r'path_to_KayPython')
from KaiPython.Misc import get_file_barename, default_download_path

# Helper function to parallel a class method (this is genius)
#   credit to Qingkai Kong: http://qingkaikong.blogspot.com/2016/12/python-parallel-method-in-class.html
def process_chunk_wrapper( arg, **kwarg ):
    SubtitleGenerator.process_chunk( *arg, **kwarg  )

# SubtitleGenerator class
#   The class generates subtitle using fixed time interval, which might not be the best idea
class SubtitleGenerator:
    def __init__( self, chunk_size=3, verbose=False, parallel=False, num_jobs=-1 )->None:
        # speech recognition obj init
        self.__recognizer   = sr.Recognizer()
        self.__translator   = Translator()
        self.parallel       = parallel
        self.num_jobs       = num_jobs
        self.barename       = 'TBD'         # to-be-decided
        self.chunk_size     = chunk_size    # in seconds
        self.opt_v          = verbose
    
    def generate_subtitle(self, src_file_path=str or os.path, out_dir=default_download_path(), 
                          in_lang=str, out_lang='en',
                          embed=False)->None:
        # Set the in_lang, out_lang, out_dir
        self.out_dir  = out_dir
        self.in_lang  = in_lang
        self.out_lang = out_lang
        self.barename = get_file_barename(src_file_path)
        self.embed    = embed

        # Create a directory to store chunked audio files
        self.chunk_dir = os.path.join( self.out_dir, 'audio_chunks_'+str(time.time()).replace('.',''))
        if not os.path.exists( self.chunk_dir ):
            os.mkdir( self.chunk_dir )

        # Extract audio from video
        self.audio_clip = AudioSegment.from_file( src_file_path )

        # Split the audio into chunks and transcribe
        self.total_duration = len(self.audio_clip) // 1_000             # in seconds
        self.num_chunks = int(self.total_duration / self.chunk_size) + 1
        if self.opt_v: print(f'Number of chunks = {self.num_chunks}')

        self.subtitle_lines = []  # Store subtitle lines for the entire video

        # Performance Analysis
        performance_start_time = time.time()    

        # Parallel | Serial
        if self.parallel:
            if self.opt_v:
                if self.num_jobs == -1:
                    print("Parallel mode: multi-threading =", os.cpu_count())
                else:
                    print("Parallel mode: multi-threading =", self.num_jobs)
            tasks = [ delayed(process_chunk_wrapper)(tpl) for tpl in zip( [self] * self.num_chunks, range(self.num_chunks) ) ]
            Parallel(n_jobs=self.num_jobs, backend='threading', require="sharedmem")(tasks)
            # Sort (Parallel jobs does not append in order
            self.subtitle_lines = sorted( self.subtitle_lines, key=lambda x: x['index'] )
        else:
            for idx in range(self.num_chunks):
                self.process_chunk(idx=idx)

        # Performance Analysis
        print("--- %s seconds ---" % (time.time() - performance_start_time))

        # Write .srt subtitle file after translation iteration ends
        out_path = self.__write_to_file(subtitle_lines=self.subtitle_lines)

        # Clean up temporary audio files
        if self.opt_v: print('Cleaning up tmp dir', self.chunk_dir, '...')
        shutil.rmtree(self.chunk_dir)

        # Embed to video
        if self.embed:
            self.embed_to_video(src_file_path=src_file_path, out_path=out_path)

    def embed_to_video( self, src_file_path=str or os.path, out_path=str or os.path ) -> None:
        orig_name = os.path.basename(src_file_path)
        split_name_list = str(orig_name).split('.')
        split_name_list.insert(-1,'subtitled')
        new_name  = '.'.join(split_name_list)
        new_path  = os.path.join(self.out_dir, new_name)
        command = f'ffmpeg -i {src_file_path} -vf \"subtitles={out_path}\" {new_path}'
        result = subprocess.run(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        if result.returncode == 0:
            if self.opt_v: print("Subtitle embedding complete.")
        else:
            print("Subtitle embedding failed with return code:", result.returncode)
            print("Standard Error:")
            print(result.stderr)
            exit()

    def process_chunk( self, idx=int )->None:   # had to make this public b/c of the parallel wrapper func
        start_time  = idx * self.chunk_size
        end_time    = min((idx + 1) * self.chunk_size, self.total_duration)
        chunk_audio = self.audio_clip[ start_time * 1_000 : end_time * 1_000 ]  # pydub use unit in milsec

        # Save the chunked audio as a temporary WAV file
        temp_audio_file = os.path.join( self.chunk_dir, f'chunk_{idx}.wav' )
        chunk_audio.export(temp_audio_file, format='wav')

        # Translate
        transcript, translated = self.__translate( audio_data_file=temp_audio_file )

        # Verbose progress tracking
        if self.opt_v and transcript != '':
            print(f"[{idx}/{self.num_chunks}]: [{start_time}s=>{end_time}s]\n# {transcript}\n# {translated}")

        # Append the chunk's transcript to the subtitle lines
        self.subtitle_lines.append({
            'index': idx + 1,
            'start_time': start_time,
            'end_time': end_time,
            'transcript': transcript,
            'translated': translated,
        })

    def __translate( self, audio_data_file=str, retry=3 )->str:
        # Perform speech recognition
        for _ in range(retry):
            try:
                # Load the temporary audio file and transcribe it
                with sr.AudioFile(audio_data_file) as source:
                    audio_data = self.__recognizer.record(source)

                transcript = self.__recognizer.recognize_google(audio_data, language = self.in_lang) #, show_all = True)

                # Translate the transcript using googletrans
                translated_text = self.__translator.translate(text=transcript, dest=self.out_lang)

                return (transcript, translated_text.text)

            except sr.UnknownValueError:
                # Might just be silence...
                if self.opt_v:
                    print("@ Speech Recognition could not understand the audio. might be silence", file=stderr)
                return ('', '')
            
            except sr.RequestError as e:
                print(f"@ Could not request results from Google Speech Recognition service; {e}", file=stderr)
                return ('', '')
            
            except Exception as e:
                print(f"Retrying on unexpected exception: {e}", file=stderr)

    def __write_to_file( self, subtitle_lines=list )->None:
            # expected struct
            # [
            #     {
            #         'index': idx,
            #         'start_time': start_time,
            #         'end_time': end_time,
            #         'transcript': transcript,
            #         'translated': translated
            #     }
            # ]

        # Construct output path
        out_path = os.path.join( self.out_dir, self.barename + '.srt' )
        # Write the subtitle lines to the output SRT file
        with open(out_path, 'w', encoding='utf-8') as subtitle_file:
            for line in subtitle_lines:
                start_time_str = '{:02}:{:02}:{:02},000'.format(line['start_time'] // (60 * 60),
                                                                (line['start_time'] % (60 * 60)) // 60,
                                                                line['start_time'] % 60)
                end_time_str = '{:02}:{:02}:{:02},000'.format(line['end_time'] // (60 * 60),
                                                                (line['end_time'] % (60 * 60)) // 60,
                                                                line['end_time'] % 60)
                subtitle_file.write(f"{line['index']}\n")
                subtitle_file.write(f"{start_time_str} --> {end_time_str}\n")
                subtitle_file.write(f"{line['transcript']}\n{line['translated']}\n")
                subtitle_file.write("\n")

        print(f"Subtitle file saved as '{out_path}'.")
        return out_path
    
