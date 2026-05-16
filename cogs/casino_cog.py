import discord
from discord import app_commands
from discord.ext import commands
from views.card_view import CardView
from views.stats_view import StatsView
from views.pay_view import PayView


class CasinoCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def send_error(self, interaction: discord.Interaction, text: str):
        await interaction.response.send_message(
            view=CardView(f"### ❌ Komunikat\n\n{text}", discord.Color.red()),
            ephemeral=True
        )

    @app_commands.command(name="balance", description="Sprawdź stan swojego konta")
    async def balance(self, interaction: discord.Interaction):
        user_data = await self.bot.db.get_user(interaction.user.id)
        text = (
            f"### 💰 Stan konta\n\n"
            f"Gracz: **{interaction.user.display_name}**\n"
            f"Aktualny stan konta: `{user_data['balance']} monet`"
        )
        await interaction.response.send_message(
            view=CardView(text, discord.Color.green())
        )

    @app_commands.command(name="historia", description="Pokazuje Twoje ostatnie gry")
    @app_commands.describe(limit="Ile gier pokazać (domyślnie 10)")
    async def historia(self, interaction: discord.Interaction, limit: int = 10):
        if limit > 100:
            limit = 100

        history = await self.bot.db.get_user_history(interaction.user.id, limit)
        if not history:
            return await self.send_error(interaction, "Nie masz jeszcze historii gier.")

        lines = []
        for g in history:
            status = f"✅ +{g['win_amount']}" if g["win_amount"] > 0 else f"❌ -{g['bet']}"
            lines.append(f"`{g['timestamp']}` | **{status}** | `{g['game_type']}`")

        description = "\n".join(lines)
        if len(description) > 3500:
            description = description[:3500] + "\n..."

        text = (
            f"### 📜 Ostatnie {len(history)} gier\n\n"
            f"{description}"
        )

        await interaction.response.send_message(
            view=CardView(text, discord.Color.blue())
        )

    @app_commands.command(name="stats", description="Twoje statystyki w kasynie")
    async def stats(self, interaction: discord.Interaction):
        s = await self.bot.db.get_user_stats(interaction.user.id)

        if s["total_games"] == 0:
            return await self.send_error(interaction, "Musisz najpierw coś zagrać!")

        view = StatsView(self.bot, interaction.user, s)
        await interaction.response.send_message(view=view)
        view.message = await interaction.original_response()

    @app_commands.command(name="pay", description="Przelej monety innemu graczowi")
    @app_commands.describe(member="Gracz, któremu chcesz przelać monety", amount="Kwota przelewu")
    async def pay(self, interaction: discord.Interaction, member: discord.Member, amount: int):
        if member.id == interaction.user.id:
            return await self.send_error(interaction, "Nie możesz przelać pieniędzy samemu sobie!")

        if member.bot:
            return await self.send_error(interaction, "Boty nie potrzebują pieniędzy.")

        if amount <= 0:
            return await self.send_error(interaction, "Kwota przelewu musi być większa niż 0!")

        sender_data = await self.bot.db.get_user(interaction.user.id)
        if sender_data["balance"] < amount:
            return await self.send_error(
                interaction,
                f"Nie masz wystarczająco środków! Twój balans: `{sender_data['balance']} monet`."
            )

        view = PayView(self.bot, interaction.user, member, amount)
        await interaction.response.send_message(view=view)
        view.message = await interaction.original_response()

    @app_commands.command(name="doladuj", description="Doładuj swoje konto")
    async def doladuj(self, interaction: discord.Interaction):
        token = await self.bot.db.generate_payment_token(interaction.user.id)
        base_url = "http://127.0.0.1:5000"
        payment_url = f"{base_url}/pay/{token}"

        button = discord.ui.Button(
            label="Otwórz Panel Płatności",
            url=payment_url,
            style=discord.ButtonStyle.link,
            emoji="💳"
        )

        text = (
            f"### 💳 Zasilanie konta\n\n"
            f"Witaj **{interaction.user.display_name}**!\n\n"
            f"Wygenerowaliśmy dla Ciebie link do doładowania monet.\n"
            f"Link wygaśnie za **15 minut**.\n\n"
            f"**Instrukcja:**\n"
            f"1. Kliknij przycisk poniżej.\n"
            f"2. Wpisz ilość monet.\n"
            f"3. Zatwierdź kodem BLIK."
        )

        await interaction.response.send_message(
            view=CardView(text, discord.Color.from_rgb(255, 0, 85), buttons=[button]),
            ephemeral=True
        )

    @app_commands.command(name="help", description="Wyświetla listę dostępnych komend kasyna")
    async def help_command(self, interaction: discord.Interaction):
        text = (
            f"### 🎮 Gaming Casino — Centrum Pomocy\n\n"
            f"Witaj w naszym kasynie! Poniżej znajdziesz listę dostępnych komend i gier.\n\n"
            f"**Gry**\n"
            f"`/slots [bet]` — klasyczny automat. Domyślna stawka: `{self.bot.default_bet}`\n"
            f"`/multi_slots [bet] [num_slots]` — kilka automatów obok siebie.\n"
            f"`/ruletka [bet]` — wybór koloru: czerwony, czarny albo zielony.\n"
            f"`/blackjack [bet]` — gra w blackjacka.\n\n"
            f"**Ekonomia**\n"
            f"`/balance` — sprawdza stan konta.\n"
            f"`/historia [limit]` — pokazuje ostatnie gry.\n"
            f"`/stats` — pokazuje statystyki.\n"
            f"`/pay [member] [amount]` — przelew monet.\n"
            f"`/doladuj` — doładowanie konta."
        )

        await interaction.response.send_message(
            view=CardView(text, discord.Color.gold()),
            ephemeral=True
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(CasinoCog(bot))
