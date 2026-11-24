import asyncio
import io
import json
import os
import unittest
from unittest import mock

import httpx

from .support import ApiTestCase  # noqa: F401  (sets env + sqlite before app import)
from app import translation_engine as engine
from app.humanizer import clean_model_output, humanize_local, looks_non_english
from app.doc_retrieval import extractive_answer, relevant_context


def _mock_client(handler):
    real = httpx.AsyncClient

    class Patched(real):
        def __init__(self, *a, **k):
            k["transport"] = httpx.MockTransport(handler)
            super().__init__(*a, **k)

    return mock.patch.object(engine.httpx, "AsyncClient", Patched)


class TranslationEngineTests(unittest.TestCase):
    def setUp(self):
        for name in ("GOOGLE_TRANSLATE_API_KEY", "INDICTRANS_URL", "TRANSLATION_ALLOW_UNOFFICIAL_GOOGLE", "TRANSLATION_PROVIDERS"):
            os.environ.pop(name, None)

    def test_no_provider_returns_none(self):
        self.assertIsNone(asyncio.run(engine.translate_with_providers("Hello", "en", "ta")))

    def test_google_cloud_request_and_response(self):
        os.environ["GOOGLE_TRANSLATE_API_KEY"] = "test-key"
        seen = {}

        def handler(request: httpx.Request):
            seen["url"] = str(request.url)
            seen["body"] = json.loads(request.content)
            return httpx.Response(200, json={"data": {"translations": [{"translatedText": "வணக்கம் &amp; நன்றி"}]}})

        with _mock_client(handler):
            result = asyncio.run(engine.translate_with_providers("Hello & thanks", "en", "ta"))
        self.assertEqual(result.provider, "google")
        self.assertEqual(result.translation, "வணக்கம் & நன்றி")
        self.assertIn("key=test-key", seen["url"])
        self.assertEqual(seen["body"]["target"], "ta")
        self.assertEqual(seen["body"]["source"], "en")
        self.assertEqual(seen["body"]["format"], "text")

    def test_auto_source_omits_source_field(self):
        os.environ["GOOGLE_TRANSLATE_API_KEY"] = "k"
        seen = {}

        def handler(request):
            seen["body"] = json.loads(request.content)
            return httpx.Response(200, json={"data": {"translations": [{"translatedText": "Hello"}]}})

        with _mock_client(handler):
            asyncio.run(engine.translate_with_providers("வணக்கம்", "auto", "en"))
        self.assertNotIn("source", seen["body"])

    def test_google_failure_falls_through_to_next_provider(self):
        os.environ["GOOGLE_TRANSLATE_API_KEY"] = "bad"
        os.environ["INDICTRANS_URL"] = "https://indic.example/translate"

        def handler(request: httpx.Request):
            if "googleapis" in request.url.host:
                return httpx.Response(403, json={"error": {"message": "API key not valid"}})
            return httpx.Response(200, json={"translations": ["नमस्ते"]})

        with _mock_client(handler):
            result = asyncio.run(engine.translate_with_providers("Hello", "en", "hi"))
        self.assertEqual(result.provider, "indictrans")
        self.assertEqual(result.translation, "नमस्ते")

    def test_all_failing_raises_with_reason(self):
        os.environ["GOOGLE_TRANSLATE_API_KEY"] = "bad"

        def handler(request):
            return httpx.Response(403, json={"error": {"message": "API key not valid"}})

        with _mock_client(handler):
            with self.assertRaises(engine.ProviderFailed) as ctx:
                asyncio.run(engine.translate_with_providers("Hello", "en", "ta"))
        self.assertIn("API key not valid", str(ctx.exception))

    def test_unofficial_google_is_opt_in(self):
        def handler(request):
            return httpx.Response(200, json=[[["Bonjour", "Hello", None, None, 1]], None, "en"])

        with _mock_client(handler):
            self.assertIsNone(asyncio.run(engine.translate_with_providers("Hello", "en", "fr")))
            os.environ["TRANSLATION_ALLOW_UNOFFICIAL_GOOGLE"] = "true"
            result = asyncio.run(engine.translate_with_providers("Hello", "en", "fr"))
        self.assertEqual(result.translation, "Bonjour")

    def test_tanglish_is_tamil_transliterated(self):
        os.environ["GOOGLE_TRANSLATE_API_KEY"] = "k"
        seen = {}

        def handler(request):
            seen["body"] = json.loads(request.content)
            return httpx.Response(200, json={"data": {"translations": [{"translatedText": "வணக்கம்"}]}})

        with _mock_client(handler):
            result = asyncio.run(engine.translate_with_providers("Hello", "en", "tanglish"))
        self.assertEqual(seen["body"]["target"], "ta")
        self.assertEqual(result.translation, "vanakkam")

    def test_long_text_is_chunked(self):
        text = ("Sentence number one is here. " * 400).strip()
        chunks = engine.split_text(text, 1000)
        self.assertGreater(len(chunks), 5)
        self.assertTrue(all(len(c) <= 1000 for c in chunks))
        self.assertEqual(" ".join(chunks).split(), text.split())

    def test_same_language_short_circuits(self):
        result = asyncio.run(engine.translate_with_providers("Hello", "en", "en"))
        self.assertEqual(result.translation, "Hello")


