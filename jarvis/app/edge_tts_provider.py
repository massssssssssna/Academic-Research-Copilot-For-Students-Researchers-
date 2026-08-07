import io
import av
import edge_tts
import asyncio
from livekit.agents import tts

class EdgeTTS(tts.TTS):
    def __init__(self, voice: str = "en-US-AvaNeural", sample_rate: int = 24000):
        super().__init__(capabilities=tts.TTSCapabilities(streaming=False), sample_rate=sample_rate, num_channels=1)
        self._voice = voice


    def synthesize(self, text: str, *, conn_options=None) -> tts.ChunkedStream:
        return EdgeTTSStream(self, text, self._voice, self.sample_rate)

class EdgeTTSStream(tts.ChunkedStream):
    def __init__(self, tts_instance: tts.TTS, text: str, voice: str, sample_rate: int):
        super().__init__(tts=tts_instance, input_text=text)
        self._text = text
        self._voice = voice
        self._sample_rate = sample_rate

    async def _run(self, output_emitter: tts.AudioEmitter) -> None:
        c = edge_tts.Communicate(self._text, self._voice)
        b = bytearray()
        async for ch in c.stream():
            if ch["type"] == "audio":
                b.extend(ch["data"])
        
        if not b:
            return

        container = av.open(io.BytesIO(b))
        resampler = av.AudioResampler(format="s16", layout="mono", rate=self._sample_rate)
        for frame in container.decode(audio=0):
            for resample_frame in resampler.resample(frame):
                pcm_bytes = resample_frame.to_ndarray().tobytes()
                output_emitter.push(pcm_bytes)
