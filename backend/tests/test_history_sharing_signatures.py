import io
import unittest

import pymupdf

from tests.support import ApiTestCase


def make_pdf(text="Hello Vertex", pages=2) -> bytes:
    doc = pymupdf.open()
    for number in range(pages):
        page = doc.new_page()
        page.insert_text((72, 72), f"{text} page {number + 1}")
    data = doc.tobytes()
    doc.close()
    return data


class Helpers:
    def auth(self, token):
        return {"Authorization": f"Bearer {token}"}

    def upload(self, token, name="report.pdf", data=None):
        r = self.client.post("/api/documents/upload", headers=self.auth(token),
                             files={"file": (name, data or make_pdf(), "application/pdf")})
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()


class HistoryNotificationsTests(Helpers, ApiTestCase):
    def test_upload_creates_persistent_history_and_notification(self):
        _, token = self.create_account()
        doc = self.upload(token)
        events = self.client.get("/api/history/events", headers=self.auth(token)).json()
        self.assertEqual(events["total"], 1)
        self.assertEqual(events["items"][0]["action"], "Uploaded")
        self.assertEqual(events["items"][0]["file_name"], "report.pdf")
        self.assertEqual(events["items"][0]["file_type"], "pdf")
        self.assertEqual(events["items"][0]["document_id"], doc["id"])
        notes = self.client.get("/api/notifications", headers=self.auth(token)).json()
        self.assertEqual(notes["unread_count"], 1)
        self.assertEqual(notes["items"][0]["title"], "File uploaded")

    def test_history_documents_reports_real_upload_time_and_last_operation(self):
        _, token = self.create_account()
        doc = self.upload(token)
        r = self.client.post("/api/pdf/info", headers=self.auth(token),
                             files={"file": ("report.pdf", make_pdf(), "application/pdf")})
        self.assertEqual(r.status_code, 200, r.text)
        items = self.client.get("/api/history/documents", headers=self.auth(token)).json()["items"]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["id"], doc["id"])
        self.assertTrue(items[0]["uploaded_at"])
        self.assertEqual(items[0]["file_type"], "pdf")

    def test_pdf_operation_is_recorded_with_file_name(self):
        _, token = self.create_account()
        r = self.client.post("/api/pdf/rotate", headers=self.auth(token), data={"degrees": "90"},
                             files={"file": ("turn.pdf", make_pdf(), "application/pdf")})
        self.assertEqual(r.status_code, 200, r.text)
        events = self.client.get("/api/history/events", headers=self.auth(token)).json()["items"]
        self.assertEqual(events[0]["action"], "PDF rotated")
        self.assertEqual(events[0]["file_name"], "turn.pdf")

    def test_conversion_triggers_a_notification(self):
        _, token = self.create_account()
        r = self.client.post("/api/pdf/convert", headers=self.auth(token), data={"output_format": "txt"},
                             files={"file": ("a.pdf", make_pdf(), "application/pdf")})
        self.assertEqual(r.status_code, 200, r.text)
        notes = self.client.get("/api/notifications", headers=self.auth(token)).json()
        self.assertIn("Conversion completed", [n["title"] for n in notes["items"]])

    def test_notification_read_and_delete_flow(self):
        _, token = self.create_account()
        self.upload(token)
        notes = self.client.get("/api/notifications", headers=self.auth(token)).json()
        note_id = notes["items"][0]["id"]
        r = self.client.post(f"/api/notifications/{note_id}/read", headers=self.auth(token))
        self.assertTrue(r.json()["read"])
        self.assertEqual(self.client.get("/api/notifications", headers=self.auth(token)).json()["unread_count"], 0)
        self.upload(token, "two.pdf")
        self.assertEqual(self.client.post("/api/notifications/read-all", headers=self.auth(token)).json()["updated"], 1)
        self.assertEqual(self.client.delete(f"/api/notifications/{note_id}", headers=self.auth(token)).status_code, 200)
        self.assertEqual(self.client.delete("/api/notifications", headers=self.auth(token)).status_code, 200)
        self.assertEqual(self.client.get("/api/notifications", headers=self.auth(token)).json()["items"], [])

    def test_history_and_notifications_are_private_between_users(self):
        _, first = self.create_account()
        _, second = self.create_account()
        doc = self.upload(first)
        self.assertEqual(self.client.get("/api/history/events", headers=self.auth(second)).json()["total"], 0)
        self.assertEqual(self.client.get("/api/notifications", headers=self.auth(second)).json()["items"], [])
        self.assertEqual(self.client.get("/api/history/documents", headers=self.auth(second)).json()["items"], [])
        notes = self.client.get("/api/notifications", headers=self.auth(first)).json()["items"]
        self.assertEqual(self.client.post(f"/api/notifications/{notes[0]['id']}/read", headers=self.auth(second)).status_code, 404)
        self.assertEqual(self.client.post(f"/api/documents/{doc['id']}/share", headers=self.auth(second), json={}).status_code, 404)

    def test_history_survives_document_deletion(self):
        _, token = self.create_account()
        doc = self.upload(token)
        self.assertEqual(self.client.delete(f"/api/documents/{doc['id']}", headers=self.auth(token)).status_code, 200)
        actions = [e["action"] for e in self.client.get("/api/history/events", headers=self.auth(token)).json()["items"]]
        self.assertIn("Uploaded", actions)
        self.assertIn("Deleted", actions)
        self.assertEqual(self.client.get("/api/history/documents", headers=self.auth(token)).json()["items"], [])

    def test_history_events_can_be_deleted_by_owner_only(self):
        _, first = self.create_account()
        _, second = self.create_account()
        self.upload(first)
        event_id = self.client.get("/api/history/events", headers=self.auth(first)).json()["items"][0]["id"]
        self.assertEqual(self.client.delete(f"/api/history/events/{event_id}", headers=self.auth(second)).status_code, 404)
        self.assertEqual(self.client.delete(f"/api/history/events/{event_id}", headers=self.auth(first)).status_code, 200)

    def test_history_requires_authentication(self):
        for path in ("/api/history/events", "/api/history/documents", "/api/notifications"):
            self.assertEqual(self.client.get(path).status_code, 401, path)