class HumanizerTests(unittest.TestCase):
    def test_wordy_phrases_are_simplified(self):
        text, edits = humanize_local("We utilize tools in order to help, due to the fact that it is needed.", "simple", 3)
        self.assertIn("use tools to help", text)
        self.assertIn("because", text)
        self.assertGreater(edits, 2)

    def test_participle_and_adjective_safe(self):
        text, _ = humanize_local("The team has demonstrated skill. The purchased items were fine.", "simple", 3)
        self.assertIn("has shown skill", text)
        self.assertIn("purchased items", text)

    def test_academic_expands_contractions_and_keeps_formal_openers(self):
        text, _ = humanize_local("We can't ignore this. Furthermore, it's clear.", "academic", 3)
        self.assertIn("cannot", text)
        self.assertIn("Furthermore", text)
        self.assertIn("it is clear", text)

    def test_conversational_contracts_but_not_mid_clause_pronouns(self):
        text, _ = humanize_local("We do not know what it is. It is fine.", "conversational", 3)
        self.assertIn("don't", text)
        self.assertIn("what it is", text)
        self.assertIn("It's fine", text)

    def test_filler_is_removed_and_next_word_capitalised(self):
        text, _ = humanize_local("It is important to note that dogs bark.", "simple", 3)
        self.assertEqual(text, "Dogs bark.")

    def test_long_sentence_is_split_but_lists_are_not(self):
        long = ("The committee reviewed the proposal for several weeks before it finally decided to approve the plan, "
                "and the team started working on the first phase of the project immediately after the announcement.")
        text, _ = humanize_local(long, "simple", 4)
        self.assertGreaterEqual(text.count("."), 2)
        listy = "We bought apples, oranges, bananas, grapes, mangoes, pears, plums, cherries, peaches, and lemons for the party this weekend at the market."
        text, _ = humanize_local(listy, "simple", 4)
        self.assertEqual(text.count("."), 1)

    def test_paragraphs_are_preserved(self):
        text, _ = humanize_local("First para.\n\nSecond para.", "simple", 3)
        self.assertEqual(text.count("\n\n"), 1)

    def test_helpers(self):
        self.assertTrue(looks_non_english("வணக்கம் நண்பா"))
        self.assertFalse(looks_non_english("Hello friend"))
        self.assertEqual(clean_model_output("Sure, here is the text:\n\nHello there"), "Hello there")
        self.assertEqual(clean_model_output('"Quoted"'), "Quoted")


class RetrievalTests(unittest.TestCase):
    DOC = "\n\n".join(
        [f"Section {i}. This paragraph talks about gardening topic number {i} and soil." for i in range(60)]
        + ["The refund policy allows returns within 30 days of purchase with a receipt."]
        + [f"Another filler paragraph {i} about weather and clouds." for i in range(60)]
    )

    def test_relevant_context_finds_the_needle_and_stays_small(self):
        context = relevant_context(self.DOC, "What is the refund policy for returns?", budget=1500)
        self.assertIn("refund policy", context)
        self.assertLess(len(context), 2400)

    def test_short_document_returned_whole(self):
        self.assertEqual(relevant_context("Tiny doc.", "anything"), "Tiny doc.")

    def test_extractive_answer(self):
        answer = extractive_answer(self.DOC, "refund policy returns days")
        self.assertIn("30 days", answer)
        self.assertEqual(extractive_answer("Nothing here.", "zebra"), "")


