import discord
from discord import app_commands
from discord.ext import commands
from views.card_view import CardView
from views.stats_view import StatsView
from views.transfer_view import TransferView


class EconomyCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @property
    def currency(self):
        return self.bot.currency_name_genitive

    async def send_error(self, interaction: discord.Interaction, text: str):
        await interaction.response.send_message(
            view=CardView(f"### ❌ Komunikat\n\n{text}", discord.Color.red()),
            ephemeral=True
        )

    @app_commands.command(name="konto", description="Sprawdź stan swojego konta")
    async def konto(self, interaction: discord.Interaction):
        user_data = await self.bot.db.get_user(interaction.user.id)
        text = (
            f"### {self.bot.currency_icon} Stan konta\n\n"
            f"Użytkownik: **{interaction.user.display_name}**\n"
            f"Aktualny stan konta: `{user_data['balance']} {self.currency}`"
        )
        await interaction.response.send_message(view=CardView(text, discord.Color.green()))

    @app_commands.command(name="historia", description="Pokazuje Twoje ostatnie aktywności")
    @app_commands.describe(limit="Ile wpisów pokazać (domyślnie 10)")
    async def historia(self, interaction: discord.Interaction, limit: int = 10):
        if limit > 100:
            limit = 100

        history = await self.bot.db.get_user_history(interaction.user.id, limit)
        if not history:
            return await self.send_error(interaction, "Nie masz jeszcze historii aktywności.")

        activity_names = {
            "DRAWING_MAIN": "Losowanie",
            "DRAWING_MULTI": "Multi losowanie",
            "COLORS": "Kolory",
            "CARDS": "Karty",
            "BONUS_OK": "Bonus - trafiony",
            "BONUS_EMPTY": "Bonus - nietrafiony",
            "TRANSFER_SEND": "Przekazano",
            "TRANSFER_RECEIVE": "Odebrano",
        }

        lines = []
        for item in history:
            reward = item["reward_amount"]
            cost = item["entry_cost"]
            status = f"✅ +{reward}" if reward > 0 else f"➖ -{cost}"
            activity_name = activity_names.get(item["activity_type"], item["activity_type"])
            lines.append(f"`{item['timestamp']}` | **{status}** | `{activity_name}`")

        description = "\n".join(lines)
        if len(description) > 3500:
            description = description[:3500] + "\n..."

        text = f"### 📜 Ostatnie wpisy: {len(history)}\n\n{description}"
        await interaction.response.send_message(view=CardView(text, discord.Color.blue()))

    @app_commands.command(name="statystyki", description="Twoje statystyki aktywności")
    async def statystyki(self, interaction: discord.Interaction):
        stats = await self.bot.db.get_user_stats(interaction.user.id)

        if stats["total_games"] == 0:
            return await self.send_error(interaction, "Najpierw wykonaj jakąś aktywność.")

        view = StatsView(self.bot, interaction.user, stats)
        await interaction.response.send_message(view=view)
        view.message = await interaction.original_response()

    @app_commands.command(name="przelej", description="Przekaż respekt innemu użytkownikowi")
    @app_commands.describe(member="Użytkownik, któremu chcesz przekazać respekt", amount="Ilość respektu")
    async def przelej(self, interaction: discord.Interaction, member: discord.Member, amount: int):
        if member.id == interaction.user.id:
            return await self.send_error(interaction, "Nie możesz przekazać punktów samemu sobie.")

        if member.bot:
            return await self.send_error(interaction, "Bot nie potrzebuje punktów ekonomii serwera.")

        if amount <= 0:
            return await self.send_error(interaction, "Ilość musi być większa niż 0.")

        sender_data = await self.bot.db.get_user(interaction.user.id)
        if sender_data["balance"] < amount:
            return await self.send_error(
                interaction,
                f"Nie masz wystarczająco {self.currency}. Aktualnie masz: `{sender_data['balance']} {self.currency}`."
            )

        view = TransferView(self.bot, interaction.user, member, amount)
        await interaction.response.send_message(view=view)
        view.message = await interaction.original_response()

    @app_commands.command(name="doladuj", description="Doładuj swoje konto")
    async def doladuj(self, interaction: discord.Interaction):
        token, topup_code = await self.bot.db.generate_topup_token(interaction.user.id)
        base_url = "http://127.0.0.1:5000"
        topup_url = f"{base_url}/doladuj/{token}"
        expiry_minutes = self.bot.config["topup_settings"].get("expiry_time_token", 15)
        mute_points_unit = self.bot.config["topup_settings"].get("mute_points_unit", 100)
        mute_seconds_per_unit = self.bot.config["topup_settings"].get("mute_seconds_per_unit", 30)

        try:
            await interaction.user.send(
                view=CardView(
                    f"### 🔐 Kod doładowania\n\n"
                    f"Twój 6-cyfrowy kod do wpisania w panelu to:\n\n"
                    f"## `{topup_code}`\n\n"
                    f"Kod jest jednorazowy i wygaśnie za **{expiry_minutes} minut**.",
                    discord.Color.from_rgb(124, 92, 255)
                )
            )
        except discord.Forbidden:
            await self.bot.db.deactivate_token(token)
            return await self.send_error(
                interaction,
                "Nie mogę wysłać Ci kodu w wiadomości prywatnej. Włącz wiadomości prywatne od użytkowników serwera i spróbuj ponownie."
            )

        button = discord.ui.Button(
            label="Otwórz panel doładowania",
            url=topup_url,
            style=discord.ButtonStyle.link,
            emoji="🔐"
        )

        mute_line = ""
        if self.bot.config["topup_settings"].get("mute_enabled", False) and mute_seconds_per_unit > 0:
            mute_line = (
                f"Przelicznik wyciszenia: **{mute_points_unit} {self.currency} = {mute_seconds_per_unit} s**.\n"
            )

        text = (
            f"### 🔐 Doładowanie konta\n\n"
            f"Witaj **{interaction.user.display_name}**!\n\n"
            f"Wygenerowano link do dodania {self.currency}.\n"
            f"Kod do wpisania został wysłany w wiadomości prywatnej na Discordzie.\n"
            f"{mute_line}"
            f"Link i kod wygasną za **{expiry_minutes} minut**.\n\n"
            f"**Instrukcja:**\n"
            f"1. Kliknij przycisk poniżej.\n"
            f"2. Wpisz ilość {self.currency}.\n"
            f"3. Wpisz 6-cyfrowy kod z wiadomości prywatnej.\n"
            f"4. Zatwierdź doładowanie."
        )

        await interaction.response.send_message(
            view=CardView(text, discord.Color.from_rgb(124, 92, 255), buttons=[button]),
            ephemeral=True
        )

    @app_commands.command(name="pomoc", description="Wyświetla listę dostępnych komend")
    async def pomoc(self, interaction: discord.Interaction):
        text = (
            f"### 🎮 Bot ekonomii serwera\n\n"
            f"Poniżej znajdziesz listę dostępnych komend.\n\n"
            f"**Gry losowe**\n"
            f"`/losowanie [koszt]` — klasyczne losowanie. Domyślny koszt: `{self.bot.default_entry_cost} {self.currency}`\n"
            f"`/multi_losowanie [koszt] [liczba]` — kilka losowań obok siebie.\n"
            f"`/kolory [koszt]` — wybór koloru: czerwony, czarny albo zielony.\n"
            f"`/karty [koszt]` — gra w karty.\n\n"
            f"**Ekonomia**\n"
            f"`/konto` — sprawdza stan konta.\n"
            f"`/historia [limit]` — pokazuje ostatnie aktywności.\n"
            f"`/statystyki` — pokazuje statystyki.\n"
            f"`/przelej [użytkownik] [ilość]` — przekazuje respekt.\n"
            f"`/doladuj` — doładowanie konta."
        )

        await interaction.response.send_message(
            view=CardView(text, discord.Color.gold()),
            ephemeral=True
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(EconomyCog(bot))
