import uuid

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

    def test_signup_creates_a_usable_session_and_login_accepts_the_same_credentials(self):
        email=f"{uuid.uuid4().hex}@example.com"
        signup=self.client.post("/api/auth/signup",json={"name":"New Person","email":email,"password":"StrongPass123"})
        self.assertEqual(signup.status_code,200,signup.text)
        session=signup.json()
        self.assertEqual(session["token_type"],"bearer")
        self.assertTrue(session["access_token"])
        self.assertEqual(session["user"]["email"],email)

        profile=self.client.get("/api/auth/me",headers={"Authorization":f"Bearer {session['access_token']}"})
        self.assertEqual(profile.status_code,200,profile.text)
        self.assertEqual(profile.json()["email"],email)

        relogin=self.client.post("/api/auth/login",json={"email":email.upper(),"password":"StrongPass123"})
        self.assertEqual(relogin.status_code,200,relogin.text)
        self.assertEqual(relogin.json()["user"]["id"],session["user"]["id"])

    def test_multiple_people_can_create_and_use_separate_accounts(self):
        people=[]
        for name in ("First Person","Second Person"):
            email=f"{uuid.uuid4().hex}@example.com"
            signup=self.client.post("/api/auth/signup",json={"name":name,"email":email,"password":"StrongPass123"})
            self.assertEqual(signup.status_code,200,signup.text)
            people.append((email,signup.json()))

        self.assertNotEqual(people[0][1]["user"]["id"],people[1][1]["user"]["id"])
        for email,session in people:
            profile=self.client.get("/api/auth/me",headers={"Authorization":f"Bearer {session['access_token']}"})
            self.assertEqual(profile.status_code,200,profile.text)
            self.assertEqual(profile.json()["email"],email)
            self.assertEqual(self.client.get("/api/documents",headers={"Authorization":f"Bearer {session['access_token']}"}).json(),[])
