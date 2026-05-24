import discord
from discord import app_commands
from discord.ext import commands
from games.cards_game import CardsGame
from views.card_view import CardView


class CardsCog(commands.Cog):
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

    @app_commands.command(name="karty", description="Zagraj w karty")
    @app_commands.describe(koszt="Ilość respektu używana w tej rundzie")
    async def karty(self, interaction: discord.Interaction, koszt: int = None):
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

        await interaction.response.defer()
        await self.bot.db.update_balance(interaction.user.id, -koszt)
        game = CardsGame(self.bot.config, self.bot.random_queue)
        await game.start(interaction, koszt, self.bot.db)


async def setup(bot: commands.Bot):
    await bot.add_cog(CardsCog(bot))
