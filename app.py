"""
Flask Chart Dashboard API — SSO Only
=====================================
Xac thuc bang JWT Token tu Microsoft Teams SSO.
Email lay tu token duoc dung de phan quyen RBAC.
"""

from __future__ import annotations

import functools
import os
from typing import Any

# pyrefly: ignore [missing-import]
import jwt
import requests as http_requests
from flask import Flask, Response, jsonify, render_template, request

# =============================================================================
# 0. CAU HINH AZURE AD
# =============================================================================

AZURE_CLIENT_ID: str = os.environ.get("AZURE_CLIENT_ID", "0dac6051-6c9f-4a8d-927a-e479650587e6")
AZURE_TENANT_ID: str = os.environ.get("AZURE_TENANT_ID", "4cb604a3-4a60-49f9-9fb1-5dee8a3ec5de")

# Audience = Application ID URI (khop voi manifest.json webApplicationInfo.resource)
AZURE_AUDIENCE: str = f"api://thanhtung1105.pythonanywhere.com/{AZURE_CLIENT_ID}"

# Issuer v1 (Teams SSO tra ve token v1)
AZURE_ISSUER: str = f"https://sts.windows.net/{AZURE_TENANT_ID}/"

# JWKS keys endpoint
AZURE_JWKS_URL: str = (
    f"https://login.microsoftonline.com/{AZURE_TENANT_ID}"
    f"/discovery/v2.0/keys"
)


# =============================================================================
# 1. DU LIEU PHAN QUYEN (RBAC)
# =============================================================================

# Bang phan quyen: email -> role
USERS: dict[str, dict[str, str]] = {
    "tungdt@vietanh-group.com": {"name": "Do Thanh Tung", "role": "admin"},
    "hieuptt@vietanh-group.com": {"name": "Pham Tran Trung Hieu", "role": "manager"},
    "lanmh@vietanh-group.com": {"name": "Mai Huong Lan", "role": "restricted"},
    "longnv@vietanh-group.com": {"name": "Nguyen Ngoc Long", "role": "manager"},
}

# Role -> danh sach chart_id duoc phep xem
ROLE_PERMISSIONS: dict[str, list[str]] = {
    "admin": ["tong-quan", "doanh-thu", "bao-mat"],
    "manager": ["tong-quan", "doanh-thu"],
    "restricted": [],
}


# =============================================================================
# 2. XAC THUC — Giai ma JWT Token tu Microsoft Teams SSO
# =============================================================================

_jwks_cache: dict | None = None


def _get_microsoft_public_keys() -> dict:
    """Lay khoa cong khai tu Microsoft de xac minh chu ky JWT."""
    global _jwks_cache
    if _jwks_cache is None:
        resp = http_requests.get(AZURE_JWKS_URL, timeout=10)
        resp.raise_for_status()
        _jwks_cache = resp.json()
    return _jwks_cache


def _decode_sso_token(token: str) -> tuple[dict | None, str]:
    """
    Giai ma va xac minh JWT Token tu Microsoft Teams SSO.
    Returns: (decoded_payload, error_message)
    """
    try:
        unverified_header = jwt.get_unverified_header(token)
        kid = unverified_header.get("kid")
        print(f"[DEBUG] Token kid: {kid}")

        # Buoc 1: Lay khoa cong khai
        try:
            jwks = _get_microsoft_public_keys()
            print(f"[DEBUG] Got {len(jwks.get('keys', []))} keys from Microsoft")
        except Exception as e:
            print(f"[ERROR] Cannot fetch Microsoft keys: {e}")
            return None, f"Khong the ket noi Microsoft de lay khoa: {e}"

        rsa_key = None
        for key in jwks.get("keys", []):
            if key["kid"] == kid:
                rsa_key = jwt.algorithms.RSAAlgorithm.from_jwk(key)
                break

        if rsa_key is None:
            print(f"[ERROR] No matching key for kid={kid}")
            return None, f"Khong tim thay khoa khop voi kid={kid}"

        # Buoc 2: Giai ma token
        decoded = jwt.decode(
            token,
            key=rsa_key,
            algorithms=["RS256"],
            audience=AZURE_AUDIENCE,
            issuer=AZURE_ISSUER,
        )
        print(f"[DEBUG] Token decoded OK. Email: {decoded.get('preferred_username')}")
        return decoded, ""

    except jwt.InvalidAudienceError:
        return None, f"Token audience sai. Expected: {AZURE_CLIENT_ID}"
    except jwt.InvalidIssuerError:
        return None, f"Token issuer sai. Expected tenant: {AZURE_TENANT_ID}"
    except jwt.ExpiredSignatureError:
        return None, "Token da het han"
    except Exception as e:
        print(f"[ERROR] Token decode failed: {e}")
        return None, f"Loi giai ma token: {e}"


# Luu lai loi cuoi cung de hien thi cho user
_last_auth_error: str = ""


def get_current_user_email() -> str | None:
    """Lay email tu JWT Token trong header Authorization."""
    global _last_auth_error
    _last_auth_error = ""

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        _last_auth_error = "Thieu header Authorization"
        return None

    token = auth_header.replace("Bearer ", "")
    decoded, error = _decode_sso_token(token)

    if decoded is None:
        _last_auth_error = error
        return None

    # Token v1 dung 'upn', token v2 dung 'preferred_username'
    return decoded.get("upn") or decoded.get("preferred_username")


def get_user_info(email: str) -> dict[str, str] | None:
    """Tra cuu thong tin user tu email."""
    return USERS.get(email)


def get_allowed_charts(role: str) -> list[str]:
    """Lay danh sach chart_id ma role duoc phep truy cap."""
    return ROLE_PERMISSIONS.get(role, [])


