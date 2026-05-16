import discord
from discord import app_commands
from discord.ext import commands
from games.slot_machine import SlotMachine, MultiSlotMachine
from views.card_view import CardView


class SlotsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def send_error(self, interaction: discord.Interaction, text: str):
        await interaction.response.send_message(
            view=CardView(f"### ❌ Komunikat\n\n{text}", discord.Color.red()),
            ephemeral=True
        )

    @app_commands.command(name="slots", description="Zagraj w automat do gier")
    @app_commands.describe(bet="Kwota, za którą chcesz zagrać")
    async def slots(self, interaction: discord.Interaction, bet: int = None):
        if bet is None:
            bet = self.bot.default_bet

        if bet <= 0:
            return await self.send_error(interaction, "Stawka musi być większa od zera!")

        user_data = await self.bot.db.get_user(interaction.user.id)
        if user_data["balance"] < bet:
            return await self.send_error(
                interaction,
                f"Nie masz wystarczająco monet! Posiadasz: `{user_data['balance']}`."
            )

        await self.bot.db.update_balance(interaction.user.id, -bet)
        win_rate = self.bot.config["slots_settings"].get("win_rate", 0.2)
        machine = SlotMachine(self.bot.config["slots_settings"], self.bot.random_queue)
        await machine.animate_spin(interaction, win_rate, bet, self.bot.db)

    @app_commands.command(name="multi_slots", description="Zagraj w kilka automatów obok siebie")
    @app_commands.describe(bet="Kwota, za którą chcesz zagrać na każdy slot", num_slots="Liczba slotów obok siebie (2-4)")
    async def multi_slots(self, interaction: discord.Interaction, bet: int = None, num_slots: int = 3):
        if num_slots < 2 or num_slots > 4:
            return await self.send_error(interaction, "Liczba slotów musi być między 2 a 4!")

        if bet is None:
            bet = self.bot.default_bet

        if bet <= 0:
            return await self.send_error(interaction, "Stawka musi być większa od zera!")

        total_bet = bet * num_slots
        user_data = await self.bot.db.get_user(interaction.user.id)
        if user_data["balance"] < total_bet:
            return await self.send_error(
                interaction,
                f"Nie masz wystarczająco monet! Posiadasz: `{user_data['balance']}`, potrzebujesz: `{total_bet}`."
            )

        await self.bot.db.update_balance(interaction.user.id, -total_bet)
        win_rate = self.bot.config["slots_settings"].get("multi_win_rate", self.bot.config["slots_settings"].get("win_rate", 0.2))
        machine = MultiSlotMachine(num_slots, self.bot.config["slots_settings"], self.bot.random_queue)
        await machine.animate_spin(interaction, win_rate, bet, self.bot.db)


async def setup(bot: commands.Bot):
    await bot.add_cog(SlotsCog(bot))
