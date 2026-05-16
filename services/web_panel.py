from flask import Flask, request, render_template_string
import logging
import asyncio

logger = logging.getLogger("CasinoBot")

app = Flask(__name__)
db_instance = None

EXCHANGE_RATE = 0.01

def verify_blik_code(code):
    return len(code) == 6 and code.isdigit()

HTML_BLIK = """
<!DOCTYPE html>
<html lang="pl">
<head>
    <meta charset="UTF-8">
    <title>Doładowanie Kasyna</title>
    <style>
        body { font-family: 'Segoe UI', sans-serif; background: #1a1a1a; color: white; display: flex; justify-content: center; align-items: center; min-height: 100vh; margin: 0; }
        .container { background: #2a2a2a; padding: 40px; border-radius: 20px; box-shadow: 0 10px 30px rgba(0,0,0,0.5); text-align: center; width: 400px; }
        
        .input-group { margin-bottom: 25px; text-align: left; }
        label { display: block; margin-bottom: 8px; color: #aaa; font-size: 14px; }
        
        .coins-input {
            width: 100%; padding: 12px; border-radius: 10px; border: 2px solid #444;
            background: #333; color: white; font-size: 18px; box-sizing: border-box; outline: none;
        }
        .coins-input:focus { border-color: #ff0055; }

        .price-info { background: #333; padding: 15px; border-radius: 10px; margin-bottom: 25px; border-left: 4px solid #ff0055; }
        .price-info span { color: #ff0055; font-weight: bold; font-size: 20px; }

        .blik-inputs { display: flex; gap: 8px; justify-content: center; margin: 15px 0; }
        .code-input {
            width: 45px; height: 60px; border: 2px solid #444; border-radius: 10px;
            background: #333; color: #ff0055; font-size: 28px; font-weight: bold;
            text-align: center; outline: none; transition: 0.3s;
        }
        .code-input:focus { border-color: #ff0055; box-shadow: 0 0 10px #ff0055; }
        
        button {
            background: #ff0055; color: white; border: none; padding: 15px 40px;
            border-radius: 30px; font-size: 18px; font-weight: bold; cursor: pointer;
            transition: 0.3s; width: 100%; margin-top: 10px;
        }
        button:hover { background: #ff3377; transform: scale(1.02); }
        .msg { margin-top: 20px; font-weight: bold; padding: 10px; border-radius: 10px; }
    </style>
</head>
<body>
    <div class="container">
        <h2 style="color: #ff0055; margin-bottom: 5px;">DOŁADOWANIE</h2>
        <p style="color: #aaa; font-size: 14px; margin-bottom: 30px;">Zasil swoje konto w kilka sekund</p>
        
        <form method="POST">
            <div class="input-group">
                <label>Ilość monet do kupienia:</label>
                <input type="number" name="coins" id="coins" class="coins-input" placeholder="np. 1000" min="1" required oninput="updatePrice()">
            </div>

            <div class="price-info">
                Do zapłaty: <span id="total-price">0.00</span> PLN
            </div>

            <label style="text-align: center;">Wprowadź kod doładowania:</label>
            <div class="blik-inputs">
                <input type="text" name="c1" id="c1" class="code-input" maxlength="1" pattern="[0-9]" required oninput="moveNext(this, 'c2')">
                <input type="text" name="c2" id="c2" class="code-input" maxlength="1" pattern="[0-9]" required oninput="moveNext(this, 'c3')">
                <input type="text" name="c3" id="c3" class="code-input" maxlength="1" pattern="[0-9]" required oninput="moveNext(this, 'c4')">
                <input type="text" name="c4" id="c4" class="code-input" maxlength="1" pattern="[0-9]" required oninput="moveNext(this, 'c5')">
                <input type="text" name="c5" id="c5" class="code-input" maxlength="1" pattern="[0-9]" required oninput="moveNext(this, 'c6')">
                <input type="text" name="c6" id="c6" class="code-input" maxlength="1" pattern="[0-9]" required>
            </div>
            
            <button type="submit">ZAPŁAĆ I DOŁADUJ</button>
        </form>

        {% if message and "Sukces" in message %}
            <div class="msg" style="border: 1px solid #43b581; color: #43b581; background: rgba(67, 181, 129, 0.1);">
                {{ message }}
                <p id="timer">Ta strona zamknie się za <span id="seconds">5</span>s...</p>
            </div>

            <script>
                let seconds = 5;
                const timerElement = document.getElementById('seconds');
                
                const interval = setInterval(() => {
                    seconds--;
                    timerElement.innerText = seconds;
                    if (seconds <= 0) {
                        clearInterval(interval);
                        window.close();
                        document.getElementById('timer').innerHTML = "<b>Możesz już bezpiecznie zamknąć tę kartę i wrócić do Discorda.</b>";
                    }
                }, 1000);
            </script>
        {% elif message %}
            <div class="msg" style="border: 1px solid {{ color }}; color: {{ color }};">
                {{ message }}
            </div>
        {% endif %}
    </div>

    <script>
        const RATE = 0.01; 

        function updatePrice() {
            const coins = document.getElementById('coins').value;
            const price = (coins * RATE).toFixed(2);
            document.getElementById('total-price').innerText = price;
        }

        function moveNext(current, nextFieldID) {
            if (current.value.length >= 1) {
                document.getElementById(nextFieldID).focus();
            }
        }

        document.querySelectorAll('.code-input').forEach(input => {
            input.addEventListener('keydown', (e) => {
                if (e.key === "Backspace" && input.value === "") {
                    const prev = input.previousElementSibling;
                    if (prev) prev.focus();
                }
            });
        });
    </script>
</body>
</html>
"""

@app.route("/pay/<token>", methods=["GET", "POST"])
def pay_page(token):
    message, color = "", "white"
    
    if request.method == "POST":
        coins = request.form.get("coins")
        full_code = "".join([request.form.get(f"c{i}", "") for i in range(1, 7)])
        
        if full_code and coins and db_instance:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(db_instance.make_payment(token, int(coins)))
                if result == "Sukces":
                    message = f"✅ Sukces! Doładowano {coins} monet."
                    color = "#43b581"
                else:
                    message = "❌ Kod nieprawidłowy lub link wygasł."
                    color = "#f04747"
            except Exception as e:
                message = f"❌ Błąd serwera: {str(e)}"
                color = "#f04747"
            finally:
                loop.close()
            
    return render_template_string(HTML_BLIK, message=message, color=color)

def run_server(db_ref):
    global db_instance
    db_instance = db_ref
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False, threaded=True)