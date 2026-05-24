import discord
from views.card_view import CardView, make_container


class StatsView(discord.ui.LayoutView):
    def __init__(self, bot, user, stats):
        super().__init__(timeout=60)
        self.bot = bot
        self.user = user
        self.message = None
        self.render(stats, "Globalne")

    @property
    def currency(self):
        return self.bot.currency_name_genitive

    def make_text(self, stats, label):
        color_icon = "🟢" if stats["net_change"] >= 0 else "🔴"

        return (
            f"### 📊 Statystyki aktywności\n"
            f"Użytkownik: **{self.user.display_name}**\n\n"
            f"**Zakres:** `{label}`\n\n"
            f"🕹️ **Wszystkie rundy:** `{stats['total_games']}`\n"
            f"✅ **Trafione rundy:** `{stats['successful_rounds']}`\n"
            f"➖ **Rundy bez trafienia:** `{stats['empty_rounds']}`\n"
            f"📈 **Średnia nagroda:** `{stats['avg_reward']:.2f}`\n"
            f"{self.bot.currency_icon} **Zmiana konta:** {color_icon} `{stats['net_change']} {self.currency}`"
        )

    def render(self, stats, label):
        self.clear_items()
        color = discord.Color.green() if stats["net_change"] >= 0 else discord.Color.red()

        button_1h = discord.ui.Button(label="Ostatnia 1h", style=discord.ButtonStyle.secondary)
        button_1h.callback = self.stats_hour

        button_24h = discord.ui.Button(label="Ostatnie 24h", style=discord.ButtonStyle.secondary)
        button_24h.callback = self.stats_day

        button_7d = discord.ui.Button(label="Ostatnie 7 dni", style=discord.ButtonStyle.secondary)
        button_7d.callback = self.stats_week

        button_all = discord.ui.Button(label="Wszystko", style=discord.ButtonStyle.primary)
        button_all.callback = self.stats_all

        self.add_item(make_container(self.make_text(stats, label), color, button_1h, button_24h, button_7d, button_all))

    async def interaction_check(self, interaction: discord.Interaction):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message(
                view=CardView("### ❌ Komunikat\n\nTo nie są twoje statystyki.", discord.Color.red()),
                ephemeral=True
            )
            return False
        return True

    async def update_stats(self, interaction: discord.Interaction, hours, label: str):
        stats = await self.bot.db.get_user_stats(self.user.id, hours)
        self.render(stats, label)
        await interaction.response.edit_message(view=self)

    async def stats_hour(self, interaction: discord.Interaction):
        await self.update_stats(interaction, 1, "Ostatnia 1h")

    async def stats_day(self, interaction: discord.Interaction):
        await self.update_stats(interaction, 24, "Ostatnie 24h")

    async def stats_week(self, interaction: discord.Interaction):
        await self.update_stats(interaction, 168, "Ostatnie 7 dni")

    async def stats_all(self, interaction: discord.Interaction):
        await self.update_stats(interaction, None, "Globalne")

    async def on_timeout(self):
        for item in self.walk_children():
            if isinstance(item, discord.ui.Button):
                item.disabled = True

        if self.message:
            await self.message.edit(view=self)