class EndpointTests(ApiTestCase):
    def setUp(self):
        super().setUp()
        for name in ("GOOGLE_TRANSLATE_API_KEY", "INDICTRANS_URL", "TRANSLATION_ALLOW_UNOFFICIAL_GOOGLE", "TRANSLATION_PROVIDERS"):
            os.environ.pop(name, None)
        _, token = self.create_account()
        self.headers = {"Authorization": f"Bearer {token}"}

    def test_humanize_works_without_any_llm(self):
        response = self.client.post("/api/ai/humanize", headers=self.headers, json={
            "text": "Furthermore, we utilize numerous tools in order to facilitate work.", "writing_style": "simple", "strength": 3})
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["engine"], "local")
        self.assertNotIn("utilize", body["humanized_text"])
        self.assertTrue(body["notice"])

    def test_humanize_non_english_without_engines_explains_what_to_configure(self):
        response = self.client.post("/api/ai/humanize", headers=self.headers, json={
            "text": "இது ஒரு சோதனை வாக்கியம் ஆகும் இது நீண்ட வாக்கியம்.", "writing_style": "simple", "strength": 3})
        self.assertEqual(response.status_code, 503)
        self.assertIn("GOOGLE_TRANSLATE_API_KEY", response.json()["detail"])

    def test_translate_without_provider_gives_actionable_message(self):
        response = self.client.post("/api/ai/translate", headers=self.headers, json={
            "text": "Hello", "source_language": "en", "target_language": "ta"})
        self.assertEqual(response.status_code, 503)
        self.assertIn("GOOGLE_TRANSLATE_API_KEY", response.json()["detail"])

    def test_translate_uses_engine_and_reports_provider(self):
        os.environ["GOOGLE_TRANSLATE_API_KEY"] = "k"

        def handler(request):
            return httpx.Response(200, json={"data": {"translations": [{"translatedText": "Bonjour"}]}})

        with _mock_client(handler):
            response = self.client.post("/api/ai/translate", headers=self.headers, json={
                "text": "Hello", "source_language": "en", "target_language": "fr"})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["translation"], "Bonjour")
        self.assertEqual(response.json()["provider"], "google")

    def test_humanize_non_english_round_trips_through_engine(self):
        os.environ["GOOGLE_TRANSLATE_API_KEY"] = "k"
        calls = []

        def handler(request):
            body = json.loads(request.content)
            calls.append(body["target"])
            out = "We utilize tools in order to work." if body["target"] == "en" else "நாங்கள் கருவிகளை பயன்படுத்துகிறோம்"
            return httpx.Response(200, json={"data": {"translations": [{"translatedText": out}]}})

        with _mock_client(handler):
            response = self.client.post("/api/ai/humanize", headers=self.headers, json={
                "text": "நாங்கள் வேலை செய்ய கருவிகளை பயன்படுத்துகிறோம் என்பது உண்மை.", "writing_style": "simple", "strength": 3})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(calls, ["en", "ta"])
        self.assertEqual(response.json()["engine"], "local+translation")

    def test_language_check_reports_engine(self):
        os.environ["GOOGLE_TRANSLATE_API_KEY"] = "k"
        response = self.client.get("/api/translation/languages", headers=self.headers)
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["engines"], ["google"])
        statuses = {item["code"]: item["status"] for item in body["languages"]}
        self.assertEqual(statuses["ta"], "available")
        self.assertEqual(statuses["tanglish"], "available")

    def test_new_theme_ids_are_accepted(self):
        for theme in ("violet", "aurora-pink", "forest-dark"):
            response = self.client.put("/api/settings/preferences", headers=self.headers, json={"theme": theme})
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()["theme"], theme)
        bad = self.client.put("/api/settings/preferences", headers=self.headers, json={"theme": "Not Valid!"})
        self.assertEqual(bad.status_code, 422)


