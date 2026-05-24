import discord
import asyncio
import random
import logging
from views.card_view import CardView, make_container

logger = logging.getLogger("EconomyBot")


class ColorsGame:
    def __init__(self, settings, random_queue=None):
        self.settings = settings
        self.random_queue = random_queue
        self.wheel_layout = [
            (0, "green"),
            (32, "red"), (15, "black"), (19, "red"), (4, "black"),
            (21, "red"), (2, "black"), (25, "red"), (17, "black"),
            (34, "red"), (6, "black"), (27, "red"), (13, "black"),
            (36, "red"), (11, "black"), (30, "red"), (8, "black"),
            (23, "red"), (10, "black"), (5, "red"), (24, "black"),
            (16, "red"), (33, "black"), (1, "red"), (20, "black"),
            (14, "red"), (31, "black"), (9, "red"), (22, "black"),
            (18, "red"), (29, "black"), (7, "red"), (28, "black"),
            (12, "red"), (35, "black"), (3, "red"), (26, "black")
        ]
        self.total_fields = len(self.wheel_layout)
        self.color_emojis = {"red": "🟥", "black": "⬛", "green": "🟩"}
        self.color_names = {"red": "czerwony", "black": "czarny", "green": "zielony"}
        self.last_api_num = "N/A"

    async def fetch_api_number(self):
        if self.random_queue:
            self.last_api_num = await self.random_queue.get_number()
            return self.last_api_num
        self.last_api_num = random.randint(1, 1000)
        return self.last_api_num

    def get_field(self, position):
        number, color = self.wheel_layout[position % self.total_fields]
        return number, color, self.color_emojis[color]

    def format_field(self, position, active=False):
        number, color, emoji = self.get_field(position)
        value = f"{emoji}{number:02d}"
        if active:
            return f"⚪ {value}"
        return value

    def format_table(self, active_pos=None):
        rows = []
        row = []
        for position in range(self.total_fields):
            row.append(self.format_field(position, active_pos == position))
            if len(row) == 5:
                rows.append("  ".join(row))
                row = []
        if row:
            rows.append("  ".join(row))
        return "```text\n" + "\n".join(rows) + "\n```"

    def format_strip(self, pointer_pos):
        fields = []
        for offset in range(-3, 4):
            position = (pointer_pos + offset) % self.total_fields
            fields.append(self.format_field(position, offset == 0))
        return "```text\n" + " | ".join(fields) + "\n```"

    def progress_bar(self, current, total):
        size = 14
        filled = max(1, int((current / total) * size))
        filled = min(filled, size)
        return "▰" * filled + "▱" * (size - filled)

    def build_animation_text(self, user_name, chosen_color, entry_cost, pointer_pos, step, total_steps, currency):
        chosen_label = self.color_names.get(chosen_color, chosen_color)
        chosen_emoji = self.color_emojis.get(chosen_color, "🎲")
        progress = self.progress_bar(step, total_steps)
        return (
            f"### 🎡 Kolory\n\n"
            f"Użytkownik: **{user_name}**\n"
            f"Koszt rundy: `{entry_cost} {currency}`\n"
            f"Wybrany kolor: {chosen_emoji} **{chosen_label}**\n\n"
            f"{self.format_strip(pointer_pos)}\n"
            f"**Postęp:** `{progress}`"
        )

    def build_result_text(self, user_name, chosen_color, entry_cost, final_pos, reward_total, balance, currency):
        number, result_color, result_emoji = self.get_field(final_pos)
        chosen_label = self.color_names.get(chosen_color, chosen_color)
        chosen_emoji = self.color_emojis.get(chosen_color, "🎲")
        result_label = self.color_names.get(result_color, result_color)

        if reward_total > 0:
            title = "### 🟢 Kolory: trafiony kolor"
            result_line = f"**Nagroda:** `{reward_total} {currency}`"
        else:
            title = "### 🔴 Kolory: brak trafienia"
            result_line = f"**Nagroda:** `0 {currency}`"

        return (
            f"{title}\n\n"
            f"Użytkownik: **{user_name}**\n"
            f"**Koszt rundy:** `{entry_cost} {currency}`\n"
            f"Wybrano: {chosen_emoji} **{chosen_label}**\n"
            f"Wypadło: {result_emoji} **{number}**, kolor **{result_label}**\n\n"
            f"{self.format_table(final_pos)}\n"
            f"{result_line}\n"
            f"**Stan konta:** `{balance} {currency}`"
        )

    async def animate(self, interaction, chosen_color, entry_cost, db, user_name, currency):
        api_num = await self.fetch_api_number()
        success_chance = self.settings["colors_settings"].get("success_rate", 0.2)
        is_success = api_num <= int(success_chance * 1000)

        matching_fields = [index for index, (_, color) in enumerate(self.wheel_layout) if color == chosen_color]
        other_fields = [index for index, (_, color) in enumerate(self.wheel_layout) if color != chosen_color]
        possible_fields = matching_fields if is_success else other_fields
        final_pos = possible_fields[api_num % len(possible_fields)]

        total_steps = self.total_fields * 2 + final_pos
        msg = await interaction.edit_original_response(
            view=CardView(
                self.build_animation_text(user_name, chosen_color, entry_cost, 0, 1, total_steps, currency),
                discord.Color.gold()
            )
        )

        for step in range(0, total_steps + 1, 4):
            text = self.build_animation_text(
                user_name,
                chosen_color,
                entry_cost,
                step % self.total_fields,
                min(step, total_steps),
                total_steps,
                currency
            )
            await msg.edit(view=CardView(text, discord.Color.gold()))
            await asyncio.sleep(0.16 if total_steps - step > 20 else 0.32)

        number, result_color, result_emoji = self.get_field(final_pos)
        is_actually_success = result_color == chosen_color
        multiplier = 14 if result_color == "green" else 2
        reward_total = int(entry_cost * multiplier) if is_actually_success else 0

        if is_actually_success:
            await db.update_balance(interaction.user.id, reward_total)

        await db.add_log(interaction.user.id, "COLORS", entry_cost, reward_total)
        user_data = await db.get_user(interaction.user.id)
        logger.info(
            "KOLORY | User: %s | Cost: %s | Reward: %s | Number: %s | Color: %s | RandomNumber: %s",
            user_name,
            entry_cost,
            reward_total,
            number,
            result_color,
            self.last_api_num
        )

        card_color = discord.Color.green() if is_actually_success else discord.Color.red()
        text = self.build_result_text(user_name, chosen_color, entry_cost, final_pos, reward_total, user_data["balance"], currency)
        await msg.edit(view=CardView(text, card_color))


