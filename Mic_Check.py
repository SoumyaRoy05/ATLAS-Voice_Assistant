import sys
import numpy as np
import sounddevice as sd

def test_microphone():
    print("=" * 55)
    print("AUDIO INPUT DEVICE")
    print("=" * 55)

    try:
        device_info = sd.query_devices(kind="input")
        print(f"Device Name : {device_info['name']}")
        print(f"Sample Rate : {int(device_info['default_samplerate'])} Hz")
        print(f"Channels    : {device_info['max_input_channels']}")
    except Exception as e:
        print(f"Failed to query audio devices: {e}")
        return

    print("\n" + "=" * 55)
    print("MONITORING LIVE INPUT (Press Ctrl+C to exit)")
    print("Speak into your mic to test responsiveness.")
    print("=" * 55 + "\n")

    bar_width = 30

    def audio_callback(indata, frames, time, status):
        if status:
            print(f"\nStream status: {status}", file=sys.stderr)
        
        # Calculate Root Mean Square (RMS) amplitude
        rms = np.sqrt(np.mean(indata**2))
        
        # Scale RMS into a visual ASCII meter
        scaled_level = int(min(rms * 10, 1.0) * bar_width)
        bar = "█" * scaled_level + "-" * (bar_width - scaled_level)
        status_label = "RECEIVING AUDIO" if rms > 0.01 else "WAITING / QUIET"

        print(f"\r[{bar}] RMS: {rms:0.4f} | {status_label}", end="", flush=True)

    try:
        with sd.InputStream(callback=audio_callback, channels=1):
            while True:
                sd.sleep(100)
    except KeyboardInterrupt:
        print("\n\nSession terminated by user.")
    except Exception as e:
        print(f"\nMicrophone stream error: {e}")

if __name__ == "__main__":
    test_microphone()