# 📊 Chart Dashboard — Teams SSO

Hệ thống Dashboard biểu đồ tích hợp Microsoft Teams, xác thực qua SSO và phân quyền theo vai trò (RBAC).

## 🎯 Tổng quan

Ứng dụng cung cấp API trả về dữ liệu biểu đồ dạng JSON, được nhúng vào Microsoft Teams dưới dạng Tab.  
Mỗi người dùng đăng nhập Teams sẽ được tự động xác thực và chỉ xem được các biểu đồ theo quyền được cấp.

### Luồng hoạt động

```
User mở Tab trong Teams
    → Teams SDK gọi API của Microsoft để lấy JWT Token (SSO)
    → Token chứa thông tin user (tên, email) được ký số bởi Microsoft
    → Frontend gửi token lên Backend qua header Authorization
    → Backend tải khóa công khai từ Microsoft (JWKS endpoint)
    → Xác minh chữ ký token → Đảm bảo token không bị giả mạo
    → Lấy email từ token → Tra bảng phân quyền
    → Trả về dữ liệu biểu đồ theo quyền
```

### Cơ chế xác thực

Ứng dụng sử dụng **Microsoft Teams SSO** (Single Sign-On) để xác thực người dùng:

- **Token JWT**: Khi user mở app trong Teams, Teams SDK tự động gọi API `microsoftTeams.authentication.getAuthToken()` của Microsoft để lấy JWT Token. Token này được Microsoft ký số, đảm bảo không thể giả mạo.
- **Xác minh phía Backend**: Backend gọi Microsoft JWKS endpoint (`login.microsoftonline.com`) để lấy khóa công khai, dùng khóa đó xác minh chữ ký token. Chỉ khi token hợp lệ mới lấy được email để phân quyền.
- **Không cần đăng nhập thủ công**: User đã đăng nhập Teams rồi nên SSO tự động, không cần nhập lại mật khẩu.

## 📁 Cấu trúc dự án

```
phân quyền teams/
├── app.py                  # Backend Flask — API + Xác thực SSO + Phân quyền
├── requirements.txt        # Dependencies
├── manifest.json           # Teams App manifest (đóng gói cùng icons để upload)
├── color.png               # Icon màu cho Teams App
├── outline.png             # Icon outline cho Teams App
├── README.md
└── templates/
    ├── index.html           # Giao diện Dashboard chính
    └── config.html          # Trang cấu hình Tab trong Teams
```

## 🔐 Phân quyền (RBAC)

### Bảng vai trò hiện tại

| Email | Vai trò | Tổng quan | Doanh thu | Bảo mật |
|---|---|:---:|:---:|:---:|
| `tungdt@vietanh-group.com` | admin | ✅ | ✅ | ✅ |
| `hieuptt@vietanh-group.com` | manager | ✅ | ✅ | ❌ |
| `longnv@vietanh-group.com` | manager | ✅ | ✅ | ❌ |
| `lanmh@vietanh-group.com` | restricted | ❌ | ❌ | ❌ |

### Thêm người dùng mới

Hiện tại việc thêm/sửa/xóa người dùng và phân quyền được thực hiện **thủ công trong mã nguồn** (`app.py`), cụ thể tại 2 biến `USERS` (danh sách email → vai trò) và `ROLE_PERMISSIONS` (vai trò → biểu đồ được phép xem). Sau khi sửa code cần deploy lại lên server.

Có 3 vai trò có sẵn: **admin** (xem tất cả), **manager** (xem 2 bảng), **restricted** (không xem gì).

> 📌 **Định hướng phát triển**: Chuyển sang lưu trữ bằng Database (SQL) để quản lý user/role qua giao diện web, không cần sửa code khi thêm/bớt người dùng.

## ⚙️ Cấu hình Azure AD

Ứng dụng sử dụng Microsoft Teams SSO, yêu cầu đăng ký app trên Azure Portal.

| Tham số | Giá trị |
|---|---|
| Client ID | `0dac6051-6c9f-4a8d-927a-e479650587e6` |
| Tenant ID | `4cb604a3-4a60-49f9-9fb1-5dee8a3ec5de` |
| Application ID URI | `api://thanhtung1105.pythonanywhere.com/{client-id}` |

### Cấu hình Azure Portal cần thiết

1. **App registrations** → Tạo app → lấy Client ID, Tenant ID
2. **Expose an API** → Set Application ID URI → Thêm scope `access_as_user`
3. **Authorized client applications** → Thêm:
   - `1fec8e78-bce4-4aaf-ab1b-5451cc387264` (Teams desktop/mobile)
   - `5e3ce6c0-2b1f-4285-8d4b-75ee78787346` (Teams web)

## 🚀 Deploy

### Hosting: PythonAnywhere

URL: `https://thanhtung1105.pythonanywhere.com`

### Cài đặt local (dev)

```bash
# Cài dependencies
pip install -r requirements.txt

# Chạy server
python app.py
```

Server sẽ chạy tại `http://localhost:5000`.

> ⚠️ **Lưu ý**: SSO chỉ hoạt động khi app chạy trong Microsoft Teams. Khi chạy local trên trình duyệt thường sẽ không xác thực được.

### Upload lên Teams

1. Đóng gói `manifest.json` + `color.png` + `outline.png` thành file `.zip`
2. Mở Teams → **Manage Apps** → **Upload a custom app** → chọn file `.zip`

## 🛠️ Tech Stack

| Thành phần | Công nghệ |
|---|---|
| Backend | Python, Flask |
| Frontend | HTML, CSS, JavaScript |
| Xác thực | Microsoft Teams SSO (JWT + JWKS) |
| Hosting | PythonAnywhere |
| SDK | Microsoft Teams JavaScript SDK v2.25.0 |

## 📡 API Endpoints

| Method | Endpoint | Mô tả |
|---|---|---|
| GET | `/` | Trang Dashboard |
| GET | `/config` | Trang cấu hình Tab |
| GET | `/api/my-charts` | Lấy danh sách biểu đồ được phép xem |
| GET | `/api/charts/tong-quan` | Dữ liệu biểu đồ Tổng quan |
| GET | `/api/charts/doanh-thu` | Dữ liệu biểu đồ Doanh thu |
| GET | `/api/charts/bao-mat` | Dữ liệu biểu đồ Bảo mật |
| GET | `/api/debug-token` | Debug thông tin token (dev) |
| GET | `/api/health` | Health check |

> Tất cả API `/api/charts/*` yêu cầu header `Authorization: Bearer <token>`.

## 📌 Roadmap

- [ ] Kết nối Database (thay thế dict hardcode)
- [ ] Trang quản lý user/role (thêm/sửa/xóa không cần sửa code)
- [ ] Tích hợp Microsoft Graph API (lấy ảnh, phòng ban)
- [ ] Dữ liệu biểu đồ thật (thay vì mock data)
- [ ] Chuyển sang Gunicorn/Waitress cho production