class ColorsView(discord.ui.LayoutView):
    def __init__(self, colors_instance, user_id, user_name, entry_cost, db, currency):
        super().__init__(timeout=60.0)
        self.colors = colors_instance
        self.user_id = user_id
        self.user_name = user_name
        self.entry_cost = entry_cost
        self.db = db
        self.currency = currency
        self.message = None
        self.render()

    def build_menu_text(self, disabled=False, chosen=None):
        status = "Runda startuje, przyciski zostały zablokowane." if disabled else "Wybierz kolor."
        chosen_text = ""
        if chosen:
            emoji = self.colors.color_emojis.get(chosen, "🎲")
            label = self.colors.color_names.get(chosen, chosen)
            chosen_text = f"\nWybrano: {emoji} **{label}**\n"

        return (
            f"### 🎡 Kolory\n\n"
            f"Użytkownik: **{self.user_name}**\n"
            f"Koszt rundy: `{self.entry_cost} {self.currency}`\n"
            f"Możliwa nagroda za 🟥/⬛: `{self.entry_cost * 2} {self.currency}`\n"
            f"Możliwa nagroda za 🟩: `{self.entry_cost * 14} {self.currency}`\n"
            f"{chosen_text}\n"
            f"{self.colors.format_table()}\n"
            f"**Status:** {status}"
        )

    def render(self, disabled=False, chosen=None):
        self.clear_items()

        red_button = discord.ui.Button(label="Czerwony x2", style=discord.ButtonStyle.danger, emoji="🟥", disabled=disabled)
        red_button.callback = self.red

        black_button = discord.ui.Button(label="Czarny x2", style=discord.ButtonStyle.secondary, emoji="⬛", disabled=disabled)
        black_button.callback = self.black

        green_button = discord.ui.Button(label="Zielony x14", style=discord.ButtonStyle.success, emoji="🟩", disabled=disabled)
        green_button.callback = self.green

        self.add_item(make_container(self.build_menu_text(disabled, chosen), discord.Color.dark_purple(), red_button, black_button, green_button))

    async def interaction_check(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                view=CardView("### ❌ Komunikat\n\nTo nie jest Twoja runda.", discord.Color.red()),
                ephemeral=True
            )
            return False
        return True

    async def red(self, interaction: discord.Interaction):
        await self.start(interaction, "red")

    async def black(self, interaction: discord.Interaction):
        await self.start(interaction, "black")

    async def green(self, interaction: discord.Interaction):
        await self.start(interaction, "green")

    async def start(self, interaction, color):
        self.render(disabled=True, chosen=color)
        await interaction.response.edit_message(view=self)
        await self.colors.animate(interaction, color, self.entry_cost, self.db, self.user_name, self.currency)

    async def on_timeout(self):
        self.render(disabled=True)
