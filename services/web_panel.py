from flask import Flask, request, render_template_string
import logging
import asyncio
from datetime import timedelta

try:
    import discord
except ImportError:
    discord = None

logger = logging.getLogger("EconomyBot")

app = Flask(__name__)
db_instance = None
config_instance = None
bot_instance = None


def verify_topup_code(code):
    return len(code) == 6 and code.isdigit()


def get_topup_settings():
    if not config_instance:
        return {
            "mute_enabled": False,
            "mute_points_unit": 100,
            "mute_seconds_per_unit": 30,
            "guild_id": 0,
            "reason": "Doładowanie respektu przez panel ekonomii"
        }
    return config_instance.get("topup_settings", {})


def get_currency_settings():
    if not config_instance:
        return {
            "currency_name": "respekt",
            "currency_name_genitive": "respektu",
            "currency_icon": "⭐"
        }
    return config_instance.get("economy_settings", {})


def calculate_mute_seconds(amount: int):
    settings = get_topup_settings()
    if not settings.get("mute_enabled", False):
        return 0

    points_unit = int(settings.get("mute_points_unit", 100) or 100)
    seconds_per_unit = int(settings.get("mute_seconds_per_unit", 30) or 0)

    if points_unit <= 0 or seconds_per_unit <= 0 or amount <= 0:
        return 0

    return int((amount / points_unit) * seconds_per_unit)


def format_duration(seconds: int):
    seconds = int(seconds or 0)
    if seconds <= 0:
        return "0 s"

    minutes, sec = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)

    parts = []
    if hours:
        parts.append(f"{hours} godz.")
    if minutes:
        parts.append(f"{minutes} min")
    if sec:
        parts.append(f"{sec} s")

    return " ".join(parts)


async def apply_discord_timeout(user_id: int, mute_seconds: int):
    if discord is None or bot_instance is None:
        return False, "Brak dostępu do Discorda z panelu WWW."

    settings = get_topup_settings()
    if not settings.get("mute_enabled", False):
        return False, "Wyciszenie po doładowaniu jest wyłączone."

    guild_id = int(settings.get("guild_id", 0) or 0)
    if guild_id <= 0 or mute_seconds <= 0:
        return False, "Nie ustawiono guild_id albo przelicznika wyciszenia w config.json."

    guild = bot_instance.get_guild(guild_id)
    if guild is None:
        return False, "Bot nie widzi podanego serwera."

    try:
        member = guild.get_member(user_id) or await guild.fetch_member(user_id)
        until = discord.utils.utcnow() + timedelta(seconds=mute_seconds)
        await member.timeout(until, reason=settings.get("reason", "Doładowanie przez panel ekonomii"))
        return True, f"Użytkownik został wyciszony na {format_duration(mute_seconds)}."
    except Exception as exc:
        logger.warning("Nie udało się wyciszyć użytkownika po doładowaniu: %s", exc)
        return False, str(exc)


def schedule_timeout(user_id: int, mute_seconds: int):
    if bot_instance is None or mute_seconds <= 0:
        return

    try:
        future = asyncio.run_coroutine_threadsafe(apply_discord_timeout(user_id, mute_seconds), bot_instance.loop)
        future.add_done_callback(lambda result: logger.info("Wynik wyciszenia po doładowaniu: %s", result.result()))
    except Exception as exc:
        logger.warning("Nie udało się zaplanować wyciszenia po doładowaniu: %s", exc)


