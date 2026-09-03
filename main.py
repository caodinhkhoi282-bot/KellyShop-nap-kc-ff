import re
import random
import sqlite3
from datetime import datetime, timezone
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

try:
    from supabase import create_client, Client
except ImportError:
    Client = None

# ==========================================
# FULL GIAO DIỆN HTML / CSS / JS
# ==========================================
HTML_CONTENT = """
<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Kelly Shop - Nạp Kim Cương Free Fire</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
        body { background: #f0f2f5; color: #333; padding-bottom: 30px; }
        .header { background: #0066ff; color: white; padding: 15px; display: flex; justify-content: space-between; align-items: center; position: relative; }
        .header h1 { font-size: 18px; font-weight: bold; }
        .header-right { display: flex; align-items: center; gap: 15px; }
        .coin-badge { background: #ffb300; color: #000; padding: 5px 10px; border-radius: 20px; font-weight: bold; font-size: 14px; cursor: pointer; }
        .menu-btn { font-size: 20px; cursor: pointer; background: none; border: none; color: white; }
        .side-menu { display: none; position: absolute; top: 100%; right: 0; background: white; width: 200px; box-shadow: -2px 5px 10px rgba(0,0,0,0.15); z-index: 100; }
        .side-menu a { display: block; padding: 12px 15px; color: #333; text-decoration: none; border-bottom: 1px solid #eee; font-size: 14px; }
        .side-menu a:hover { background: #f5f5f5; color: #0066ff; }
        .service-selector { margin: 15px auto; max-width: 500px; padding: 0 15px; }
        .service-selector select { width: 100%; padding: 12px; border-radius: 8px; border: 2px solid #0066ff; font-weight: bold; font-size: 15px; background: white; color: #0066ff; }
        .container { max-width: 500px; margin: 0 auto; background: white; padding: 20px; border-radius: 12px; box-shadow: 0 2px 10px rgba(0,0,0,0.05); }
        .page { display: none; }
        .page.active { display: block; }
        .badge-verified { background: #e6f0ff; color: #0066ff; padding: 8px 12px; border-radius: 6px; font-size: 13px; font-weight: bold; margin-bottom: 15px; text-align: center; }
        .progress-box { background: #fff8e6; border: 1px solid #ffe0b2; padding: 12px; border-radius: 8px; margin-bottom: 15px; }
        .progress-title { display: flex; justify-content: space-between; font-size: 13px; font-weight: bold; margin-bottom: 5px; }
        .progress-bg { background: #e0e0e0; height: 12px; border-radius: 6px; overflow: hidden; }
        .progress-fill { background: #ff9800; height: 100%; width: 0%; transition: width 0.3s ease; }
        .progress-gift { font-size: 12px; color: #e65100; margin-top: 5px; display: block; font-weight: 500; }
        .form-label { display: block; font-size: 13px; font-weight: bold; margin: 10px 0 4px 0; color: #555; }
        input[type="text"], select { width: 100%; padding: 10px 12px; border: 1px solid #ccc; border-radius: 6px; font-size: 14px; }
        .btn { width: 100%; padding: 12px; background: #0066ff; color: white; border: none; border-radius: 6px; font-weight: bold; font-size: 15px; cursor: pointer; margin-top: 12px; }
        .btn-gold { background: #ffb300; color: #000; }
        .btn-red { background: #ff3333; color: white; margin-top: 8px; display: none; }
        ul { list-style: none; text-align: left; }
        ul li { padding: 10px; border-bottom: 1px solid #eee; font-size: 13px; color: #444; }
    </style>
</head>
<body>

    <div class="header">
        <h1>KELLY SHOP</h1>
        <div class="header-right">
            <div class="coin-badge">🪙 <span id="userCoins">0</span> Xu</div>
            <button class="menu-btn" onclick="toggleMenu()"><i class="fa-solid fa-bars"></i></button>
            <div id="sideMenu" class="side-menu">
                <a href="#" onclick="showPage('home')">Trang Chủ</a>
                <a href="#" onclick="showPage('giftcodePage')">Nhập Giftcode</a>
                <a href="#" onclick="showPage('myHistory')">Lịch Sử Cá Nhân</a>
                <a href="#" onclick="showPage('history')">BXH & Lịch Sử Chung</a>
            </div>
        </div>
    </div>

    <div class="service-selector">
        <select onchange="switchService(this.value)">
            <option value="nap_kc">Nạp Kim Cương / Thẻ Cào</option>
            <option value="vong_quay">Vòng Quay Kim Cương 🪙</option>
        </select>
    </div>

    <div id="home" class="page active">
        <div class="container">
            <div id="napKCSection">
                <div class="badge-verified"><i class="fa-solid fa-shield-halved"></i> Hệ Thống Nạp An Toàn & Tự Động</div>
                <div class="progress-box">
                    <div class="progress-title">
                        <span>Nhiệm Vụ Cấp <span id="questLevel">1</span></span>
                        <span id="questProgressText">0 / 70.000 KC</span>
                    </div>
                    <div class="progress-bg"><div id="questProgressFill" class="progress-fill"></div></div>
                    <span class="progress-gift">🎁 Đạt mốc nhận ngay: +1 Đồng Xu 🪙</span>
                </div>

                <form id="cardForm" onsubmit="handleCardSubmit(event)">
                    <span class="form-label">ID Nhân Vật (Free Fire):</span>
                    <input type="text" id="userId" placeholder="Nhập ID game" required>

                    <span class="form-label">Loại Thẻ:</span>
                    <select id="cardType" required>
                        <option value="Viettel">Viettel</option>
                        <option value="Garena">Garena</option>
                        <option value="Zing">Zing</option>
                    </select>

                    <span class="form-label">Mệnh Giá:</span>
                    <select id="cardAmount" onchange="updateDiamondBonus()" required>
                        <option value="10.000 VNĐ">10.000 VNĐ (💎 500 KC)</option>
                        <option value="20.000 VNĐ">20.000 VNĐ (💎 1.100 KC)</option>
                        <option value="50.000 VNĐ">50.000 VNĐ (💎 2.800 KC)</option>
                    </select>

                    <span class="form-label">Số Seri:</span>
                    <input type="text" id="cardSerial" placeholder="Mã seri" required>

                    <span class="form-label">Mã Thẻ (PIN):</span>
                    <input type="text" id="cardPin" placeholder="Mã pin" required>

                    <button type="submit" class="btn">XÁC NHẬN NẠP THẺ</button>
                    <button type="button" class="btn btn-red" id="btnPayCoin" onclick="handleCoinPayment()">THANH TOÁN BẰNG 1 XU 🪙</button>
                </form>
            </div>

            <div id="vongQuaySection" style="display: none;">
                <div style="text-align: center;">
                    <h3 style="color: #ffb300; margin-bottom: 10px;">🎉 VÒNG QUAY KIM CƯƠNG 🎉</h3>
                    <input type="text" id="wheelUserId" placeholder="Nhập ID game nhận KC">
                    <button class="btn btn-gold" onclick="handleSpinWheel()">SPIN NOW (1 XU) 🎰</button>
                </div>
            </div>
        </div>
    </div>

    <div id="giftcodePage" class="page">
        <div class="container">
            <h3>🎁 Nhập Mã Giftcode</h3>
            <input type="text" id="giftcodeCode" placeholder="Nhập mã (VD: newbie)" style="margin-top: 15px;">
            <button class="btn" onclick="handleRedeemCode()">NHẬN QUÀ</button>
        </div>
    </div>

    <div id="myHistory" class="page">
        <div class="container">
            <h3>📜 Lịch Sử Cá Nhân</h3>
            <ul id="myHistoryList" style="margin-top: 10px;"><li>Đang tải...</li></ul>
        </div>
    </div>

    <div id="history" class="page">
        <div class="container">
            <h3>🏆 Bảng Xếp Hạng Top Nạp</h3>
            <ul id="topList" style="margin-top: 10px;"><li>Đang tải...</li></ul>
            <hr style="margin: 20px 0; border: none; border-top: 1px solid #eee;">
            <h3>⚡ Lịch Sử Nạp Gần Đây</h3>
            <ul id="globalHistoryList" style="margin-top: 10px;"><li>Đang tải...</li></ul>
        </div>
    </div>

    <script>
        function getDeviceUUID() {
            let uuid = localStorage.getItem("device_uuid");
            if (!uuid) {
                uuid = 'dev-' + Math.random().toString(36).substring(2, 15);
                localStorage.setItem("device_uuid", uuid);
            }
            return uuid;
        }

        const DEVICE_UUID = getDeviceUUID();
        let currentDiamondsSelected = "💎 500 KC";

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
            document.getElementById('napKCSection').style.display = (val === 'nap_kc') ? 'block' : 'none';
            document.getElementById('vongQuaySection').style.display = (val === 'vong_quay') ? 'block' : 'none';
        }

        function updateDiamondBonus() {
            const select = document.getElementById('cardAmount');
            const text = select.options[select.selectedIndex].text;
            const match = text.match(/\((.*?)\)/);
            if (match) currentDiamondsSelected = match[1];
        }

        async function loadUserProgress() {
            try {
                const res = await fetch('/api/get-progress', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ device_uuid: DEVICE_UUID })
                });
                const data = await res.json();

                document.getElementById('userCoins').innerText = data.coins || 0;
                document.getElementById('questLevel').innerText = data.quest_level || 1;
                
                const pct = Math.min(100, Math.round((data.total_kc / data.target_kc) * 100));
                document.getElementById('questProgressFill').style.width = pct + '%';
                document.getElementById('questProgressText').innerText = `${(data.total_kc || 0).toLocaleString()} / ${(data.target_kc || 70000).toLocaleString()} KC`;
                
                document.getElementById('btnPayCoin').style.display = (data.coins > 0) ? 'block' : 'none';
            } catch (err) {
                console.error("Lỗi lấy tiến độ:", err);
            }
        }

        async function handleCardSubmit(e) {
            e.preventDefault();
            try {
                const res = await fetch('/api/verify-card', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        user_id: document.getElementById('userId').value,
                        amount: document.getElementById('cardAmount').value,
                        diamonds: currentDiamondsSelected,
                        card_type: document.getElementById('cardType').value,
                        serial: document.getElementById('cardSerial').value,
                        pin: document.getElementById('cardPin').value,
                        device_uuid: DEVICE_UUID,
                        pay_with_coin: false
                    })
                });
                const result = await res.json();
                if (!res.ok) throw new Error(result.detail);

                alert("✅ " + result.message);
                document.getElementById('cardForm').reset();
                loadUserProgress();
            } catch (err) { alert("❌ Lỗi: " + err.message); }
        }

        async function handleCoinPayment() {
            const userId = document.getElementById('userId').value;
            if (!userId) return alert("Vui lòng nhập ID Game!");

            try {
                const res = await fetch('/api/verify-card', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        user_id: userId,
                        amount: document.getElementById('cardAmount').value,
                        diamonds: currentDiamondsSelected,
                        card_type: "COIN_PAYMENT",
                        serial: "COIN_PAY",
                        pin: "COIN_PAY",
                        device_uuid: DEVICE_UUID,
                        pay_with_coin: true
                    })
                });
                const result = await res.json();
                if (!res.ok) throw new Error(result.detail);

                alert("🎉 " + result.message);
                loadUserProgress();
            } catch (err) { alert("❌ Lỗi: " + err.message); }
        }

        async function handleSpinWheel() {
            try {
                const res = await fetch('/api/spin-wheel', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ device_uuid: DEVICE_UUID, user_id: document.getElementById('wheelUserId').value })
                });
                const result = await res.json();
                if (!res.ok) throw new Error(result.detail);

                alert(result.message);
                loadUserProgress();
            } catch (err) { alert("❌ Lỗi: " + err.message); }
        }

        async function handleRedeemCode() {
            try {
                const res = await fetch('/api/redeem-code', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ code: document.getElementById('giftcodeCode').value, device_uuid: DEVICE_UUID })
                });
                const result = await res.json();
                if (!res.ok) throw new Error(result.detail);

                alert("🎉 " + result.message);
                document.getElementById('giftcodeCode').value = "";
                loadUserProgress();
            } catch (err) { alert("❌ Lỗi: " + err.message); }
        }

        async function fetchHistoryData() {
            try {
                const res = await fetch(`/api/history?device_uuid=${DEVICE_UUID}`);
                const data = await res.json();

                const myHistoryList = document.getElementById('myHistoryList');
                if (data.my_history && data.my_history.length > 0) {
                    myHistoryList.innerHTML = data.my_history.map(item => 
                        `<li><b>${item.date}</b> - ID: <code>${item.user_id}</code> - Gói: <b>${item.diamonds}</b> (${item.amount}) - Trạng thái: <span style="color:green;">${item.status}</span></li>`
                    ).join('');
                } else {
                    myHistoryList.innerHTML = '<li>Chưa có lịch sử giao dịch nào.</li>';
                }

                const topList = document.getElementById('topList');
                if (data.top_users && data.top_users.length > 0) {
                    topList.innerHTML = data.top_users.map((item, index) => 
                        `<li><b>TOP ${index + 1}:</b> ID <code>${item.user_id}</code> - Tổng KC: <b style="color:#d9534f;">${item.total_kc.toLocaleString()} 💎</b></li>`
                    ).join('');
                } else {
                    topList.innerHTML = '<li>Chưa có dữ liệu bảng xếp hạng.</li>';
                }

                const globalHistoryList = document.getElementById('globalHistoryList');
                if (data.global_history && data.global_history.length > 0) {
                    globalHistoryList.innerHTML = data.global_history.map(item => 
                        `<li>⚡ <b>${item.user_id}</b> vừa nạp thành công <b>${item.diamonds}</b> (${item.time_ago})</li>`
                    ).join('');
                } else {
                    globalHistoryList.innerHTML = '<li>Chưa có giao dịch gần đây.</li>';
                }
            } catch (err) {
                console.error("Lỗi lấy dữ liệu lịch sử:", err);
            }
        }

        window.addEventListener('DOMContentLoaded', () => {
            updateDiamondBonus();
            loadUserProgress();
        });
    </script>
</body>
</html>
"""