if __name__ == "__main__":
    unittest.main()


class PdfPageTests(ApiTestCase):
    def setUp(self):
        super().setUp()
        _, token = self.create_account()
        self.headers = {"Authorization": f"Bearer {token}"}

    def _pdf(self, pages=3):
        import pymupdf
        doc = pymupdf.open()
        for i in range(pages):
            page = doc.new_page(width=300 + i * 10, height=400)
            page.insert_text((50, 100), f"Original page {i + 1}")
        data = doc.tobytes()
        doc.close()
        return data

    def _texts(self, data):
        import pymupdf
        doc = pymupdf.open(stream=data, filetype="pdf")
        out = [p.get_text().strip() for p in doc]
        sizes = [(round(p.rect.width), round(p.rect.height)) for p in doc]
        doc.close()
        return out, sizes

    def test_insert_blank_page_in_the_middle_keeps_existing_pages(self):
        r = self.client.post("/api/pdf/insert-blank", headers=self.headers,
                             files={"file": ("a.pdf", self._pdf(3), "application/pdf")}, data={"position": "2"})
        self.assertEqual(r.status_code, 200, r.text)
        texts, sizes = self._texts(r.content)
        self.assertEqual(texts, ["Original page 1", "", "Original page 2", "Original page 3"])
        self.assertEqual(r.headers["X-Page-Count"], "4")
        self.assertEqual(sizes[1], sizes[2])  # new page matches the page it was inserted before

    def test_insert_at_first_and_last_position(self):
        r = self.client.post("/api/pdf/insert-blank", headers=self.headers,
                             files={"file": ("a.pdf", self._pdf(2), "application/pdf")}, data={"position": "1"})
        texts, _ = self._texts(r.content)
        self.assertEqual(texts, ["", "Original page 1", "Original page 2"])
        r = self.client.post("/api/pdf/insert-blank", headers=self.headers,
                             files={"file": ("a.pdf", self._pdf(2), "application/pdf")}, data={"position": "3"})
        texts, _ = self._texts(r.content)
        self.assertEqual(texts, ["Original page 1", "Original page 2", ""])

    def test_invalid_position_is_rejected(self):
        for position in ("0", "5", "-1"):
            r = self.client.post("/api/pdf/insert-blank", headers=self.headers,
                                 files={"file": ("a.pdf", self._pdf(2), "application/pdf")}, data={"position": position})
            self.assertEqual(r.status_code, 400, position)

    def test_blank_pdf(self):
        r = self.client.post("/api/pdf/blank", headers=self.headers, data={"pages": "2", "page_size": "Letter"})
        self.assertEqual(r.status_code, 200)
        texts, sizes = self._texts(r.content)
        self.assertEqual(len(texts), 2)
        self.assertEqual(sizes[0], (612, 792))
        self.assertEqual(self.client.post("/api/pdf/blank", headers=self.headers, data={"pages": "0"}).status_code, 400)

    def test_document_chat_falls_back_to_document_text_without_a_model(self):
        text = b"Intro paragraph about the company.\n\nThe refund policy allows returns within 30 days of purchase.\n\nClosing words."
        up = self.client.post("/api/documents/upload", headers=self.headers, files={"file": ("policy.txt", text, "text/plain")})
        self.assertEqual(up.status_code, 200, up.text)
        doc_id = up.json()["id"]
        r = self.client.post(f"/api/ai/documents/{doc_id}/chat", headers=self.headers,
                             json={"message": "What is the refund policy?", "language": "en"})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["engine"], "extractive")
        self.assertIn("30 days", r.json()["reply"])


class SummarizeFileTests(ApiTestCase):
    def test_summarize_uploaded_text_file(self):
        _, token = self.create_account()
        h = {"Authorization": f"Bearer {token}"}
        text = " ".join(f"Sentence {i} explains important detail number {i} about the quarterly plan." for i in range(80))
        r = self.client.post("/api/ai/summarize-file", headers=h, files={"file": ("plan.txt", text.encode(), "text/plain")}, data={"length": "short"})
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertLess(body["summary_words"], body["words"])
        self.assertLessEqual(len(body["summary"]), 900)
        bad = self.client.post("/api/ai/summarize-file", headers=h, files={"file": ("plan.txt", b"hello", "text/plain")}, data={"length": "huge"})
        self.assertEqual(bad.status_code, 400)


