
import sys
from pathlib import Path
import queue
import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel

# Make root-level modules importable when this file is run directly.
project_root = Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))


from Organs.brain import Brain

SAMPLE_RATE = 16000
FRAME_DURATION_MS = 100  # 100ms chunks
BLOCK_SIZE = int(SAMPLE_RATE * (FRAME_DURATION_MS / 1000.0))
PHRASE_PAUSE_SECONDS = 0.6  # Silence pause to trigger instant transcription of a phrase
SESSION_TIMEOUT_SECONDS = 4.0  # Continuous silence to conclude session and return all text


def calibrate_threshold(input_queue: queue.Queue, calibration_seconds: float = 1.0) -> float:
    """Measures ambient noise floor to dynamically set speech detection threshold."""
    print("Calibrating ambient noise floor (stay quiet)...")
    frames = []
    num_frames = int(calibration_seconds / (FRAME_DURATION_MS / 1000.0))
    print(f"Expected frames: {num_frames}")

    while len(frames) < num_frames:
        try:
            data = input_queue.get(timeout=0.5)
            frames.append(data)
        except queue.Empty:
            pass

    concatenated = np.concatenate(frames)
    ambient_rms = np.sqrt(np.mean(concatenated**2))
    # Speech threshold set at 2.5x ambient noise, bounded by minimum floor
    threshold = max(ambient_rms * 2.5, 0.015)
    print(f"Calibrated energy threshold: {threshold:.4f}\n")
    return threshold


def transcribe_stream() -> str:
    print("Loading the faster-whisper model on your CUDA (float16)...")
    model = WhisperModel("base.en",
                          device="cuda", 
                          compute_type="float16",
                          local_files_only=True)

    audio_queue = queue.Queue()

    def audio_callback(indata, frames, time_info, status):
        if status:
            pass
        audio_queue.put(indata[:, 0].copy())

    transcript_parts = []
    phrase_buffer = []

    with sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="float32",
        blocksize=BLOCK_SIZE,
        callback=audio_callback,
    ):
        energy_threshold = calibrate_threshold(audio_queue)

        print("Start speaking (session will auto-stop after 4s of silence):\n")
        print("# ------------- EARS are listening ------------- #\n")

        silence_duration = 0.0
        has_spoken_at_least_once = False
        is_speaking = False

        print("[Ears]:")
        while True:
            try:
                frame = audio_queue.get(timeout=0.2)
            except queue.Empty:
                continue

            # Calculate frame RMS energy
            rms = np.sqrt(np.mean(frame**2))

            if rms >= energy_threshold:
                # Voice detected
                is_speaking = True
                has_spoken_at_least_once = True
                silence_duration = 0.0
                phrase_buffer.append(frame)
            else:
                # Silence frame
                silence_duration += FRAME_DURATION_MS / 1000.0

                if is_speaking:
                    phrase_buffer.append(frame)

                    # Short pause detected -> transcribe current phrase immediately
                    if silence_duration >= PHRASE_PAUSE_SECONDS:
                        is_speaking = False

                        # Transcribe if accumulated audio is at least 0.4 seconds
                        if len(phrase_buffer) * (FRAME_DURATION_MS / 1000.0) >= 0.4:
                            audio_chunk = np.concatenate(phrase_buffer)
                            segments, _ = model.transcribe(
                                audio_chunk,
                                beam_size=1,  # Lowest latency greedy decoding
                                language="en",
                                condition_on_previous_text=False,
                                without_timestamps=True,
                            )
                            text = "".join(segment.text for segment in segments).strip()
                            if text:
                                print(f"{text} ", end="", flush=True)
                                transcript_parts.append(text)

                        phrase_buffer.clear()

                # Session timeout check (triggered after 4s of quiet once speech began)
                if has_spoken_at_least_once and silence_duration >= SESSION_TIMEOUT_SECONDS:
                    print("\n\n[4 seconds of silence reached. Session ended.]\n")
                    break

    full_transcript = " ".join(transcript_parts).strip()
    return full_transcript


def hear():
    result = transcribe_stream()
    print("--- Final Complete Prompt ---")
    print(result)
    Brain().think(result)


if __name__ == "__main__":
    hear()