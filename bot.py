import discord
import json
import logging
import os
import sys
import threading
from discord.ext import commands

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from views.card_view import CardView

try:
    from services.web_panel import run_server
except ImportError:
    run_server = None


def load_json_file(filename: str, error_message: str):
    path = os.path.join(BASE_DIR, filename)

    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(error_message)
        sys.exit(1)
    except json.JSONDecodeError as exc:
        print(f"BŁĄD: Plik {filename} ma niepoprawny format JSON: {exc}")
        sys.exit(1)


config = load_json_file("config.json", "BŁĄD: Nie znaleziono pliku config.json!")
token_config = load_json_file("token.json", "BŁĄD: Nie znaleziono pliku token.json!")
BOT_TOKEN = token_config.get("token")

if not BOT_TOKEN or BOT_TOKEN == "WKLEJ_TUTAJ_TOKEN_BOTA":
    print("BŁĄD: Wpisz token bota w pliku token.json!")
    sys.exit(1)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.FileHandler(os.path.join(BASE_DIR, config["files"]["log_file"]), encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("CasinoBot")

class CasinoBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix=config["bot_settings"]["prefix"], intents=intents)
        self.config = config
        self.default_bet = config["slots_settings"]["default_bet"]
        self.db = None
        self.random_queue = None

    async def load_cogs(self) -> None:
        cogs = [
            "cogs.casino_cog",
            "cogs.slots_cog",
            "cogs.roulette_cog",
            "cogs.blackjack_cog",
        ]

        for cog_path in cogs:
            try:
                await self.load_extension(cog_path)
                logger.info("Załadowano cog: %s", cog_path)
            except Exception as exc:
                logger.exception("Błąd ładowania coga %s: %s", cog_path, exc)

    async def sync_commands(self) -> None:
        try:
            logger.info("Syncing command tree...")
            await self.tree.sync()
            logger.info("Command tree synced.")
            logger.info("Registered commands: %s", [c.name for c in self.tree.walk_commands()])
        except Exception as exc:
            logger.exception("Nie udało się zsynchronizować command tree: %s", exc)

    async def setup_hook(self):
        from services.database import DatabaseHandler
        from services.random_queue import RandomQueueService

        database_path = os.path.join(BASE_DIR, config["files"]["database"])
        self.db = DatabaseHandler(database_path, config)
        await self.db.setup()

        self.random_queue = RandomQueueService(config)
        await self.random_queue.connect()

        if run_server:
            flask_thread = threading.Thread(target=run_server, args=(self.db,), daemon=True)
            flask_thread.start()
            logger.info("Serwer WWW uruchomiony na porcie 5000.")
        else:
            logger.warning("Serwer WWW nie został uruchomiony (brak lub problem z modułem web_panel).")

        await self.load_cogs()
        self.tree.on_error = self.on_app_command_error
        await self.sync_commands()


    async def send_bot_error_message(self, target, text: str, ephemeral: bool = False):
        view = CardView(f"### ❌ Komunikat\n\n{text}", discord.Color.red())

        if isinstance(target, discord.Interaction):
            if target.response.is_done():
                await target.followup.send(view=view, ephemeral=ephemeral)
            else:
                await target.response.send_message(view=view, ephemeral=ephemeral)
        else:
            await target.send(view=view)

    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError) -> None:
        if isinstance(error, commands.CommandNotFound):
            await self.send_bot_error_message(
                ctx,
                f"Taka komenda nie istnieje: `{ctx.message.content}`.\nUżyj `/help`, aby zobaczyć dostępne komendy."
            )
            return

        logger.exception("Błąd komendy tekstowej: %s", error)
        await self.send_bot_error_message(
            ctx,
            "Wystąpił błąd podczas wykonywania komendy."
        )

    async def on_app_command_error(self, interaction: discord.Interaction, error: Exception) -> None:
        logger.exception("Błąd komendy slash: %s", error)
        await self.send_bot_error_message(
            interaction,
            "Wystąpił błąd podczas wykonywania komendy slash. Sprawdź dane i spróbuj ponownie.",
            ephemeral=True
        )


    async def close(self) -> None:
        if self.random_queue:
            await self.random_queue.close()
        await super().close()

    async def on_ready(self) -> None:
        if not getattr(self, "_commands_synced", False):
            await self.sync_commands()
            self._commands_synced = True
        logger.info("%s Bot is ready. %s", "=" * 20, "=" * 20)

bot = CasinoBot()

if __name__ == "__main__":
    bot.run(BOT_TOKEN)