class IndicTransClientTests(unittest.TestCase):
    """The local IndicTrans2 service can answer in several shapes; every one must work."""

    def setUp(self):
        for name in ("GOOGLE_TRANSLATE_API_KEY", "TRANSLATION_ALLOW_UNOFFICIAL_GOOGLE", "TRANSLATION_PROVIDERS"):
            os.environ.pop(name, None)
        os.environ["INDICTRANS_URL"] = "http://localhost:8001/translate"

    def tearDown(self):
        os.environ.pop("INDICTRANS_URL", None)

    def _run(self, text, src, tgt, handler):
        with _mock_client(handler):
            return asyncio.run(engine.translate_with_providers(text, src, tgt))

    def test_accepts_translation_string_shape(self):
        seen = {}

        def handler(request):
            seen["body"] = json.loads(request.content)
            return httpx.Response(200, json={"translation": "வணக்கம்"})

        result = self._run("Hello", "en", "ta", handler)
        self.assertEqual((result.provider, result.translation), ("indictrans", "வணக்கம்"))
        self.assertEqual(seen["body"]["src_lang"], "eng_Latn")
        self.assertEqual(seen["body"]["tgt_lang"], "tam_Taml")
        self.assertEqual(seen["body"]["text"], "Hello")

    def test_accepts_list_and_nested_shapes(self):
        for payload in ({"translations": ["नमस्ते"]}, {"translated_text": "नमस्ते"}, {"data": {"translation": "नमस्ते"}}, {"output": ["नमस्ते"]}):
            result = self._run("Hello", "en", "hi", lambda r, p=payload: httpx.Response(200, json=p))
            self.assertEqual(result.translation, "नमस्ते", payload)

    def test_indic_to_indic_pivots_through_english(self):
        calls = []

        def handler(request):
            body = json.loads(request.content)
            calls.append((body["src_lang"], body["tgt_lang"]))
            return httpx.Response(200, json={"translation": "Hello" if body["tgt_lang"] == "eng_Latn" else "नमस्ते"})

        result = self._run("வணக்கம்", "ta", "hi", handler)
        self.assertEqual(calls, [("tam_Taml", "eng_Latn"), ("eng_Latn", "hin_Deva")])
        self.assertEqual(result.translation, "नमस्ते")

    def test_unsupported_pairs_skip_indictrans(self):
        for src, tgt in (("en", "ja"), ("en", "fr"), ("de", "en"), ("es", "ta")):
            self.assertIsNone(self._run("Hello", src, tgt, lambda r: httpx.Response(200, json={"translation": "x"})), (src, tgt))

    def test_tanglish_target_uses_tamil_then_transliterates(self):
        result = self._run("Hello", "en", "tanglish", lambda r: httpx.Response(200, json={"translation": "வணக்கம்"}))
        self.assertEqual((result.provider, result.translation), ("indictrans", "vanakkam"))

    def test_service_down_gives_actionable_error(self):
        def handler(request):
            raise httpx.ConnectError("refused")

        with self.assertRaises(engine.ProviderFailed) as ctx:
            self._run("Hello", "en", "ta", handler)
        self.assertIn("Is it running", str(ctx.exception))

    def test_validation_error_body_is_surfaced(self):
        def handler(request):
            return httpx.Response(422, json={"detail": [{"loc": ["body", "sentences"], "msg": "field required"}]})

        with self.assertRaises(engine.ProviderFailed) as ctx:
            self._run("Hello", "en", "ta", handler)
        self.assertIn("422", str(ctx.exception))
        self.assertIn("field required", str(ctx.exception))

    def test_google_free_enabled_when_listed_explicitly(self):
        os.environ.pop("INDICTRANS_URL")
        os.environ["TRANSLATION_PROVIDERS"] = "indictrans,google_free"
        result = self._run("Hello", "en", "fr", lambda r: httpx.Response(200, json=[[["Bonjour", "Hello", None, None, 1]], None, "en"]))
        self.assertEqual((result.provider, result.translation), ("google_free", "Bonjour"))
        os.environ.pop("TRANSLATION_PROVIDERS")

    def test_default_order_prefers_local_models(self):
        os.environ["GOOGLE_TRANSLATE_API_KEY"] = "k"
        order = []

        def handler(request):
            order.append(request.url.host)
            if request.url.host == "localhost":
                return httpx.Response(200, json={"translation": "वणक्कम्"})
            return httpx.Response(200, json={"data": {"translations": [{"translatedText": "x"}]}})

        result = self._run("Hello", "en", "hi", handler)
        self.assertEqual(order[0], "localhost")
        self.assertEqual(result.provider, "indictrans")
        os.environ.pop("GOOGLE_TRANSLATE_API_KEY")

    def test_probe_reports_each_provider(self):
        os.environ["TRANSLATION_PROVIDERS"] = "indictrans,google"
        report = asyncio.run(engine.probe_providers()) if False else None
        with _mock_client(lambda r: httpx.Response(200, json={"translation": "नमस्ते"})):
            report = asyncio.run(engine.probe_providers())
        by_name = {item["provider"]: item for item in report}
        self.assertTrue(by_name["indictrans"]["working"])
        self.assertFalse(by_name["google"]["configured"])
        self.assertNotIn("test-key", json.dumps(report))
        os.environ.pop("TRANSLATION_PROVIDERS")


