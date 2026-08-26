"""Pure-Python port of ``IndicTransToolkit.processor.IndicProcessor``.

IndicTrans2 (the translation backend in ``ai4bharat_voice.py``) requires
this pre/post-processing step (script normalization, tokenization,
placeholder-wrapping of numbers/URLs/emails, transliteration) around the
raw model call — see the "Usage Instructions" section of the model cards
at https://huggingface.co/ai4bharat/indictrans2-en-indic-dist-200M.

The upstream package (`pip install IndicTransToolkit`) ships this logic
as a Cython extension (`processor.pyx`) with no prebuilt Windows wheel,
so installing it requires the MSVC Build Tools C++ compiler — not present
on this machine and not something to install silently for a capstone
dev environment. This module is a line-for-line behavioral port of that
same `.pyx` file (IndicTransToolkit 1.1.1, MIT license, AI4Bharat) with
Cython type declarations (`cdef`/`cpdef`/`except *`) stripped so it runs
as plain CPython — no compiler needed. Logic is otherwise unchanged.

Upstream: https://github.com/AI4Bharat/IndicTransToolkit
"""
from __future__ import annotations

from queue import Queue

import regex as re
from indicnlp.normalize.indic_normalize import IndicNormalizerFactory
from indicnlp.tokenize import indic_detokenize, indic_tokenize
from indicnlp.transliterate.unicode_transliterate import UnicodeIndicTransliterator
from sacremoses import MosesDetokenizer, MosesPunctNormalizer, MosesTokenizer


