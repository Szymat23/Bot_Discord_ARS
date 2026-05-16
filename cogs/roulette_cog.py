import discord
from discord import app_commands
from discord.ext import commands
from games.roulette import Roulette, RouletteView
from views.card_view import CardView


class RouletteCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def send_error(self, interaction: discord.Interaction, text: str):
        await interaction.response.send_message(
            view=CardView(f"### ❌ Komunikat\n\n{text}", discord.Color.red()),
            ephemeral=True
        )

    @app_commands.command(name="ruletka", description="Zagraj w Ruletkę i wybierz kolor")
    @app_commands.describe(bet="Kwota, którą chcesz postawić")
    async def ruletka(self, interaction: discord.Interaction, bet: int = None):
        if bet is None:
            bet = self.bot.config["roulette_settings"]["default_bet"]

        if bet <= 0:
            return await self.send_error(interaction, "Stawka musi być większa od zera!")

        user_data = await self.bot.db.get_user(interaction.user.id)
        if user_data["balance"] < bet:
            return await self.send_error(
                interaction,
                f"Nie masz wystarczająco monet! Posiadasz: `{user_data['balance']}`."
            )

        await self.bot.db.update_balance(interaction.user.id, -bet)
        game = Roulette(self.bot.config, self.bot.random_queue)
        view = RouletteView(game, interaction.user.id, interaction.user.name, bet, self.bot.db)
        await interaction.response.send_message(view=view)


async def setup(bot: commands.Bot):
    await bot.add_cog(RouletteCog(bot))