class SharingTests(Helpers, ApiTestCase):
    def test_share_link_downloads_the_right_file_and_can_be_revoked(self):
        _, token = self.create_account()
        payload = make_pdf("Shared content")
        doc = self.upload(token, "share-me.pdf", payload)
        share = self.client.post(f"/api/documents/{doc['id']}/share", headers=self.auth(token), json={})
        self.assertEqual(share.status_code, 200, share.text)
        body = share.json()
        self.assertEqual(body["email_status"], "not_requested")
        got = self.client.get(body["download_path"])
        self.assertEqual(got.status_code, 200)
        self.assertEqual(got.content, payload)
        shares = self.client.get(f"/api/documents/{doc['id']}/shares", headers=self.auth(token)).json()["items"]
        self.assertEqual(shares[0]["download_count"], 1)
        self.assertEqual(self.client.delete(f"/api/shares/{body['id']}", headers=self.auth(token)).status_code, 200)
        self.assertEqual(self.client.get(body["download_path"]).status_code, 404)

    def test_share_with_email_reports_honestly_when_smtp_is_not_configured(self):
        _, token = self.create_account()
        doc = self.upload(token)
        body = self.client.post(f"/api/documents/{doc['id']}/share", headers=self.auth(token),
                                json={"recipient_email": "friend@example.com"}).json()
        self.assertEqual(body["email_status"], "not_configured")
        self.assertFalse(body["emailed"])

    def test_unknown_or_invalid_share_token_is_rejected(self):
        self.assertEqual(self.client.get("/api/shared/not-a-real-token").status_code, 404)

    def test_share_requires_valid_email_and_logs_history(self):
        _, token = self.create_account()
        doc = self.upload(token)
        bad = self.client.post(f"/api/documents/{doc['id']}/share", headers=self.auth(token), json={"recipient_email": "nope"})
        self.assertEqual(bad.status_code, 422)
        self.client.post(f"/api/documents/{doc['id']}/share", headers=self.auth(token), json={})
        actions = [e["action"] for e in self.client.get("/api/history/events", headers=self.auth(token)).json()["items"]]
        self.assertIn("Shared", actions)


