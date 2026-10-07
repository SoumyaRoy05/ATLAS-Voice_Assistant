import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from faster_whisper import WhisperModel

# -----------------------------------------------------------------------------
# 1. Hardware Acceleration & Dynamic Environment Setup
# -----------------------------------------------------------------------------
# Inject NVIDIA CUDA and cuBLAS DLL binaries into the Windows runtime path
nvidia_dir = Path(sys.prefix) / "Lib" / "site-packages" / "nvidia"
if nvidia_dir.exists():
    for bin_folder in nvidia_dir.rglob("bin"):
        if bin_folder.is_dir():
            os.add_dll_directory(str(bin_folder))
            os.environ["PATH"] = str(bin_folder) + os.pathsep + os.environ.get("PATH", "")

# Locate and load environment variables from the project root .env
root_dir = Path(__file__).resolve().parent
load_dotenv(dotenv_path=root_dir / ".env")

# Route Hugging Face models to a user-specific cache unless explicitly configured.
if not os.getenv("HF_HOME"):
    local_app_data = os.getenv("LOCALAPPDATA")
    cache_root = Path(local_app_data) if local_app_data else Path.home() / ".cache"
    os.environ["HF_HOME"] = str(cache_root / "Atlas" / "huggingface")


# -----------------------------------------------------------------------------
# 2. Sensory Organ Import
# -----------------------------------------------------------------------------
from Organs.ears import hear  # Auditory sensory organ: wake word detection + speech-to-text
from Organs.mouth import speak  # Vocal organ: text-to-speech synthesis
from Organs.brain import Brain
from Behaviour.persona import get_wake_receipt


# -----------------------------------------------------------------------------
# 3. Central Nervous System Lifecycle Supervisor
# -----------------------------------------------------------------------------
def main() -> None:
    """Master ignition routine for Atlas.

    Initializes hardware contexts, boots the acoustic sensory organ,
    and supervises the event loop until clean termination.
    """
    print("\n")
    print("=" * 60)
    print("               ATLAS DIGITAL STEWARD ONLINE                 ")
    print("=" * 60)
    print("\n")

    try:
        print("------- Central Nervous System [CNS] Engaged -------")
        print("[CNS] Initializing acoustic and cognitive subsystems...")

        # the brain instance stores the mouth function for later use in the conversation loop
        brain = Brain(mouth=speak)
        wake_receipt = get_wake_receipt()
        brain.remember_assistant_message(wake_receipt) # Remember the wake receipt in the brain's history
        speak(wake_receipt)

        print("[CNS] Ignition sequence complete. Acoustic sensory organ active.")
        print("Loading the faster-whisper model on your CUDA (float16)...")
        whisper_model = WhisperModel(
            "base.en",
            device="cuda",
            compute_type="float16",
            local_files_only=True,
        )

        # Reuse one Brain and one Whisper model for the complete session.
        while True:
            transcript = hear(whisper_model)
            if transcript:
                brain.think(transcript)

    except KeyboardInterrupt:
        print("\n[CNS] Manual keyboard interrupt received. Commencing safe teardown...")

    except SystemExit:
        print("\n[CNS] System power-down command confirmed. Standing down...")

    except Exception as e:
        print(f"\n[CNS - Critical Fault]: Unhandled pipeline exception: {e}")

    finally:
        print("[CNS] Audio hardware unhooked. GPU contexts released. System offline.")



if __name__ == "__main__":
    main()