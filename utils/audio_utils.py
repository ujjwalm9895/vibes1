import pyaudio, wave, os
from tempfile import NamedTemporaryFile
from faster_whisper import WhisperModel

SAMPLE_RATE = 16000
CHANNELS = 1
CHUNK = 1024
DURATION = 2

model = WhisperModel("base.en", compute_type="int8")

def record_and_transcribe():
    with NamedTemporaryFile(delete=False, suffix=".wav") as temp:
        path = temp.name
        p = pyaudio.PyAudio()
        stream = p.open(format=pyaudio.paInt16,
                        channels=CHANNELS,
                        rate=SAMPLE_RATE,
                        input=True,
                        frames_per_buffer=CHUNK)
        frames = [stream.read(CHUNK) for _ in range(0, int(SAMPLE_RATE / CHUNK * DURATION))]
        stream.stop_stream()
        stream.close()
        p.terminate()

        with wave.open(path, 'wb') as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(p.get_sample_size(pyaudio.paInt16))
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(b''.join(frames))

    segments, _ = model.transcribe(path)
    os.remove(path)
    return " ".join([s.text for s in segments]) if segments else ""
