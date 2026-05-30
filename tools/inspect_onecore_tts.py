import asyncio

from winrt.windows.media.speechsynthesis import SpeechSynthesizer


async def main() -> None:
    synth = SpeechSynthesizer()
    voices = [voice for voice in SpeechSynthesizer.all_voices if voice.language == "vi-VN"]
    print([(voice.display_name, voice.language) for voice in voices])
    synth.voice = voices[0]
    stream = await synth.synthesize_text_to_stream_async("Xin chào. Đây là bản thử giọng.")
    print(type(stream), stream.size)
    print([name for name in dir(stream) if not name.startswith("_")])


asyncio.run(main())
