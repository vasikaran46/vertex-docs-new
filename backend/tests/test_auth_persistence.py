from tests.support import ApiTestCase

class AuthPersistenceTests(ApiTestCase):
    def test_account_sign_in_reuse_and_authentication_failures(self):
        email,token=self.create_account("Persistent User")
        auth={"Authorization":f"Bearer {token}"}
        profile=self.client.get("/api/auth/me",headers=auth)
        self.assertEqual(profile.status_code,200,profile.text)
        self.assertEqual(profile.json()["email"],email)

        self.assertEqual(self.client.post("/api/auth/logout",headers=auth).status_code,200)
        relogin=self.client.post("/api/auth/login",json={"email":email,"password":"StrongPass123"})
        self.assertEqual(relogin.status_code,200,relogin.text)
        restored=self.client.get("/api/auth/me",headers={"Authorization":f"Bearer {relogin.json()['access_token']}"})
        self.assertEqual(restored.status_code,200,restored.text)
        self.assertEqual(restored.json()["id"],profile.json()["id"])

        self.assertEqual(self.client.get("/api/auth/me").status_code,401)
        self.assertEqual(self.client.post("/api/auth/login",json={"email":email,"password":"wrong-password"}).status_code,401)
