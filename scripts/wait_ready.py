import time

import httpx

for _ in range(90):
    try:
        api = httpx.get("http://localhost:8000/v1/health/ready", timeout=3, trust_env=False)
        web = httpx.get("http://localhost:3000", timeout=3, trust_env=False)
        if api.status_code == 200 and web.status_code == 200:
            print("Web and control API are ready.")
            break
    except httpx.HTTPError:
        pass
    time.sleep(1)
else:
    raise SystemExit("Local stack did not become ready; inspect .local logs.")