# =============================================================================
# 3. DECORATOR PHAN QUYEN
# =============================================================================

def require_chart_permission(chart_id: str):
    """Kiem tra quyen truy cap bieu do truoc khi cho phep."""

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> tuple[Response, int] | Any:
            email: str | None = get_current_user_email()

            if not email:
                return jsonify({
                    "success": False,
                    "error": "UNAUTHORIZED",
                    "message": "Thieu token xac thuc.",
                }), 401

            user: dict[str, str] | None = get_user_info(email)

            if user is None:
                return jsonify({
                    "success": False,
                    "error": "UNAUTHORIZED",
                    "message": f"Email '{email}' khong ton tai trong he thong.",
                }), 401

            role: str = user["role"]
            allowed_charts: list[str] = get_allowed_charts(role)

            if chart_id not in allowed_charts:
                return jsonify({
                    "success": False,
                    "error": "FORBIDDEN",
                    "message": f"Vai tro '{role}' khong co quyen xem '{chart_id}'.",
                }), 403

            current_user: dict[str, str] = {
                "email": email,
                "name": user["name"],
                "role": role,
            }
            kwargs["current_user"] = current_user
            return func(*args, **kwargs)

        return wrapper

    return decorator


# =============================================================================
# 4. FLASK APP
# =============================================================================

app = Flask(__name__)


# =============================================================================
# 5. API ENDPOINTS
# =============================================================================

@app.route("/")
def dashboard():
    return render_template("index.html")


@app.route('/config')
def config_tab():
    return render_template('config.html')


@app.route("/api/charts/tong-quan")
@require_chart_permission("tong-quan")
def chart_tong_quan(current_user: dict[str, str]) -> tuple[Response, int]:
    return jsonify({
        "success": True,
        "chart_id": "tong-quan",
        "chart_name": "Bieu do Tong quan",
        "accessed_by": current_user,
        "data": {
            "total_users": 1250,
            "active_sessions": 342,
            "total_revenue": "1.2B VND",
        },
    }), 200


@app.route("/api/charts/doanh-thu")
@require_chart_permission("doanh-thu")
def chart_doanh_thu(current_user: dict[str, str]) -> tuple[Response, int]:
    return jsonify({
        "success": True,
        "chart_id": "doanh-thu",
        "chart_name": "Bieu do Doanh thu",
        "accessed_by": current_user,
        "data": {
            "monthly_revenue": [
                {"month": "01/2026", "value": 120_000_000},
                {"month": "02/2026", "value": 135_000_000},
                {"month": "03/2026", "value": 98_000_000},
                {"month": "04/2026", "value": 142_000_000},
            ],
            "currency": "VND",
        },
    }), 200


@app.route("/api/charts/bao-mat")
@require_chart_permission("bao-mat")
def chart_bao_mat(current_user: dict[str, str]) -> tuple[Response, int]:
    return jsonify({
        "success": True,
        "chart_id": "bao-mat",
        "chart_name": "Bieu do Bao mat",
        "accessed_by": current_user,
        "data": {
            "failed_logins_today": 23,
            "blocked_ips": 5,
            "threat_level": "LOW",
            "last_scan": "2026-05-07T10:30:00+07:00",
        },
    }), 200


@app.route("/api/my-charts")
def my_charts() -> tuple[Response, int]:
    email = get_current_user_email()
    if not email:
        return jsonify({
            "success": False,
            "error": "UNAUTHORIZED",
            "message": _last_auth_error or "Khong xac thuc duoc",
        }), 401

    user = get_user_info(email)
    if user is None:
        return jsonify({
            "success": False,
            "error": "UNAUTHORIZED",
            "message": f"Email '{email}' khong co trong he thong",
        }), 401

    role = user["role"]
    return jsonify({
        "success": True,
        "user": {"email": email, "name": user["name"], "role": role},
        "allowed_charts": get_allowed_charts(role),
    }), 200


@app.route("/api/debug-token")
def debug_token() -> tuple[Response, int]:
    """Endpoint debug — xem token có vấn đề gì."""
    auth_header = request.headers.get("Authorization", "")
    has_token = auth_header.startswith("Bearer ")

    result = {
        "has_authorization_header": bool(auth_header),
        "has_bearer_token": has_token,
        "client_id": AZURE_CLIENT_ID,
        "tenant_id": AZURE_TENANT_ID,
    }

    if has_token:
        token = auth_header.replace("Bearer ", "")
        # Decode without verification to see contents
        try:
            payload = jwt.decode(token, options={"verify_signature": False})
            result["token_audience"] = payload.get("aud")
            result["token_issuer"] = payload.get("iss")
            result["token_email"] = payload.get("preferred_username")
            result["token_name"] = payload.get("name")
            result["expected_audience"] = AZURE_CLIENT_ID
            result["expected_issuer"] = f"https://login.microsoftonline.com/{AZURE_TENANT_ID}/v2.0"
            result["audience_match"] = payload.get("aud") == AZURE_CLIENT_ID
        except Exception as e:
            result["decode_error"] = str(e)

        # Try full verification
        decoded, error = _decode_sso_token(token)
        result["verification_ok"] = decoded is not None
        result["verification_error"] = error

    return jsonify(result), 200


@app.route("/api/health")
def health_check() -> tuple[Response, int]:
    return jsonify({"status": "ok", "service": "chart-dashboard-api"}), 200


# =============================================================================
# 6. CHAY UNG DUNG
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("  Chart Dashboard API — Teams SSO")
    print(f"  Client ID: {AZURE_CLIENT_ID[:8]}...")
    print(f"  Tenant ID: {AZURE_TENANT_ID[:8]}...")
    print("=" * 60)

    app.run(debug=True, host="0.0.0.0", port=5000)
