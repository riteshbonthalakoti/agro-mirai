"""``AI4BharatVoiceService`` — the live v1 ``VoiceService`` implementation.

Per ``specs/core/voice-interface.md``, backed by three AI4Bharat models,
none of which match the module prompt's original per-capability pick
1:1 — each substitution is forced by a real gap, documented here and in
``docs/architecture.md``:

- **Translation** — IndicTrans2 distilled 200M
  (``ai4bharat/indictrans2-en-indic-dist-200M`` for en->kn,
  ``ai4bharat/indictrans2-indic-en-dist-200M`` for kn->en). As specced.
- **Speech-to-text** — ``ai4bharat/indic-conformer-600m-multilingual``
  for `kn` (IndicWav2Vec, the originally-named backend, has no Kannada
  checkpoint) and ``openai/whisper-tiny.en`` for `en` (AI4Bharat's ASR
  line is Indian-languages-only by design; it ships no English model at
  all, so there is no AI4Bharat option to substitute in — this is the
  one non-AI4Bharat component in the adapter).
- **Text-to-speech** — Piper for `en` (as specced) and
  ``ai4bharat/vits_rasa_13`` for `kn` (Piper has no Kannada voice in its
  published voice set).

All three translation/ASR/TTS models load lazily and are cached on the
instance — constructing ``AI4BharatVoiceService()`` does no model I/O.
"""
from __future__ import annotations

import io
from pathlib import Path

from agro_mirai.voice.interface import (
    UnsupportedLanguageError,
    V1_LANGUAGES,
    VoiceUnavailableError,
)

#: ISO 639-1 -> FLORES-200 tag, for the two languages IndicTrans2 calls
#: are made against in v1.
_FLORES_TAGS = {"en": "eng_Latn", "kn": "kan_Knda"}

#: VITS speaker/style ids for ai4bharat/vits_rasa_13 Kannada synthesis.
#: KAN_F (id 8), BOOK style (neutral, id 3) — see the model's README
#: speaker/style table. No speaker selection is exposed through
#: VoiceService; this is a fixed, documented default for v1.
_VITS_KANNADA_SPEAKER_ID = 8
_VITS_KANNADA_STYLE_ID = 3

#: IndicConformer is loaded by HF repo id, not the local snapshot path in
#: models/voice/ — its bundled model_onnx.py `from_pretrained` calls
#: `snapshot_download(repo_id=pretrained_model_name_or_path, ...)`
#: unconditionally, so a local directory path fails HF's repo-id
#: validation. Passing the repo id makes it use (and populate, on first
#: run) the default `~/.cache/huggingface/hub` cache instead — offline
#: after that first run, same as every other model here.
_INDIC_CONFORMER_REPO_ID = "ai4bharat/indic-conformer-600m-multilingual"