# ==========================================
# BACKEND PYTHON & DATABASE
# ==========================================
SUPABASE_URL = "https://sdeixbihpbiuqcuagxqi.supabase.co"
SUPABASE_KEY = "sb_publishable_1rDqbrmjaUAVmMuyxhW3Dg_9uLMOz4B"

supabase: Optional[Client] = None
if Client and SUPABASE_KEY and not SUPABASE_KEY.startswith("sb_publishable"):
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception:
        pass

def init_sqlite():
    conn = sqlite3.connect("shop.db")
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS users (device_uuid TEXT PRIMARY KEY, coins INTEGER DEFAULT 0, quest_level INTEGER DEFAULT 1, total_kc INTEGER DEFAULT 0)")
    cursor.execute("CREATE TABLE IF NOT EXISTS history (id INTEGER PRIMARY KEY AUTOINCREMENT, device_uuid TEXT, user_id TEXT, amount TEXT, diamonds TEXT, card_type TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
    cursor.execute("CREATE TABLE IF NOT EXISTS redeemed_codes (device_uuid TEXT, code TEXT, PRIMARY KEY (device_uuid, code))")
    conn.commit()
    conn.close()

init_sqlite()

app = FastAPI()
QUEST_TARGETS = {1: 70000, 2: 150000, 3: 300000}

class ProgressRequest(BaseModel):
    device_uuid: str

class VerifyCardRequest(BaseModel):
    user_id: str
    amount: str
    diamonds: str
    card_type: str
    serial: str
    pin: str
    device_uuid: str
    pay_with_coin: bool = False

class SpinWheelRequest(BaseModel):
    device_uuid: str
    user_id: Optional[str] = ""

class RedeemCodeRequest(BaseModel):
    code: str
    device_uuid: str

def get_sqlite_user(uuid: str):
    conn = sqlite3.connect("shop.db")
    cursor = conn.cursor()
    cursor.execute("SELECT coins, quest_level, total_kc FROM users WHERE device_uuid = ?", (uuid,))
    row = cursor.fetchone()
    if not row:
        cursor.execute("INSERT INTO users VALUES (?, 0, 1, 0)", (uuid,))
        conn.commit()
        conn.close()
        return 0, 1, 0
    conn.close()
    return row[0], row[1], row[2]

def update_sqlite_user(uuid: str, coins: int, quest_level: int, total_kc: int):
    conn = sqlite3.connect("shop.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET coins = ?, quest_level = ?, total_kc = ? WHERE device_uuid = ?", (coins, quest_level, total_kc, uuid))
    conn.commit()
    conn.close()

def add_sqlite_history(uuid: str, user_id: str, amount: str, diamonds: str, card_type: str):
    conn = sqlite3.connect("shop.db")
    cursor = conn.cursor()
    cursor.execute("INSERT INTO history (device_uuid, user_id, amount, diamonds, card_type) VALUES (?, ?, ?, ?, ?)", (uuid, user_id, amount, diamonds, card_type))
    conn.commit()
    conn.close()

@app.get("/", response_class=HTMLResponse)
async def read_root():
    return HTML_CONTENT

@app.post("/api/get-progress")
async def get_progress(req: ProgressRequest):
    coins, quest_level, total_kc = get_sqlite_user(req.device_uuid)
    return {"coins": coins, "quest_level": quest_level, "total_kc": total_kc, "target_kc": QUEST_TARGETS.get(quest_level, 500000)}

@app.post("/api/verify-card")
async def verify_card(req: VerifyCardRequest):
    coins, quest_level, total_kc = get_sqlite_user(req.device_uuid)
    match = re.search(r'\d[\d\.]*', req.diamonds.replace('.', ''))
    kc_amount = int(match.group()) if match else 0

    if req.pay_with_coin:
        if coins < 1:
            raise HTTPException(status_code=400, detail="Không đủ Đồng Xu!")
        coins -= 1
        msg = f"Đổi 1 Xu lấy {req.diamonds} cho ID {req.user_id} thành công!"
    else:
        total_kc += kc_amount
        if total_kc >= QUEST_TARGETS.get(quest_level, 500000):
            quest_level += 1
            coins += 1
            msg = f"Nạp thành công! Nhận {req.diamonds} + 1 Xu 🪙!"
        else:
            msg = f"Nạp thẻ thành công! Đã chuyển {req.diamonds} tới ID {req.user_id}."

    update_sqlite_user(req.device_uuid, coins, quest_level, total_kc)
    add_sqlite_history(req.device_uuid, req.user_id, req.amount, req.diamonds, req.card_type)
    return {"message": msg}

@app.post("/api/spin-wheel")
async def spin_wheel(req: SpinWheelRequest):
    coins, quest_level, total_kc = get_sqlite_user(req.device_uuid)
    if coins < 1:
        raise HTTPException(status_code=400, detail="Bạn cần ít nhất 1 Đồng Xu 🪙!")

    coins -= 1
    won_kc = random.choice([99, 199, 499, 999, 4999, 9999, 99999])
    update_sqlite_user(req.device_uuid, coins, quest_level, total_kc)
    if req.user_id:
        add_sqlite_history(req.device_uuid, req.user_id, "Vòng Quay", f"💎 {won_kc:,} KC", "VONG_QUAY")

    return {"message": f"🎉 Bạn đã quay trúng 💎 {won_kc:,} KC!"}

@app.post("/api/redeem-code")
async def redeem_code(req: RedeemCodeRequest):
    if req.code.strip().lower() != "newbie":
        raise HTTPException(status_code=400, detail="Mã Giftcode không hợp lệ!")

    conn = sqlite3.connect("shop.db")
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM redeemed_codes WHERE device_uuid = ? AND code = ?", (req.device_uuid, "newbie"))
    if cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=400, detail="Đã nhận mã này rồi!")

    cursor.execute("INSERT INTO redeemed_codes VALUES (?, 'newbie')", (req.device_uuid,))
    conn.commit()
    conn.close()

    coins, quest_level, total_kc = get_sqlite_user(req.device_uuid)
    update_sqlite_user(req.device_uuid, coins + 1, quest_level, total_kc)
    return {"message": "Nhập mã thành công! Bạn nhận +1 Đồng Xu 🪙."}

