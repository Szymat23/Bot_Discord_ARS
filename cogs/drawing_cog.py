import discord
from discord import app_commands
from discord.ext import commands
from games.drawing_game import DrawingGame, MultiDrawingGame
from views.card_view import CardView


class DrawingCog(commands.Cog):
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

    @app_commands.command(name="losowanie", description="Zagraj w losowanie")
    @app_commands.describe(koszt="Ilość respektu używana w tej rundzie")
    async def losowanie(self, interaction: discord.Interaction, koszt: int = None):
        if koszt is None:
            koszt = self.bot.default_entry_cost

        if koszt <= 0:
            return await self.send_error(interaction, "Koszt rundy musi być większy od zera.")

        user_data = await self.bot.db.get_user(interaction.user.id)
        if user_data["balance"] < koszt:
            return await self.send_error(
                interaction,
                f"Nie masz wystarczająco {self.currency}. Posiadasz: `{user_data['balance']}`."
            )

        await self.bot.db.update_balance(interaction.user.id, -koszt)
        success_rate = self.bot.config["drawing_settings"].get("success_rate", 0.2)
        game = DrawingGame(self.bot.config["drawing_settings"], self.bot.random_queue)
        await game.animate(interaction, success_rate, koszt, self.bot.db)

    @app_commands.command(name="multi_losowanie", description="Zagraj w multi losowanie")
    @app_commands.describe(koszt="Ilość respektu na jedno losowanie", liczba="Liczba losowań obok siebie (2-4)")
    async def multi_losowanie(self, interaction: discord.Interaction, koszt: int = None, liczba: int = 3):
        if liczba < 2 or liczba > 4:
            return await self.send_error(interaction, "Liczba losowań musi być między 2 a 4.")

        if koszt is None:
            koszt = self.bot.default_entry_cost

        if koszt <= 0:
            return await self.send_error(interaction, "Koszt rundy musi być większy od zera.")

        total_cost = koszt * liczba
        user_data = await self.bot.db.get_user(interaction.user.id)
        if user_data["balance"] < total_cost:
            return await self.send_error(
                interaction,
                f"Nie masz wystarczająco {self.currency}. Posiadasz: `{user_data['balance']}`, potrzebujesz: `{total_cost}`."
            )

        await self.bot.db.update_balance(interaction.user.id, -total_cost)
        success_rate = self.bot.config["drawing_settings"].get(
            "multi_success_rate",
            self.bot.config["drawing_settings"].get("success_rate", 0.2)
        )
        game = MultiDrawingGame(liczba, self.bot.config["drawing_settings"], self.bot.random_queue)
        await game.animate(interaction, success_rate, koszt, self.bot.db)


async def setup(bot: commands.Bot):
    await bot.add_cog(DrawingCog(bot))