class AI4BharatVoiceService:
    def __init__(self, model_dir: str | Path = "models/voice"):
        self._model_dir = Path(model_dir)
        self._translate_models: dict[tuple[str, str], tuple] = {}
        self._indic_processor = None
        self._indic_conformer_model = None
        self._whisper_en_pipeline = None
        self._whisper_lid_processor = None
        self._whisper_lid_model = None
        self._piper_en_voice = None
        self._vits_kn_model = None
        self._vits_kn_tokenizer = None

    # -- VoiceService ------------------------------------------------

    def translate(self, text: str, source_lang: str, target_lang: str) -> str:
        self._check_supported(source_lang)
        self._check_supported(target_lang)
        if source_lang == target_lang:
            return text

        tok, model = self._get_translate_model(source_lang, target_lang)
        ip = self._get_indic_processor()
        src_tag = _FLORES_TAGS[source_lang]
        tgt_tag = _FLORES_TAGS[target_lang]

        import torch

        batch = ip.preprocess_batch([text], src_lang=src_tag, tgt_lang=tgt_tag)
        inputs = tok(batch, truncation=True, padding="longest", return_tensors="pt")
        with torch.no_grad():
            generated = model.generate(
                **inputs, use_cache=True, min_length=0, max_length=256, num_beams=5
            )
        decoded = tok.batch_decode(
            generated, skip_special_tokens=True, clean_up_tokenization_spaces=True
        )
        return ip.postprocess_batch(decoded, lang=tgt_tag)[0]

    def speech_to_text(
        self, audio_bytes: bytes, expected_lang: str | None = None
    ) -> tuple[str, str]:
        if expected_lang is not None:
            self._check_supported(expected_lang)
            lang = expected_lang
        else:
            lang = self._identify_language(audio_bytes)

        if lang == "kn":
            text = self._transcribe_kn(audio_bytes)
        else:
            text = self._transcribe_en(audio_bytes)
        return text, lang

    def text_to_speech(self, text: str, lang: str) -> bytes:
        self._check_supported(lang)
        if lang == "en":
            return self._synthesize_en(text)
        return self._synthesize_kn(text)

    # -- language gate -------------------------------------------------

    def _check_supported(self, lang: str) -> None:
        if lang not in V1_LANGUAGES:
            raise UnsupportedLanguageError(lang, V1_LANGUAGES)

    # -- translation -----------------------------------------------------

    def _get_indic_processor(self):
        if self._indic_processor is None:
            from agro_mirai.voice._indic_processor import IndicProcessor

            self._indic_processor = IndicProcessor(inference=True)
        return self._indic_processor

    def _get_translate_model(self, source_lang: str, target_lang: str):
        direction = (source_lang, target_lang)
        if direction not in self._translate_models:
            if source_lang == "en":
                repo_dir = self._model_dir / "indictrans2-en-indic-dist-200M"
            else:
                repo_dir = self._model_dir / "indictrans2-indic-en-dist-200M"
            if not repo_dir.exists():
                raise VoiceUnavailableError(
                    f"translation model not downloaded: {repo_dir} does not "
                    "exist (see docs/TOOLING.md for the hf download command)"
                )
            try:
                from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

                tok = AutoTokenizer.from_pretrained(str(repo_dir), trust_remote_code=True)
                model = AutoModelForSeq2SeqLM.from_pretrained(
                    str(repo_dir), trust_remote_code=True
                )
            except Exception as exc:  # pragma: no cover - defensive
                raise VoiceUnavailableError(f"failed to load translation model: {exc}") from exc
            self._translate_models[direction] = (tok, model)
        return self._translate_models[direction]

    # -- ASR ---------------------------------------------------------

    def _load_audio_16k_mono(self, audio_bytes: bytes):
        import soundfile as sf
        import torch

        data, sr = sf.read(io.BytesIO(audio_bytes), always_2d=True)
        wav = torch.from_numpy(data.T).float()
        wav = torch.mean(wav, dim=0, keepdim=True)
        if sr != 16000:
            import torchaudio

            wav = torchaudio.transforms.Resample(orig_freq=sr, new_freq=16000)(wav)
            sr = 16000
        return wav, sr

    def _transcribe_kn(self, audio_bytes: bytes) -> str:
        if self._indic_conformer_model is None:
            try:
                from transformers import AutoModel

                self._indic_conformer_model = AutoModel.from_pretrained(
                    _INDIC_CONFORMER_REPO_ID, trust_remote_code=True
                )
            except Exception as exc:
                raise VoiceUnavailableError(f"failed to load IndicConformer ASR: {exc}") from exc
        wav, _ = self._load_audio_16k_mono(audio_bytes)
        return str(self._indic_conformer_model(wav, "kn", "ctc"))

    def _transcribe_en(self, audio_bytes: bytes) -> str:
        if self._whisper_en_pipeline is None:
            try:
                from transformers import pipeline as hf_pipeline

                self._whisper_en_pipeline = hf_pipeline(
                    "automatic-speech-recognition", model="openai/whisper-tiny.en"
                )
            except Exception as exc:
                raise VoiceUnavailableError(f"failed to load whisper-tiny.en ASR: {exc}") from exc
        import soundfile as sf

        data, sr = sf.read(io.BytesIO(audio_bytes))
        result = self._whisper_en_pipeline({"array": data, "sampling_rate": sr})
        return result["text"].strip()

    def _identify_language(self, audio_bytes: bytes) -> str:
        """Binary en-vs-kn acoustic language ID using whisper-tiny's own
        language-detection mechanism (its first decoder step scores every
        Whisper-supported language as a token), restricted to just the
        two v1 tokens instead of Whisper's full open-ended argmax across
        ~99 languages.

        AI4Bharat has no dedicated audio language-ID model in its public
        catalogue (IndicLID is text-only), and IndicConformer forced into
        a single target language will always emit *something* in that
        language's script regardless of what it's actually hearing — so
        neither AI4Bharat component can be used for this. Whisper-tiny's
        raw (unrestricted) language guess is also not reliable enough on
        its own for Kannada specifically (observed misclassifying
        synthetic Kannada TTS audio as Sinhala in testing) — restricting
        the comparison to only the two languages this project actually
        supports resolves that. See docs/architecture.md for the
        full writeup and what a real audio LID model would look like for
        a v2 language expansion.
        """
        import torch
        import torchaudio

        if self._whisper_lid_model is None:
            try:
                from transformers import WhisperForConditionalGeneration, WhisperProcessor

                self._whisper_lid_processor = WhisperProcessor.from_pretrained("openai/whisper-tiny")
                self._whisper_lid_model = WhisperForConditionalGeneration.from_pretrained(
                    "openai/whisper-tiny"
                )
                self._whisper_lid_model.eval()
            except Exception as exc:
                raise VoiceUnavailableError(f"failed to load whisper-tiny for LID: {exc}") from exc

        wav, sr = self._load_audio_16k_mono(audio_bytes)
        inputs = self._whisper_lid_processor(
            wav.squeeze().numpy(), sampling_rate=sr, return_tensors="pt"
        )
        with torch.no_grad():
            encoder_outputs = self._whisper_lid_model.get_encoder()(inputs["input_features"])
            decoder_start = torch.tensor(
                [[self._whisper_lid_model.config.decoder_start_token_id]]
            )
            step = self._whisper_lid_model(
                decoder_input_ids=decoder_start, encoder_outputs=encoder_outputs
            )
            first_token_logits = step.logits[0, -1]

        tok = self._whisper_lid_processor.tokenizer
        en_score = first_token_logits[tok.convert_tokens_to_ids("<|en|>")].item()
        kn_score = first_token_logits[tok.convert_tokens_to_ids("<|kn|>")].item()
        return "en" if en_score >= kn_score else "kn"

    # -- TTS -----------------------------------------------------------

    def _synthesize_en(self, text: str) -> bytes:
        if self._piper_en_voice is None:
            voice_path = (
                self._model_dir / "piper" / "en" / "en_US" / "lessac" / "medium"
                / "en_US-lessac-medium.onnx"
            )
            if not voice_path.exists():
                raise VoiceUnavailableError(
                    f"Piper en voice not downloaded: {voice_path} does not exist"
                )
            try:
                from piper import PiperVoice

                self._piper_en_voice = PiperVoice.load(str(voice_path))
            except Exception as exc:
                raise VoiceUnavailableError(f"failed to load Piper voice: {exc}") from exc

        import wave

        buf = io.BytesIO()
        with wave.open(buf, "wb") as wav_file:
            self._piper_en_voice.synthesize_wav(text, wav_file)
        return buf.getvalue()

    def _synthesize_kn(self, text: str) -> bytes:
        if self._vits_kn_model is None:
            try:
                from transformers import AutoModel, AutoTokenizer

                self._vits_kn_model = AutoModel.from_pretrained(
                    "ai4bharat/vits_rasa_13", trust_remote_code=True
                )
                self._vits_kn_tokenizer = AutoTokenizer.from_pretrained(
                    "ai4bharat/vits_rasa_13", trust_remote_code=True
                )
            except Exception as exc:
                raise VoiceUnavailableError(f"failed to load vits_rasa_13: {exc}") from exc

        import soundfile as sf

        inputs = self._vits_kn_tokenizer(text=text, return_tensors="pt")
        outputs = self._vits_kn_model(
            inputs["input_ids"],
            speaker_id=_VITS_KANNADA_SPEAKER_ID,
            emotion_id=_VITS_KANNADA_STYLE_ID,
        )
        buf = io.BytesIO()
        sf.write(
            buf,
            outputs.waveform.squeeze().detach().numpy(),
            self._vits_kn_model.config.sampling_rate,
            format="WAV",
        )
        return buf.getvalue()
