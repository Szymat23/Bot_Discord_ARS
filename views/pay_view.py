import discord
from views.card_view import CardView, make_container


class PayView(discord.ui.LayoutView):
    def __init__(self, bot, sender, receiver, amount):
        super().__init__(timeout=60)
        self.bot = bot
        self.sender = sender
        self.receiver = receiver
        self.amount = amount
        self.message = None

        self.render_confirmation()

    def confirmation_text(self):
        return (
            f"### 💸 Potwierdzenie przelewu\n\n"
            f"**Od:** {self.sender.mention}\n"
            f"**Dla:** {self.receiver.mention}\n"
            f"**Kwota:** `{self.amount} monet`\n\n"
            f"Czy na pewno chcesz wykonać ten przelew?"
        )

    def render_confirmation(self):
        self.clear_items()

        confirm_button = discord.ui.Button(label="Potwierdź", style=discord.ButtonStyle.success)
        confirm_button.callback = self.confirm_transfer

        cancel_button = discord.ui.Button(label="Anuluj", style=discord.ButtonStyle.danger)
        cancel_button.callback = self.cancel_transfer

        self.add_item(
            make_container(
                self.confirmation_text(),
                discord.Color.gold(),
                confirm_button,
                cancel_button
            )
        )

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.sender.id:
            await interaction.response.send_message(
                view=CardView("### ❌ Komunikat\n\nTylko osoba wykonująca przelew może używać tych przycisków.", discord.Color.red()),
                ephemeral=True
            )
            return False
        return True

    async def confirm_transfer(self, interaction: discord.Interaction):
        sender_data = await self.bot.db.get_user(self.sender.id)

        if sender_data["balance"] < self.amount:
            text = (
                f"### ❌ Przelew anulowany\n\n"
                f"Nie masz już wystarczająco środków.\n"
                f"Twój balans: `{sender_data['balance']} monet`"
            )
            return await interaction.response.edit_message(
                view=CardView(text, discord.Color.red())
            )

        await self.bot.db.update_balance(self.sender.id, -self.amount)
        await self.bot.db.get_user(self.receiver.id)
        await self.bot.db.update_balance(self.receiver.id, self.amount)
        await self.bot.db.add_log(self.sender.id, "TRANSFER_SEND", self.amount, 0)
        await self.bot.db.add_log(self.receiver.id, "TRANSFER_RECEIVE", 0, self.amount)

        text = (
            f"### ✅ Przelew zakończony\n\n"
            f"**Od:** {self.sender.mention}\n"
            f"**Dla:** {self.receiver.mention}\n"
            f"**Kwota:** `{self.amount} monet`"
        )

        await interaction.response.edit_message(
            view=CardView(text, discord.Color.green())
        )

    async def cancel_transfer(self, interaction: discord.Interaction):
        await interaction.response.edit_message(
            view=CardView("### ❌ Przelew został anulowany", discord.Color.red())
        )

    async def on_timeout(self):
        for item in self.walk_children():
            if isinstance(item, discord.ui.Button):
                item.disabled = True

        if self.message:
            try:
                await self.message.edit(view=self)
            except Exception:
                pass
