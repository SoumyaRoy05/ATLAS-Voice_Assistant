import os
import warnings

import numpy as np
from dotenv import load_dotenv

load_dotenv()

warnings.filterwarnings(
    "ignore",
    message=r"dropout option adds dropout after all but last recurrent layer.*",
    category=UserWarning,
)
warnings.filterwarnings(
    "ignore",
    message=r".*torch\.nn\.utils\.weight_norm.*deprecated.*",
    category=FutureWarning,
)

# -------------------------------------------------------------- MAIN MOUTH PIPELINE -------------------------------------------------------------- 

# Kokoro is already cached locally in this environment. Avoid unauthenticated
# Hub requests unless the user explicitly provides an HF token.
if not os.getenv("HF_TOKEN"):
    os.environ.setdefault("HF_HUB_OFFLINE", "1")

import sounddevice as sd
from kokoro import KPipeline

# Keep the pipeline outside so the model stays in RAM
pipeline = KPipeline(lang_code="b", repo_id="hexgrad/Kokoro-82M")

def speak(text: str):
    if not text or not text.strip():
        return

    reply = text.strip()
    # Defined locally inside the function
    voice = "bm_fable"
    speed = 1.25

    print("# ------------- MOUTH is speaking ------------- #", flush=True)
    print(f"[Mouth]: Final response: {reply}", flush=True)

    with sd.OutputStream(samplerate=24000, channels=1, dtype="float32") as output:
        for _, _, audio in pipeline(
            reply,
            voice=voice,
            speed=speed,
            split_pattern=r"(?<=[.!?])\s+",
        ):
            if audio is None or isinstance(audio, str):
                continue
            if hasattr(audio, "cpu"):
                audio = audio.cpu().numpy()
            audio_array = np.asarray(audio, dtype=np.float32).reshape(-1, 1)
            if audio_array.size:
                output.write(audio_array)

if __name__ == "__main__":
    speak("Voice is assigned and working.")
    speak("This is an example of text-to-speech synthesis using the Kokoro library to check my speech output.")