import os
import sys
import warnings
from pathlib import Path

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

# Make root-level packages importable when this file is run directly.
project_root = Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))


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

    # Use a context manager to ensure the output stream is properly closed after use
    with sd.OutputStream(samplerate=24000, channels=1, dtype="float32") as output:
        print("\n# ------------- MOUTH is speaking ------------- #", flush=True)
        print(f"[Mouth]---\nFinal response: {reply}", flush=True)
    
        for _, _, audio in pipeline(
            reply,
            voice=voice,
            speed=speed,
            split_pattern=r"(?<=[.!?])\s+",
        ):
            
            if audio is None or isinstance(audio, str): # Skip if audio is None or an error message
                continue
            
            if hasattr(audio, "cpu"): # Convert PyTorch tensor to NumPy array if it's a tensor
                audio = audio.cpu().numpy()
            
            audio_array = np.asarray(audio, dtype=np.float32).reshape(-1, 1) # Ensure audio is a 2D array for the output stream
            
            if audio_array.size: # Only write to the output stream if the audio array is not empty
                output.write(audio_array)

if __name__ == "__main__":
    speak("Voice is assigned and working.")
    speak("This is an example of text-to-speech synthesis using the Kokoro library to check my speech output.")