class SignatureTests(Helpers, ApiTestCase):
    def request_signature(self, token, doc_id, **overrides):
        payload = {"document_id": doc_id, "signer_name": "Asha Raman", "signer_email": "asha@example.com"}
        payload.update(overrides)
        return self.client.post("/api/signatures", headers=self.auth(token), json=payload)

    def test_full_signature_flow_stamps_a_new_signed_copy(self):
        _, token = self.create_account()
        doc = self.upload(token, "contract.pdf", make_pdf("Contract"))
        created = self.request_signature(token, doc["id"], message="Please sign")
        self.assertEqual(created.status_code, 200, created.text)
        request = created.json()
        self.assertEqual(request["status"], "pending")
        self.assertEqual(request["email_status"], "not_configured")
        link_token = request["sign_url"].split("?sign=")[1]

        details = self.client.get(f"/api/signatures/public/{link_token}").json()
        self.assertEqual(details["document_name"], "contract.pdf")
        self.assertEqual(details["status"], "pending")
        shown = self.client.get(f"/api/signatures/public/{link_token}/document")
        self.assertEqual(shown.status_code, 200)
        self.assertTrue(shown.content.startswith(b"%PDF"))

        refused = self.client.post(f"/api/signatures/public/{link_token}/sign", json={"signature_text": "Asha Raman", "agree": False})
        self.assertEqual(refused.status_code, 422)
        signed = self.client.post(f"/api/signatures/public/{link_token}/sign", json={"signature_text": "Asha Raman", "agree": True})
        self.assertEqual(signed.status_code, 200, signed.text)

        listing = self.client.get("/api/signatures", headers=self.auth(token)).json()["items"]
        self.assertEqual(listing[0]["status"], "signed")
        self.assertTrue(listing[0]["signed_document_id"])
        copy = self.client.get(f"/api/documents/{listing[0]['signed_document_id']}/download", headers=self.auth(token))
        self.assertEqual(copy.status_code, 200)
        text = "".join(page.get_text() for page in pymupdf.open(stream=copy.content, filetype="pdf"))
        self.assertIn("Signed by Asha Raman", text)
        self.assertIn("Contract", text)
        again = self.client.post(f"/api/signatures/public/{link_token}/sign", json={"signature_text": "Asha Raman", "agree": True})
        self.assertEqual(again.status_code, 409)
        titles = [n["title"] for n in self.client.get("/api/notifications", headers=self.auth(token)).json()["items"]]
        self.assertIn("Document signed", titles)

    def test_decline_and_cancel(self):
        _, token = self.create_account()
        doc = self.upload(token)
        first = self.request_signature(token, doc["id"]).json()
        link = first["sign_url"].split("?sign=")[1]
        self.assertEqual(self.client.post(f"/api/signatures/public/{link}/decline").status_code, 200)
        self.assertEqual(self.client.get(f"/api/signatures/public/{link}/document").status_code, 409)
        second = self.request_signature(token, doc["id"]).json()
        self.assertEqual(self.client.post(f"/api/signatures/{second['id']}/cancel", headers=self.auth(token)).json()["status"], "cancelled")
        self.assertEqual(self.client.post(f"/api/signatures/{second['id']}/cancel", headers=self.auth(token)).status_code, 409)

    def test_validation_and_ownership(self):
        _, first = self.create_account()
        _, second = self.create_account()
        doc = self.upload(first)
        self.assertEqual(self.request_signature(second, doc["id"]).status_code, 404)
        self.assertEqual(self.request_signature(first, doc["id"], signer_email="bad").status_code, 422)
        self.assertEqual(self.request_signature(first, doc["id"], signer_name="").status_code, 422)
        text_doc = self.upload(first, "notes.txt", b"hello")
        self.assertEqual(self.request_signature(first, text_doc["id"]).status_code, 400)
        self.assertEqual(self.client.get("/api/signatures/public/bogus").status_code, 404)
        self.assertEqual(len(self.client.get("/api/signatures", headers=self.auth(second)).json()["items"]), 0)