class IndicProcessor:
    def __init__(self, inference: bool = True):
        self.inference = inference

        self._flores_codes = {
            "asm_Beng": "as", "awa_Deva": "hi", "ben_Beng": "bn",
            "bho_Deva": "hi", "brx_Deva": "hi", "doi_Deva": "hi",
            "eng_Latn": "en", "gom_Deva": "kK", "gon_Deva": "hi",
            "guj_Gujr": "gu", "hin_Deva": "hi", "hne_Deva": "hi",
            "kan_Knda": "kn", "kas_Arab": "ur", "kas_Deva": "hi",
            "kha_Latn": "en", "lus_Latn": "en", "mag_Deva": "hi",
            "mai_Deva": "hi", "mal_Mlym": "ml", "mar_Deva": "mr",
            "mni_Beng": "bn", "mni_Mtei": "hi", "npi_Deva": "ne",
            "ory_Orya": "or", "pan_Guru": "pa", "san_Deva": "hi",
            "sat_Olck": "or", "snd_Arab": "ur", "snd_Deva": "hi",
            "tam_Taml": "ta", "tel_Telu": "te", "urd_Arab": "ur",
            "unr_Deva": "hi",
        }

        digits_dict = {
            "\u09e6": "0", "\u0ae6": "0", "\u0ce6": "0", "\u0966": "0",
            "\u0660": "0", "\uabf0": "0", "\u0b66": "0", "\u0a66": "0",
            "\u1c50": "0", "\u06f0": "0",
            "\u09e7": "1", "\u0ae7": "1", "\u0967": "1", "\u0ce7": "1",
            "\u06f1": "1", "\uabf1": "1", "\u0b67": "1", "\u0a67": "1",
            "\u1c51": "1", "\u0c67": "1",
            "\u09e8": "2", "\u0ae8": "2", "\u0968": "2", "\u0ce8": "2",
            "\u06f2": "2", "\uabf2": "2", "\u0b68": "2", "\u0a68": "2",
            "\u1c52": "2", "\u0c68": "2",
            "\u09e9": "3", "\u0ae9": "3", "\u0969": "3", "\u0ce9": "3",
            "\u06f3": "3", "\uabf3": "3", "\u0b69": "3", "\u0a69": "3",
            "\u1c53": "3", "\u0c69": "3",
            "\u09ea": "4", "\u0aea": "4", "\u096a": "4", "\u0cea": "4",
            "\u06f4": "4", "\uabf4": "4", "\u0b6a": "4", "\u0a6a": "4",
            "\u1c54": "4", "\u0c6a": "4",
            "\u09eb": "5", "\u0aeb": "5", "\u096b": "5", "\u0ceb": "5",
            "\u06f5": "5", "\uabf5": "5", "\u0b6b": "5", "\u0a6b": "5",
            "\u1c55": "5", "\u0c6b": "5",
            "\u09ec": "6", "\u0aec": "6", "\u096c": "6", "\u0cec": "6",
            "\u06f6": "6", "\uabf6": "6", "\u0b6c": "6", "\u0a6c": "6",
            "\u1c56": "6", "\u0c6c": "6",
            "\u09ed": "7", "\u0aed": "7", "\u096d": "7", "\u0ced": "7",
            "\u06f7": "7", "\uabf7": "7", "\u0b6d": "7", "\u0a6d": "7",
            "\u1c57": "7", "\u0c6d": "7",
            "\u09ee": "8", "\u0aee": "8", "\u096e": "8", "\u0cee": "8",
            "\u06f8": "8", "\uabf8": "8", "\u0b6e": "8", "\u0a6e": "8",
            "\u1c58": "8", "\u0c6e": "8",
            "\u09ef": "9", "\u0aef": "9", "\u096f": "9", "\u0cef": "9",
            "\u06f9": "9", "\uabf9": "9", "\u0b6f": "9", "\u0a6f": "9",
            "\u1c59": "9", "\u0c6f": "9",
        }
        self._digits_translation_table = {ord(k): v for k, v in digits_dict.items()}
        for c in range(ord("0"), ord("9") + 1):
            self._digits_translation_table[c] = chr(c)

        self._placeholder_entity_maps = Queue()

        self._en_tok = MosesTokenizer(lang="en")
        self._en_normalizer = MosesPunctNormalizer()
        self._en_detok = MosesDetokenizer(lang="en")

        self._xliterator = UnicodeIndicTransliterator()

        self._MULTISPACE_REGEX = re.compile(r"[ ]{2,}")
        self._DIGIT_SPACE_PERCENT = re.compile(r"(\d) %")
        self._DOUBLE_QUOT_PUNC = re.compile(r"\"([,\.]+)")
        self._DIGIT_NBSP_DIGIT = re.compile(r"(\d) (\d)")
        self._END_BRACKET_SPACE_PUNC_REGEX = re.compile(r"\) ([\.!:?;,])")

        self._URL_PATTERN = re.compile(
            r"\b(?<![\w/.])(?:(?:https?|ftp)://)?(?:(?:[\w-]+\.)+(?!\.))(?:[\w/\-?#&=%.]+)+(?!\.\w+)\b"
        )
        self._NUMERAL_PATTERN = re.compile(
            r"(~?\d+\.?\d*\s?%?\s?-?\s?~?\d+\.?\d*\s?%|~?\d+%|\d+[-\/.,:']\d+[-\/.,:'+]\d+(?:\.\d+)?|\d+[-\/.:'+]\d+(?:\.\d+)?)"
        )
        self._EMAIL_PATTERN = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}")
        self._OTHER_PATTERN = re.compile(r"[A-Za-z0-9]*[#|@]\w+")

        self._PUNC_REPLACEMENTS = [
            (re.compile(r"\r"), ""),
            (re.compile(r"\(\s*"), "("),
            (re.compile(r"\s*\)"), ")"),
            (re.compile(r"\s:\s?"), ":"),
            (re.compile(r"\s;\s?"), ";"),
            (re.compile(r"[`´‘‚’]"), "'"),
            (re.compile(r"[„“”«»]"), '"'),
            (re.compile(r"[–—]"), "-"),
            (re.compile(r"\.\.\."), "..."),
            (re.compile(r" %"), "%"),
            (re.compile(r"nº "), "nº "),
            (re.compile(r" ºC"), " ºC"),
            (re.compile(r" [?!;]"), lambda m: m.group(0).strip()),
            (re.compile(r", "), ", "),
        ]

        self._INDIC_FAILURE_CASES = [
            "آی ڈی ", "ꯑꯥꯏꯗꯤ", "आईडी", "आई . डी . ", "आई . डी .",
            "आई. डी. ", "आई. डी.", "आय. डी. ", "आय. डी.", "आय . डी . ",
            "आय . डी ." "आइ . डी . ", "आइ . डी .", "आइ. डी. ", "आइ. डी.",
            "ऐटि", "آئی ڈی ", "ᱟᱭᱰᱤ ᱾", "आयडी", "ऐडि", "आइडि", "ᱟᱭᱰᱤ",
        ]

    def _apply_punc_replacements(self, text, replacements):
        for pattern, repl in replacements:
            text = pattern.sub(repl, text)
        return text

    def _punc_norm(self, text):
        text = self._apply_punc_replacements(text, self._PUNC_REPLACEMENTS)
        text = self._MULTISPACE_REGEX.sub(" ", text)
        text = self._END_BRACKET_SPACE_PUNC_REGEX.sub(r")\1", text)
        text = self._DIGIT_SPACE_PERCENT.sub(r"\1%", text)
        text = self._DOUBLE_QUOT_PUNC.sub(r'\1"', text)
        text = self._DIGIT_NBSP_DIGIT.sub(r"\1.\2", text)
        return text.strip()

    def _wrap_with_placeholders(self, text):
        serial_no = 1
        placeholder_entity_map = {}
        patterns = [
            self._EMAIL_PATTERN,
            self._URL_PATTERN,
            self._NUMERAL_PATTERN,
            self._OTHER_PATTERN,
        ]

        for pattern in patterns:
            matches = set(pattern.findall(text))
            for match in matches:
                if pattern is self._URL_PATTERN:
                    if len(match.replace(".", "")) < 4:
                        continue
                if pattern is self._NUMERAL_PATTERN:
                    if len(match.replace(" ", "").replace(".", "").replace(":", "")) < 4:
                        continue

                base_placeholder = f"<ID{serial_no}>"
                placeholder_entity_map[f"<ID{serial_no}>"] = match
                placeholder_entity_map[f"< ID{serial_no} >"] = match
                placeholder_entity_map[f"[ID{serial_no}]"] = match
                placeholder_entity_map[f"[ ID{serial_no} ]"] = match
                placeholder_entity_map[f"[ID {serial_no}]"] = match
                placeholder_entity_map[f"<ID{serial_no}]"] = match
                placeholder_entity_map[f"< ID{serial_no}]"] = match
                placeholder_entity_map[f"<ID{serial_no} ]"] = match

                placeholder_entity_map[f"<id{serial_no}>"] = match
                placeholder_entity_map[f"< id{serial_no} >"] = match
                placeholder_entity_map[f"[id{serial_no}]"] = match
                placeholder_entity_map[f"[ id{serial_no} ]"] = match
                placeholder_entity_map[f"[id {serial_no}]"] = match
                placeholder_entity_map[f"<id{serial_no}]"] = match
                placeholder_entity_map[f"< id{serial_no}]"] = match
                placeholder_entity_map[f"<id{serial_no} ]"] = match

                for indic_case in self._INDIC_FAILURE_CASES:
                    placeholder_entity_map[f"<{indic_case}{serial_no}>"] = match
                    placeholder_entity_map[f"< {indic_case}{serial_no} >"] = match
                    placeholder_entity_map[f"< {indic_case} {serial_no} >"] = match
                    placeholder_entity_map[f"<{indic_case} {serial_no}]"] = match
                    placeholder_entity_map[f"< {indic_case} {serial_no} ]"] = match
                    placeholder_entity_map[f"[{indic_case}{serial_no}]"] = match
                    placeholder_entity_map[f"[{indic_case} {serial_no}]"] = match
                    placeholder_entity_map[f"[ {indic_case}{serial_no} ]"] = match
                    placeholder_entity_map[f"[ {indic_case} {serial_no} ]"] = match
                    placeholder_entity_map[f"{indic_case} {serial_no}"] = match
                    placeholder_entity_map[f"{indic_case}{serial_no}"] = match

                text = text.replace(match, base_placeholder)
                serial_no += 1

        text = re.sub(r"\s+", " ", text).replace(">/", ">").replace("]/", "]")
        self._placeholder_entity_maps.put(placeholder_entity_map)
        return text

    def _normalize(self, text):
        text = text.translate(self._digits_translation_table)
        if self.inference:
            text = self._wrap_with_placeholders(text)
        return text

    def _do_indic_tokenize_and_transliterate(self, sentence, normalizer, iso_lang, transliterate):
        normed = normalizer.normalize(sentence.strip())
        tokens = indic_tokenize.trivial_tokenize(normed, iso_lang)
        joined = " ".join(tokens)
        xlated = joined
        if transliterate:
            xlated = self._xliterator.transliterate(joined, iso_lang, "hi")
            xlated = xlated.replace(" ् ", "्")
        return xlated

    def _preprocess(self, sent, src_lang, tgt_lang, normalizer, is_target):
        iso_lang = self._flores_codes.get(src_lang, "hi")
        script_part = src_lang.split("_")[1]
        do_transliterate = True

        sent = self._punc_norm(sent)
        sent = self._normalize(sent)

        if script_part in ["Arab", "Aran", "Olck", "Mtei", "Latn"]:
            do_transliterate = False

        if iso_lang == "en":
            e_strip = sent.strip()
            e_norm = self._en_normalizer.normalize(e_strip)
            e_tokens = self._en_tok.tokenize(e_norm, escape=False)
            processed_sent = " ".join(e_tokens)
        else:
            processed_sent = self._do_indic_tokenize_and_transliterate(
                sent, normalizer, iso_lang, do_transliterate
            )

        processed_sent = processed_sent.strip()
        if not is_target:
            return f"{src_lang} {tgt_lang} {processed_sent}"
        return processed_sent

    def _postprocess(self, sent, lang, placeholder_entity_map=None):
        if isinstance(sent, (tuple, list)):
            sent = sent[0]

        if placeholder_entity_map is None:
            placeholder_entity_map = self._placeholder_entity_maps.get()

        lang_code, script_code = lang.split("_", 1)
        iso_lang = self._flores_codes.get(lang, "hi")

        if script_code in ["Arab", "Aran"]:
            sent = (
                sent.replace(" ؟", "؟")
                .replace(" ۔", "۔")
                .replace(" ،", "،")
                .replace("ٮ۪", "ؠ")
            )

        if lang_code == "ory":
            sent = sent.replace("ଯ଼", "ୟ")

        for k, v in placeholder_entity_map.items():
            sent = sent.replace(k, v)

        if lang == "eng_Latn":
            return self._en_detok.detokenize(sent.split(" "))
        xlated = self._xliterator.transliterate(sent, "hi", iso_lang)
        return indic_detokenize.trivial_detokenize(xlated, iso_lang)

    def preprocess_batch(self, batch, src_lang, tgt_lang=None, is_target=False, visualize=False):
        iso_code = self._flores_codes.get(src_lang, "hi")
        normalizer = None
        if src_lang != "eng_Latn":
            normalizer = IndicNormalizerFactory().get_normalizer(iso_code)

        return [self._preprocess(s, src_lang, tgt_lang, normalizer, is_target) for s in batch]

    def postprocess_batch(self, sents, lang="hin_Deva", visualize=False, num_return_sequences=1):
        n = len(sents)
        num_inputs = n // num_return_sequences

        placeholder_maps = [self._placeholder_entity_maps.get() for _ in range(num_inputs)]

        results = []
        for i, sent in enumerate(sents):
            map_idx = i // num_return_sequences
            current_map = placeholder_maps[map_idx]
            results.append(self._postprocess(sent, lang, current_map))

        self._placeholder_entity_maps.queue.clear()
        return results
