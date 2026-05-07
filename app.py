"""
Flask Chart Dashboard API - Phase 1 (Mock Data)
================================================
Hệ thống API trả về dữ liệu biểu đồ với phân quyền RBAC.
Giai đoạn này sử dụng Mock Data để thiết lập luồng logic chuẩn xác.

Trong tương lai:
  - Thay USERS dict -> truy vấn Database thực tế.
  - Thay X-Mock-Email header -> giải mã Token từ Microsoft SSO.
"""

from __future__ import annotations

import functools
from typing import Any

# pyrefly: ignore [missing-import]
from flask import Flask, Response, jsonify, render_template, request

# =============================================================================
# 1. MOCK DATA — Giả lập Database bằng Python Dictionary
# =============================================================================

# Danh sách người dùng giả lập.
# Key: email (sẽ khớp với định danh từ Microsoft Teams sau này).
# Value: thông tin user gồm tên hiển thị và vai trò (role).
USERS: dict[str, dict[str, str]] = {
    "admin@company.com": {
        "name": "Nguyễn Văn Admin",
        "role": "admin",
    },
    "manager@company.com": {
        "name": "Trần Thị Manager",
        "role": "manager",
    },
    "staff@company.com": {
        "name": "Lê Văn Staff",
        "role": "staff",
    },
}

# Bảng phân quyền: mỗi role được phép xem những chart_id nào.
# - admin : xem được tất cả biểu đồ.
# - manager: xem được tổng quan và doanh thu, không xem được bảo mật.
# - staff  : chỉ xem được tổng quan.
ROLE_PERMISSIONS: dict[str, list[str]] = {
    "admin": ["tong-quan", "doanh-thu", "bao-mat"],
    "manager": ["tong-quan", "doanh-thu"],
    "staff": ["tong-quan"],
}


# =============================================================================
# 2. HÀM TIỆN ÍCH — Tách riêng logic xác thực để dễ thay thế sau này
# =============================================================================

def get_current_user_email() -> str | None:
    """
    Lấy email của người dùng hiện tại từ request.

    ┌─────────────────────────────────────────────────────────────────┐
    │  ĐIỂM THAY THẾ DUY NHẤT KHI TÍCH HỢP SSO THỰC TẾ            │
    │                                                                 │
    │  Hiện tại : Đọc từ header "X-Mock-Email".                      │
    │  Sau này  : Giải mã JWT Token từ header "Authorization",       │
    │             gọi Microsoft Graph API để lấy email.               │
    │                                                                 │
    │  Chỉ cần thay đổi NỘI DUNG của hàm này, toàn bộ luồng        │
    │  phân quyền phía dưới sẽ KHÔNG cần sửa gì thêm.               │
    └─────────────────────────────────────────────────────────────────┘
    """
    return request.headers.get("X-Mock-Email")


def get_user_info(email: str) -> dict[str, str] | None:
    """
    Tra cứu thông tin user từ email.

    Hiện tại : Tra cứu từ dict USERS (mock).
    Sau này  : Query từ Database thực tế.
    """
    return USERS.get(email)


def get_allowed_charts(role: str) -> list[str]:
    """
    Lấy danh sách chart_id mà role được phép truy cập.

    Hiện tại : Tra cứu từ dict ROLE_PERMISSIONS (mock).
    Sau này  : Query từ bảng permissions trong Database.
    """
    return ROLE_PERMISSIONS.get(role, [])


# =============================================================================
# 3. DECORATOR PHÂN QUYỀN — @require_chart_permission(chart_id)
# =============================================================================

def require_chart_permission(chart_id: str):
    """
    Custom decorator kiểm tra quyền truy cập biểu đồ.

    Luồng xử lý (Pipeline):
    ────────────────────────
    Request đến
        │
        ▼
    ① Lấy email từ request (qua hàm get_current_user_email)
        │── Không có email → trả về 401 Unauthorized
        ▼
    ② Tra cứu user trong hệ thống (qua hàm get_user_info)
        │── Không tìm thấy → trả về 401 Unauthorized
        ▼
    ③ Kiểm tra role của user có quyền xem chart_id không
        │── Không có quyền → trả về 403 Forbidden
        ▼
    ④ Cho phép truy cập → gọi hàm xử lý route gốc
        (truyền thêm biến `current_user` vào kwargs để route sử dụng)

    Tham số:
        chart_id (str): Mã định danh của biểu đồ cần kiểm tra quyền.
                        Ví dụ: "tong-quan", "doanh-thu", "bao-mat".

    Cách sử dụng:
        @app.route("/api/charts/tong-quan")
        @require_chart_permission("tong-quan")
        def chart_tong_quan(current_user):
            ...
    """

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> tuple[Response, int] | Any:
            # ── Bước 1: Lấy email người dùng ──────────────────────
            email: str | None = get_current_user_email()

            if not email:
                return jsonify({
                    "success": False,
                    "error": "UNAUTHORIZED",
                    "message": "Thiếu thông tin xác thực. "
                               "Vui lòng cung cấp email trong header X-Mock-Email.",
                }), 401

            # ── Bước 2: Tra cứu user ──────────────────────────────
            user: dict[str, str] | None = get_user_info(email)

            if user is None:
                return jsonify({
                    "success": False,
                    "error": "UNAUTHORIZED",
                    "message": f"Email '{email}' không tồn tại trong hệ thống.",
                }), 401

            # ── Bước 3: Kiểm tra quyền truy cập biểu đồ ──────────
            role: str = user["role"]
            allowed_charts: list[str] = get_allowed_charts(role)

            if chart_id not in allowed_charts:
                return jsonify({
                    "success": False,
                    "error": "FORBIDDEN",
                    "message": (
                        f"Vai trò '{role}' không có quyền truy cập "
                        f"biểu đồ '{chart_id}'."
                    ),
                }), 403

            # ── Bước 4: Xác thực thành công ────────────────────────
            # Truyền thông tin user vào route handler để sử dụng.
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
# 4. KHỞI TẠO ỨNG DỤNG FLASK
# =============================================================================