class ChatbotFallbackTests(ApiTestCase):
    """The assistant UI uses /api/chat/message; it must survive model and tool-support failures."""

    def setUp(self):
        super().setUp()
        _, token = self.create_account()
        self.headers = {"Authorization": f"Bearer {token}"}
        os.environ.update({"LLM_API_KEY": "k", "LLM_BASE_URL": "http://llm.test/v1", "LLM_MODEL": "first/model:free"})

    def tearDown(self):
        for name in ("LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL"):
            os.environ.pop(name, None)

    def _chat(self, handler, stream=False):
        real = httpx.AsyncClient

        class Patched(real):
            def __init__(self, *a, **k):
                k["transport"] = httpx.MockTransport(handler)
                super().__init__(*a, **k)

        with mock.patch.object(httpx, "AsyncClient", Patched):
            return self.client.post("/api/chat/message", headers=self.headers, json={"text": "What is 2+2?", "language": "en", "stream": stream})

    def test_retries_without_tools_when_provider_rejects_them(self):
        bodies = []

        def handler(request):
            body = json.loads(request.content)
            bodies.append(body)
            if "tools" in body:
                return httpx.Response(404, json={"error": {"message": "No endpoints found that support tool use"}})
            return httpx.Response(200, json={"choices": [{"message": {"role": "assistant", "content": "Four."}}]})

        r = self._chat(handler)
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["text"], "Four.")
        self.assertEqual([("tools" in b) for b in bodies], [True, False])

    def test_falls_back_to_second_model_when_first_is_rate_limited(self):
        tried = []

        def handler(request):
            model = json.loads(request.content)["model"]
            tried.append(model)
            if model == "first/model:free":
                return httpx.Response(429, json={"error": "rate limited"})
            return httpx.Response(200, json={"choices": [{"message": {"content": "From fallback"}}]})

        r = self._chat(handler)
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["text"], "From fallback")
        self.assertEqual(tried[0], "first/model:free")
        self.assertIn("inclusionai/ling-3.2-flash:free", tried)

    def test_rejected_key_gives_clear_error(self):
        r = self._chat(lambda req: httpx.Response(401, json={"error": "bad key"}))
        self.assertEqual(r.status_code, 502)
        self.assertIn("LLM_API_KEY", r.json()["detail"])

    def test_streaming_reports_failure_as_event_not_crash(self):
        r = self._chat(lambda req: httpx.Response(500, text="boom"), stream=True)
        self.assertEqual(r.status_code, 200)
        self.assertIn("No configured AI model answered", r.text)

    def test_streaming_success(self):
        r = self._chat(lambda req: httpx.Response(200, json={"choices": [{"message": {"content": "Four."}}]}), stream=True)
        self.assertIn('"token": "Four."', r.text)
        self.assertIn('"done": true', r.text)