HTML_TOPUP = """
<!DOCTYPE html>
<html lang="pl">
<head>
    <meta charset="UTF-8">
    <title>Doładowanie konta</title>
    <style>
        body { font-family: 'Segoe UI', sans-serif; background: #15151f; color: white; display: flex; justify-content: center; align-items: center; min-height: 100vh; margin: 0; }
        .container { background: #242436; padding: 40px; border-radius: 20px; box-shadow: 0 10px 30px rgba(0,0,0,0.45); text-align: center; width: 420px; }
        .input-group { margin-bottom: 25px; text-align: left; }
        label { display: block; margin-bottom: 8px; color: #c5c5d6; font-size: 14px; }
        .amount-input {
            width: 100%; padding: 12px; border-radius: 10px; border: 2px solid #44445c;
            background: #303047; color: white; font-size: 18px; box-sizing: border-box; outline: none;
        }
        .amount-input:focus { border-color: #7c5cff; }
        .info-box { background: #303047; padding: 15px; border-radius: 10px; margin-bottom: 25px; border-left: 4px solid #7c5cff; text-align: left; }
        .info-box div { margin-bottom: 6px; }
        .info-box div:last-child { margin-bottom: 0; }
        .info-box span { color: #b8a8ff; font-weight: bold; }
        .code-inputs { display: flex; gap: 8px; justify-content: center; margin: 15px 0; }
        .code-input {
            width: 45px; height: 60px; border: 2px solid #44445c; border-radius: 10px;
            background: #303047; color: #b8a8ff; font-size: 28px; font-weight: bold;
            text-align: center; outline: none; transition: 0.3s;
        }
        .code-input:focus { border-color: #7c5cff; box-shadow: 0 0 10px #7c5cff; }
        button {
            background: #7c5cff; color: white; border: none; padding: 15px 40px;
            border-radius: 30px; font-size: 18px; font-weight: bold; cursor: pointer;
            transition: 0.3s; width: 100%; margin-top: 10px;
        }
        button:hover { background: #967dff; transform: scale(1.02); }
        .msg { margin-top: 20px; font-weight: bold; padding: 10px; border-radius: 10px; }
    </style>
</head>
<body>
    <div class="container">
        <h2 style="color: #b8a8ff; margin-bottom: 5px;">DOŁADOWANIE KONTA</h2>
        <p style="color: #c5c5d6; font-size: 14px; margin-bottom: 30px;">Dodaj {{ currency_genitive }} kodem z Discorda</p>
        
        <form method="POST">
            <div class="input-group">
                <label>Ilość {{ currency_genitive }} do dodania:</label>
                <input type="number" name="amount" id="amount" class="amount-input" placeholder="np. 1000" min="1" required oninput="updateMuteTime()">
            </div>

            <div class="info-box">
                <div>Po zatwierdzeniu konto dostanie: <span>{{ currency_icon }} wpisaną ilość {{ currency_genitive }}</span></div>
                {% if mute_enabled %}
                    <div>Przelicznik wyciszenia: <span>{{ mute_points_unit }} {{ currency_genitive }} = {{ mute_seconds_per_unit }} s</span></div>
                    <div>Wyliczony czas wyciszenia: <span id="mutePreview">0 s</span></div>
                {% else %}
                    <div>Wyciszenie po doładowaniu: <span>wyłączone</span></div>
                {% endif %}
            </div>

            <label style="text-align: center;">Wprowadź 6-cyfrowy kod z wiadomości prywatnej na Discordzie:</label>
            <div class="code-inputs">
                <input type="text" name="c1" id="c1" class="code-input" maxlength="1" pattern="[0-9]" required oninput="moveNext(this, 'c2')">
                <input type="text" name="c2" id="c2" class="code-input" maxlength="1" pattern="[0-9]" required oninput="moveNext(this, 'c3')">
                <input type="text" name="c3" id="c3" class="code-input" maxlength="1" pattern="[0-9]" required oninput="moveNext(this, 'c4')">
                <input type="text" name="c4" id="c4" class="code-input" maxlength="1" pattern="[0-9]" required oninput="moveNext(this, 'c5')">
                <input type="text" name="c5" id="c5" class="code-input" maxlength="1" pattern="[0-9]" required oninput="moveNext(this, 'c6')">
                <input type="text" name="c6" id="c6" class="code-input" maxlength="1" pattern="[0-9]" required>
            </div>
            
            <button type="submit">POTWIERDŹ DOŁADOWANIE</button>
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
        const muteEnabled = {{ mute_enabled_js }};
        const mutePointsUnit = {{ mute_points_unit }};
        const muteSecondsPerUnit = {{ mute_seconds_per_unit }};

        function formatDuration(totalSeconds) {
            totalSeconds = Math.max(0, Math.floor(totalSeconds));
            const hours = Math.floor(totalSeconds / 3600);
            const minutes = Math.floor((totalSeconds % 3600) / 60);
            const seconds = totalSeconds % 60;
            const parts = [];
            if (hours > 0) parts.push(hours + " godz.");
            if (minutes > 0) parts.push(minutes + " min");
            if (seconds > 0) parts.push(seconds + " s");
            return parts.length ? parts.join(" ") : "0 s";
        }

        function updateMuteTime() {
            if (!muteEnabled) return;
            const amountInput = document.getElementById('amount');
            const preview = document.getElementById('mutePreview');
            const amount = parseInt(amountInput.value || "0");
            const seconds = mutePointsUnit > 0 ? (amount / mutePointsUnit) * muteSecondsPerUnit : 0;
            preview.innerText = formatDuration(seconds);
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

        updateMuteTime();
    </script>
</body>
</html>
"""


