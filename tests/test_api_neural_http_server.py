import json
import threading
import urllib.request
from flow_memory.api.http_server import HttpApiConfig, HttpApiGateway, create_http_server

def test_neural_http_server_endpoint() -> None:
    gateway=HttpApiGateway(config=HttpApiConfig(enable_rate_limit=False))
    server=create_http_server(gateway, host="127.0.0.1", port=0)
    thread=threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        port=server.server_address[1]
        req=urllib.request.Request(f"http://127.0.0.1:{port}/neural/status", headers={"x-flow-memory-scopes":"neural:read"})
        with urllib.request.urlopen(req, timeout=5) as res:
            data=json.loads(res.read().decode())
        assert data["data"]["ok"] is True
    finally:
        server.shutdown()
        server.server_close()
