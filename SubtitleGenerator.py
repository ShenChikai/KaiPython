import os
from pathlib import Path
import moviepy.editor as mp
import speech_recognition as sr         # from Google
from googletrans import Translator      # from Google, version can cause issue: pip install googletrans==3.1.0a0
import shutil

def get_parent_dir( path=str ):
    return Path( path ).parent.absolute()

def get_file_barename( path=str ):
    return os.path.splitext( os.path.basename( path ) )[0]

# subtitleGenerator class
class SubtitleGenerator:
    def __init__( self, chunk_size=2, verbose=False )->None:
        # speech recognition obj init
        self.recognizer     = sr.Recognizer()
        self.translator     = Translator()
        self.chunk_size     = chunk_size    # in seconds
        self.tasklet_time   = 0             # TODO
        self.stddev         = 1
        self.opt_v          = verbose
    
    def generate_subtitle(self, src_path=str, out_path=str, in_lang='ja', out_lang='zh-CN')->None:
        # Set the in_lang, out_lang, out_dir
        self.in_lang = in_lang
        self.out_lang = out_lang
        self.out_path = out_path
        self.out_dir = get_parent_dir( out_path )

        # Create a directory to store chunked audio files
        chunk_dir = os.path.join( self.out_dir, 'audio_chunks')
        if not os.path.exists( chunk_dir ):
            os.mkdir( chunk_dir )

        # Load the video and extract audio
        video_clip = mp.VideoFileClip( src_path )
        audio_clip = video_clip.audio

        # Define chunk size in seconds (adjust as needed)
        chunk_size = self.chunk_size  # Set to a value that works for your audio file

        # Split the audio into chunks and transcribe
        total_duration = audio_clip.duration
        num_chunks = int(total_duration / chunk_size) + 1
        print(f'Number of chunks = {num_chunks}')

        subtitle_lines = []  # Store subtitle lines for the entire video

        # Iterate chunks
        for i in range(num_chunks):
            start_time = i * chunk_size
            end_time = min((i + 1) * chunk_size, total_duration)
            chunk_audio = audio_clip.subclip(start_time, end_time)

            # Save the chunked audio as a temporary WAV file
            temp_audio_file = os.path.join( chunk_dir, f'chunk_{i}.wav' )
            chunk_audio.write_audiofile(temp_audio_file, codec='pcm_s16le', verbose=False, logger=None)

            # translate
            translated_transcript = self.translate( audio_data_file=temp_audio_file, idx=i )

            # Append the chunk's transcript to the subtitle lines
            subtitle_lines.append({
                'index': i + 1,
                'start_time': start_time,
                'end_time': end_time,
                'transcript': translated_transcript
            })

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
                subtitle_file.write(f"{line['transcript']}\n")
                subtitle_file.write("\n")

        print(f"Subtitle file saved as '{out_path}'.")

        # Clean up temporary audio files
        print('- Cleaning up', chunk_dir, '...')
        shutil.rmtree(chunk_dir)

    def translate( self, audio_data_file=str, idx=int )->str:
        # Perform speech recognition
        try:
            # Load the temporary audio file and transcribe it
            with sr.AudioFile(audio_data_file) as source:
                audio_data = self.recognizer.record(source)

            transcript = self.recognizer.recognize_google(audio_data, language = self.in_lang) #, show_all = True)
            if self.opt_v: print("Transcript: ", transcript)

            # Translate the transcript using googletrans
            translated_text = self.translator.translate(text=transcript, dest=self.out_lang)
            translated_transcript = translated_text.text

            if self.opt_v: print(f"{idx}: {transcript}\n=>\t{translated_transcript}")

            return translated_transcript

        except sr.UnknownValueError:
            print("Speech Recognition could not understand the audio.")
            return ''
        
        except sr.RequestError as e:
            print(f"Could not request results from Google Speech Recognition service; {e}")
            return ''