@app.get("/api/history")
async def get_history(device_uuid: str):
    conn = sqlite3.connect("shop.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # 1. Lịch sử cá nhân
    cursor.execute("SELECT user_id, amount, diamonds, created_at FROM history WHERE device_uuid = ? ORDER BY id DESC LIMIT 10", (device_uuid,))
    my_history = [
        {
            "date": r["created_at"].split(" ")[0] if r["created_at"] else "Mới xong",
            "user_id": r["user_id"],
            "amount": r["amount"],
            "diamonds": r["diamonds"],
            "status": "Thành công"
        } for r in cursor.fetchall()
    ]

    # 2. Lịch sử chung toàn shop
    cursor.execute("SELECT user_id, diamonds, created_at FROM history ORDER BY id DESC LIMIT 15")
    global_history = [
        {
            "user_id": r["user_id"],
            "diamonds": r["diamonds"],
            "time_ago": "Vừa xong"
        } for r in cursor.fetchall()
    ]

    # 3. Bảng xếp hạng top nạp
    cursor.execute("SELECT device_uuid, total_kc FROM users WHERE total_kc > 0 ORDER BY total_kc DESC LIMIT 5")
    top_rows = cursor.fetchall()
    top_users = []
    for r in top_rows:
        cursor.execute("SELECT user_id FROM history WHERE device_uuid = ? ORDER BY id DESC LIMIT 1", (r["device_uuid"],))
        last_u = cursor.fetchone()
        top_users.append({
            "user_id": last_u["user_id"] if last_u else "Ẩn danh",
            "total_kc": r["total_kc"]
        })

    conn.close()
    return {
        "my_history": my_history,
        "global_history": global_history,
        "top_users": top_users
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
    
