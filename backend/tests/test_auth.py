def test_register_login_me(client):
    r = client.post("/api/auth/register",
                    json={"email": "a@a.gr", "password": "secret123", "full_name": "Α"})
    assert r.status_code == 200
    r = client.post("/api/auth/login", json={"email": "a@a.gr", "password": "secret123"})
    assert r.status_code == 200
    assert "grafida_token" in r.cookies
    r = client.get("/api/auth/me")
    assert r.json()["email"] == "a@a.gr"


def test_bad_password(client):
    client.post("/api/auth/register",
                json={"email": "b@b.gr", "password": "secret123", "full_name": "Β"})
    r = client.post("/api/auth/login", json={"email": "b@b.gr", "password": "wrong"})
    assert r.status_code == 401


def test_me_unauthenticated(client):
    assert client.get("/api/auth/me").status_code == 401