app = Flask(__name__)


# =============================================================================
# 5. API ENDPOINTS — Các route biểu đồ được bảo vệ bởi decorator phân quyền
# =============================================================================

@app.route("/")
def dashboard():
    """Trang giao diện Dashboard chính."""
    return render_template("index.html")



@app.route("/api/charts/tong-quan")
@require_chart_permission("tong-quan")
def chart_tong_quan(current_user: dict[str, str]) -> tuple[Response, int]:
    """
    Biểu đồ Tổng quan — Tất cả role đều có quyền xem.
    """
    return jsonify({
        "success": True,
        "chart_id": "tong-quan",
        "chart_name": "Biểu đồ Tổng quan",
        "accessed_by": current_user,
        "data": {
            "total_users": 1250,
            "active_sessions": 342,
            "total_revenue": "1.2B VNĐ",
        },
    }), 200


@app.route("/api/charts/doanh-thu")
@require_chart_permission("doanh-thu")
def chart_doanh_thu(current_user: dict[str, str]) -> tuple[Response, int]:
    """
    Biểu đồ Doanh thu — Chỉ admin và manager được xem.
    """
    return jsonify({
        "success": True,
        "chart_id": "doanh-thu",
        "chart_name": "Biểu đồ Doanh thu",
        "accessed_by": current_user,
        "data": {
            "monthly_revenue": [
                {"month": "01/2026", "value": 120_000_000},
                {"month": "02/2026", "value": 135_000_000},
                {"month": "03/2026", "value": 98_000_000},
                {"month": "04/2026", "value": 142_000_000},
            ],
            "currency": "VNĐ",
        },
    }), 200


@app.route("/api/charts/bao-mat")
@require_chart_permission("bao-mat")
def chart_bao_mat(current_user: dict[str, str]) -> tuple[Response, int]:
    """
    Biểu đồ Bảo mật — Chỉ admin được xem.
    """
    return jsonify({
        "success": True,
        "chart_id": "bao-mat",
        "chart_name": "Biểu đồ Bảo mật",
        "accessed_by": current_user,
        "data": {
            "failed_logins_today": 23,
            "blocked_ips": 5,
            "threat_level": "LOW",
            "last_scan": "2026-05-07T10:30:00+07:00",
        },
    }), 200


# ── Route phụ: Liệt kê các biểu đồ mà user hiện tại được phép xem ────────
@app.route("/api/my-charts")
def my_charts() -> tuple[Response, int]:
    """
    Trả về danh sách chart_id mà user hiện tại có quyền truy cập.
    Hữu ích cho Frontend để render menu/sidebar động.
    """
    email = get_current_user_email()

    if not email:
        return jsonify({
            "success": False,
            "error": "UNAUTHORIZED",
            "message": "Thiếu thông tin xác thực.",
        }), 401

    user = get_user_info(email)

    if user is None:
        return jsonify({
            "success": False,
            "error": "UNAUTHORIZED",
            "message": f"Email '{email}' không tồn tại trong hệ thống.",
        }), 401

    role = user["role"]
    allowed = get_allowed_charts(role)

    return jsonify({
        "success": True,
        "user": {
            "email": email,
            "name": user["name"],
            "role": role,
        },
        "allowed_charts": allowed,
    }), 200


# ── Health check ────────────────────────────────────────────────────────────
@app.route("/api/health")
def health_check() -> tuple[Response, int]:
    """Endpoint kiểm tra server có đang chạy không."""
    return jsonify({"status": "ok", "service": "chart-dashboard-api"}), 200


# =============================================================================
# 6. CHẠY ỨNG DỤNG
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("  Chart Dashboard API - Phase 1 (Mock Data)")
    print("=" * 60)
    print()
    print("  Test with curl:")
    print()
    print('  [OK] Admin xem tong-quan:')
    print('     curl -H "X-Mock-Email: admin@company.com" '
          'http://localhost:5000/api/charts/tong-quan')
    print()
    print('  [OK] Manager xem doanh-thu:')
    print('     curl -H "X-Mock-Email: manager@company.com" '
          'http://localhost:5000/api/charts/doanh-thu')
    print()
    print('  [DENIED] Staff xem bao-mat (403):')
    print('     curl -H "X-Mock-Email: staff@company.com" '
          'http://localhost:5000/api/charts/bao-mat')
    print()
    print('  [DENIED] No header (401):')
    print('     curl http://localhost:5000/api/charts/tong-quan')
    print()
    print("=" * 60)

    app.run(debug=True, host="0.0.0.0", port=5000)
