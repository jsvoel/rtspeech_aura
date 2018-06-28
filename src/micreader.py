import pyaudio, math, os, shutil, wave, webrtcvad
from collections import deque
from threading import Event

#bla bla bla
class MicReader:
    def __init__(self, micname, buffersize_sec, vadcallback, vadattacktime, vadholdtime, vadaggro, debug=False):
        self._audio = pyaudio.PyAudio()
        self._debug = MicDebug(debug)
        if micname is None:
            micname = self._audio.get_default_input_device_info()['name']
        self._micname = micname
        self._rate = 16000
        chunksperframeforvad = 4
        self._chunksize = self._rate * chunksperframeforvad / 1000 * 30
        self._channels = 1
        self._format = pyaudio.paInt16
        self._sampwidth = 2
        self._stream = None
        self._buffer = deque(maxlen=math.ceil((buffersize_sec * self._rate) / self._chunksize)) # round up to chunksize
        self._streaming = False
        self._event_newdata = Event()
        self._vad = WebrtcVad(self._rate, chunksperframeforvad, vadcallback, vadattacktime, vadholdtime, vadaggro)

    def __exit__(self, type, value, traceback):
        self.stop()
        self._audio.terminate()

    def start(self):
        devindex = self._get_device_index(self._micname)
        if not self._audio.is_format_supported(self._rate, devindex, self._channels, self._format,
                                               None, None, None):
            raise ValueError("Microphone input parameters not supported")
        self._stream = self._audio.open(self._rate, self._channels, self._format, True, False,
                                        devindex, frames_per_buffer=self._chunksize, stream_callback=self._callback)

    def stop(self):
        if self._stream is not None:
            self._stream.stop_stream()
            self._stream.close()
            self._stream = None
        self._streaming = False
        self._buffer.clear()
        self._event_newdata.set()

    def running(self):
        return self._stream.is_active() if self._stream else False

    def start_generation(self):
        if not self.running():
            self.start()
        self._streaming = True
        return self._generator()

    def stop_generation(self):
        self._streaming = False
        self._event_newdata.set()

    def _generator(self):
        self._debug.startNew()
        while True:
            while len(self._buffer) == 0: # block until we get any data
                self._event_newdata.wait()
                if not (self._streaming and self.running()):
                    break;
            if not (self._streaming and self.running()):
                break;
            # try to as much data as possible before yielding
            data = []
            while len(self._buffer):
                data.append(self._buffer.popleft())
            # pass the data out of the generator before returning to the start of the loop
            data = b''.join(data)
            self._debug.write(data)
            yield data
        self._debug.done()

    def _get_device_index(self, name):
        devcount = self._audio.get_device_count()
        for i in range(devcount):
            devinfo = self._audio.get_device_info_by_index(i)
            if name in devinfo['name']:
                return devinfo['index']
        raise ValueError("Microphone with name: " + name + " not found")

    def _callback(self, in_data, frame_count, time_info, status):
        # fill the buffer, if streaming also assert the signal
        if frame_count:
            self._buffer.append(in_data)
            self._event_newdata.set()
            self._vad.process(in_data)
            #for i in xrange(0, self._datachunksize, self._vadchunksize):
        return (None, pyaudio.paContinue)

class WebrtcVad:
    def __init__(self, rate, chunks, cb, attack, hold, aggro):
        self._rate = rate
        self._chunks = chunks
        self._maxlen = ((rate * 2)/1000)*30 # 30 milliseconds
        self._chunkidx = range(0, self._maxlen*chunks, self._maxlen)
        self._cb = cb
        self._vad = webrtcvad.Vad(aggro)
        self._active = False
        self._framesforstart = int(math.ceil(attack / 0.03))
        self._framestoend = int(math.ceil(hold / 0.03))
        self._startframes = 0
        self._endframes = 0

    def process(self, frames):
        for i in self._chunkidx:
            if self._vad.is_speech(frames[i:i+self._maxlen], self._rate):
                if self._active: # we are active and speech is detected. increment holdtime if necessary
                    if self._endframes < self._framestoend:
                        self._endframes += 1
                else: # not active but speech detected. increment detect counter and activate if necessary
                    self._startframes += 1
                    if self._startframes >= self._framesforstart:
                        self._active = True
                        self._startframes = 0
                        self._endframes = self._framestoend
                        self._cb(True)
            else: # frame is not speech
                if self._active:
                    self._endframes -= 1
                    if self._endframes <= 0: # endframes exhausted, end activity
                        self._active = False
                        self._cb(False)
                elif self._startframes > 0:
                    self._startframes -= 1

class MicDebug:
    def __init__(self, enabled):
        self._filenum = 0
        self._path = "." + os.sep + "miccap"
        self._fname = self._path + os.sep + "record_{}.wav"
        self._channels = 1
        self._sampwidth = 2
        self._rate = 16000
        self._file = None
        if enabled:
            if os.path.isdir(self._path):
                shutil.rmtree(self._path, ignore_errors=True)
            os.mkdir(self._path)
            self._filenum = 1

    def startNew(self):
        if self._filenum:
            self._file = wave.open(self._fname.format(self._filenum), 'wb')
            self._file.setnchannels(self._channels)
            self._file.setsampwidth(self._sampwidth)
            self._file.setframerate(self._rate)
            self._filenum += 1

    def write(self, data):
        if self._file:
            self._file.writeframes(data)

    def done(self):
        if self._file:
            self._file.close()
            self._file = None
