import os
import subprocess

from kokoro import KPipeline
import soundfile as sf
import numpy as np

import config

_pipeline = None


def _get_pipeline():
    global _pipeline
    if _pipeline is None:
        _pipeline = KPipeline(lang_code=config.TTS_LANG)
    return _pipeline


def text_to_audio(script, output_path):
    """
    Convert text to an MP3 file.
    output_path: Path object or string (without extension — .mp3 will be added).
    """
    output_path = str(output_path)
    wav_path = f"{output_path}.wav"
    mp3_path = f"{output_path}.mp3"

    pipeline = _get_pipeline()
    generator = pipeline(script, voice=config.TTS_VOICE, speed=config.TTS_SPEED)
    audio_chunks = []
    for _, _, audio in generator:
        audio_chunks.append(audio)
    audio = np.concatenate(audio_chunks)
    sf.write(wav_path, audio, 24000)

    # Convert to MP3 via ffmpeg
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-i", wav_path, "-q:a", "2", mp3_path],
            capture_output=True,
            check=True,
        )
        os.remove(wav_path)
    except FileNotFoundError:
        print("  ⚠️  ffmpeg not found — keeping WAV file instead.")
        return wav_path
    except subprocess.CalledProcessError as e:
        print(f"  ⚠️  ffmpeg error: {e.stderr.decode()}")
        return wav_path

    return mp3_path


def generate_article_audio(source, title, summary, article_text, output_path,
                          is_long=False):
    """
    Build a podcast-style script from summary + article, then convert to audio.
    When is_long is True, article_text is an extended summary and the full
    article is omitted.
    """
    if is_long:
        script = (
            f"A new article from {source}: {title}.\n\n"
            f"Here's a quick summary: {summary}\n\n"
            f"Here's a more detailed summary of the article.\n\n"
            f"{article_text}"
        )
    else:
        script = (
            f"A new article from {source}: {title}.\n\n"
            f"Here's a quick summary: {summary}\n\n"
            f"And now, the full article.\n\n"
            f"{article_text}"
        )
    return text_to_audio(script, output_path)