import os
import sys

# Bootstrap path
WORKSPACE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, WORKSPACE_DIR)
sys.path.insert(0, os.path.join(WORKSPACE_DIR, "backend"))

from backend.main import app

def test_openapi_schema():
    print("Generating FastAPI OpenAPI schema...")
    schema = app.openapi()
    
    # 1. Assert security schemes exist in components
    components = schema.get("components", {})
    security_schemes = components.get("securitySchemes", {})
    print(f"Security Schemes: {list(security_schemes.keys())}")
    
    assert "HTTPBearer" in security_schemes, "HTTPBearer security scheme missing in OpenAPI components!"
    scheme = security_schemes["HTTPBearer"]
    assert scheme.get("type") == "http", "HTTPBearer scheme type must be 'http'!"
    assert scheme.get("scheme") == "bearer", "HTTPBearer scheme must be 'bearer'!"
    print("  ✓ Security schemes verified.")

    # 2. Assert endpoints have security requirements
    paths = schema.get("paths", {})
    
    # Check /query endpoint
    query_post = paths.get("/query", {}).get("post", {})
    query_security = query_post.get("security", [])
    print(f"/query security requirements: {query_security}")
    assert any("HTTPBearer" in req for req in query_security), "/query endpoint missing HTTPBearer security tag!"
    
    # Check /protected-test endpoint
    protected_get = paths.get("/protected-test", {}).get("get", {})
    protected_security = protected_get.get("security", [])
    print(f"/protected-test security requirements: {protected_security}")
    assert any("HTTPBearer" in req for req in protected_security), "/protected-test endpoint missing HTTPBearer security tag!"
    
    # Check public endpoints do NOT have security tags
    login_post = paths.get("/login", {}).get("post", {})
    assert "security" not in login_post, "/login endpoint must remain completely public (no security tags)!"
    
    register_post = paths.get("/register", {}).get("post", {})
    assert "security" not in register_post, "/register endpoint must remain completely public (no security tags)!"

    print("\n" + "=" * 60)
    print("  OPENAPI SCHEMAS VERIFIED successfully! Swagger UI Authorize button is wired.")
    print("=" * 60)

if __name__ == "__main__":
    test_openapi_schema()
