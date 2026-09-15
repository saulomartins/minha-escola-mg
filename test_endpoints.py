import urllib.request
import json

def test_endpoints():
    # 1. Test index
    res = urllib.request.urlopen("http://127.0.0.1:8000/")
    print(f"Index HTML: {res.status} (Tamanho: {len(res.read())} bytes)")

    # 2. Test Gemini API validation endpoint
    req = urllib.request.Request(
        "http://127.0.0.1:8000/api/settings/test-gemini",
        data=json.dumps({"key": ""}).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    res_gemini = json.loads(urllib.request.urlopen(req).read())
    print("Teste Gemini Vazio:", res_gemini)

    # 3. Test Google Play credentials endpoint
    req_google = urllib.request.Request(
        "http://127.0.0.1:8000/api/settings/test-google",
        data=json.dumps({"service_account": ""}).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    res_google = json.loads(urllib.request.urlopen(req_google).read())
    print("Teste Google Vazio:", res_google)

    # 4. Test Apple credentials endpoint
    req_apple = urllib.request.Request(
        "http://127.0.0.1:8000/api/settings/test-apple",
        data=json.dumps({"key_id": "", "issuer_id": "", "private_key_p8": ""}).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    res_apple = json.loads(urllib.request.urlopen(req_apple).read())
    print("Teste Apple Vazio:", res_apple)

    # 5. Test stats
    res_stats = json.loads(urllib.request.urlopen("http://127.0.0.1:8000/api/stats").read())
    print("Estatísticas:", res_stats["total"], "avaliações no banco.")

if __name__ == "__main__":
    test_endpoints()