@app.route("/doladuj/<token>", methods=["GET", "POST"])
def topup_page(token):
    message, color = "", "white"
    topup_settings = get_topup_settings()
    currency_settings = get_currency_settings()
    mute_enabled = bool(topup_settings.get("mute_enabled", False))
    mute_points_unit = int(topup_settings.get("mute_points_unit", 100) or 100)
    mute_seconds_per_unit = int(topup_settings.get("mute_seconds_per_unit", 30) or 0)
    currency_name = currency_settings.get("currency_name", "respekt")
    currency_genitive = currency_settings.get("currency_name_genitive", "respektu")
    currency_icon = currency_settings.get("currency_icon", "⭐")
    
    if request.method == "POST":
        amount = request.form.get("amount")
        full_code = "".join([request.form.get(f"c{i}", "") for i in range(1, 7)])
        
        if full_code and amount and db_instance:
            if not verify_topup_code(full_code):
                message = "❌ Kod musi mieć dokładnie 6 cyfr."
                color = "#f04747"
            else:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    amount_int = int(amount)
                    mute_seconds = calculate_mute_seconds(amount_int)
                    result = loop.run_until_complete(db_instance.make_topup(token, amount_int, full_code))
                    if result.get("status") == "Sukces":
                        if mute_enabled and mute_seconds > 0:
                            schedule_timeout(int(result["user_id"]), mute_seconds)
                        message = f"✅ Sukces! Dodano {amount_int} {currency_genitive}."
                        if mute_enabled and mute_seconds > 0:
                            message += f" Wyciszenie na Discordzie: {format_duration(mute_seconds)}."
                        color = "#43b581"
                    else:
                        message = "❌ Kod nieprawidłowy lub link wygasł."
                        color = "#f04747"
                except Exception as e:
                    message = f"❌ Błąd serwera: {str(e)}"
                    color = "#f04747"
                finally:
                    loop.close()
            
    return render_template_string(
        HTML_TOPUP,
        message=message,
        color=color,
        mute_enabled=mute_enabled,
        mute_enabled_js="true" if mute_enabled else "false",
        mute_points_unit=mute_points_unit,
        mute_seconds_per_unit=mute_seconds_per_unit,
        currency_name=currency_name,
        currency_genitive=currency_genitive,
        currency_icon=currency_icon
    )


def run_server(db_ref, config_ref=None, bot_ref=None):
    global db_instance, config_instance, bot_instance
    db_instance = db_ref
    config_instance = config_ref or {}
    bot_instance = bot_ref
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False, threaded=True)