class AnnotationTests(Helpers, ApiTestCase):
    SAMPLE = [
        {"id": "a", "type": "highlight", "page": 1, "x": 0.1, "y": 0.1, "w": 0.4, "h": 0.05, "color": "#ffe066"},
        {"id": "b", "type": "text", "page": 2, "x": 0.2, "y": 0.5, "text": "Review this", "size": 14, "color": "#d6336c"},
        {"id": "c", "type": "pen", "page": 1, "points": [[0.1, 0.8], [0.2, 0.82], [0.3, 0.8]], "width": 2, "color": "#1c7ed6"},
        {"id": "d", "type": "rect", "page": 1, "x": 0.5, "y": 0.5, "w": 0.2, "h": 0.1, "color": "#2f9e44"},
    ]

    def test_annotations_persist_and_export_into_the_pdf(self):
        _, token = self.create_account()
        doc = self.upload(token)
        self.assertEqual(self.client.get(f"/api/documents/{doc['id']}/annotations", headers=self.auth(token)).json()["annotations"], [])
        saved = self.client.put(f"/api/documents/{doc['id']}/annotations", headers=self.auth(token), json={"annotations": self.SAMPLE})
        self.assertEqual(saved.status_code, 200, saved.text)
        self.assertEqual(saved.json()["count"], 4)
        loaded = self.client.get(f"/api/documents/{doc['id']}/annotations", headers=self.auth(token)).json()["annotations"]
        self.assertEqual([a["id"] for a in loaded], ["a", "b", "c", "d"])
        out = self.client.get(f"/api/documents/{doc['id']}/annotated-pdf", headers=self.auth(token))
        self.assertEqual(out.status_code, 200, out.text)
        result = pymupdf.open(stream=out.content, filetype="pdf")
        self.assertEqual(result.page_count, 2)
        self.assertIn("Review this", result[1].get_text())
        kinds = {a.type[1] for a in result[0].annots()}
        self.assertIn("Square", kinds)
        self.assertGreaterEqual(len(list(result[0].get_drawings())), 1)

    def test_annotations_are_scoped_to_their_own_document_and_user(self):
        _, first = self.create_account()
        _, second = self.create_account()
        one = self.upload(first, "one.pdf")
        two = self.upload(first, "two.pdf")
        self.client.put(f"/api/documents/{one['id']}/annotations", headers=self.auth(first), json={"annotations": self.SAMPLE[:1]})
        self.assertEqual(self.client.get(f"/api/documents/{two['id']}/annotations", headers=self.auth(first)).json()["annotations"], [])
        self.assertEqual(self.client.get(f"/api/documents/{one['id']}/annotations", headers=self.auth(second)).status_code, 404)
        self.assertEqual(self.client.put(f"/api/documents/{one['id']}/annotations", headers=self.auth(second), json={"annotations": []}).status_code, 404)

    def test_invalid_annotations_are_rejected(self):
        _, token = self.create_account()
        doc = self.upload(token)
        url = f"/api/documents/{doc['id']}/annotations"
        bad_payloads = [
            [{"type": "sticker", "page": 1}],
            [{"type": "highlight", "page": 0, "x": 0, "y": 0, "w": 1, "h": 1}],
            [{"type": "highlight", "page": 1, "x": 2, "y": 0, "w": 1, "h": 1}],
            [{"type": "text", "page": 1, "x": 0.1, "y": 0.1, "text": "  "}],
            [{"type": "pen", "page": 1, "points": [[0, 0]]}],
            [{"type": "rect", "page": 1, "x": 0, "y": 0, "w": 1, "h": 1, "color": "red"}],
        ]
        for payload in bad_payloads:
            self.assertEqual(self.client.put(url, headers=self.auth(token), json={"annotations": payload}).status_code, 422, payload)
        self.assertEqual(self.client.put(url, headers=self.auth(token), json={"annotations": "x"}).status_code, 422)

    def test_non_pdf_documents_cannot_be_annotated(self):
        _, token = self.create_account()
        doc = self.upload(token, "notes.txt", b"plain")
        self.assertEqual(self.client.get(f"/api/documents/{doc['id']}/annotations", headers=self.auth(token)).status_code, 400)

    def test_replacing_annotations_overwrites_the_previous_set(self):
        _, token = self.create_account()
        doc = self.upload(token)
        url = f"/api/documents/{doc['id']}/annotations"
        self.client.put(url, headers=self.auth(token), json={"annotations": self.SAMPLE})
        self.client.put(url, headers=self.auth(token), json={"annotations": self.SAMPLE[:1]})
        self.assertEqual(len(self.client.get(url, headers=self.auth(token)).json()["annotations"]), 1)


if __name__ == "__main__":
    unittest.main()


class DocumentOpenTests(Helpers, ApiTestCase):
    def test_text_and_page_endpoints_read_the_saved_document(self):
        _, token = self.create_account()
        pdf = self.upload(token, "doc.pdf", make_pdf("Opened content", pages=3))
        text = self.client.get(f"/api/documents/{pdf['id']}/text", headers=self.auth(token))
        self.assertEqual(text.status_code, 200, text.text)
        self.assertIn("Opened content", text.json()["text"])
        page = self.client.get(f"/api/documents/{pdf['id']}/page/3", headers=self.auth(token)).json()
        self.assertEqual(page["page_count"], 3)
        self.assertTrue(page["image_data"])
        self.assertEqual(self.client.get(f"/api/documents/{pdf['id']}/page/9", headers=self.auth(token)).status_code, 400)
        note = self.upload(token, "n.txt", "plain notes".encode())
        self.assertIn("plain notes", self.client.get(f"/api/documents/{note['id']}/text", headers=self.auth(token)).json()["text"])
        self.assertEqual(self.client.get(f"/api/documents/{note['id']}/page/1", headers=self.auth(token)).status_code, 400)

    def test_other_users_cannot_open_the_document(self):
        _, first = self.create_account()
        _, second = self.create_account()
        pdf = self.upload(first)
        self.assertEqual(self.client.get(f"/api/documents/{pdf['id']}/text", headers=self.auth(second)).status_code, 404)
        self.assertEqual(self.client.get(f"/api/documents/{pdf['id']}/page/1", headers=self.auth(second)).status_code, 404)

    def test_page_previews_do_not_flood_history(self):
        _, token = self.create_account()
        pdf = self.upload(token)
        before = self.client.get("/api/history/events", headers=self.auth(token)).json()["total"]
        r = self.client.post("/api/pdf/preview", headers=self.auth(token), data={"page": "1"},
                             files={"file": ("a.pdf", make_pdf(), "application/pdf")})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.client.get("/api/history/events", headers=self.auth(token)).json()["total"], before)
