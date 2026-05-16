import discord
import asyncio
import random
import logging
from views.card_view import CardView, make_container

logger = logging.getLogger("CasinoBot")


class Roulette:
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
        self.total_slots = len(self.wheel_layout)
        self.color_emojis = {
            "red": "🟥",
            "black": "⬛",
            "green": "🟩"
        }
        self.color_names = {
            "red": "czerwony",
            "black": "czarny",
            "green": "zielony"
        }
        self.last_api_num = "N/A"
        self.used_fallback = False

    async def fetch_api_number(self):
        if self.random_queue:
            self.last_api_num = await self.random_queue.get_number()
            self.used_fallback = False
            return self.last_api_num

        self.last_api_num = random.randint(1, 1000)
        self.used_fallback = True
        return self.last_api_num

    def get_slot(self, position):
        number, color = self.wheel_layout[position % self.total_slots]
        return number, color, self.color_emojis[color]

    def format_slot(self, position, active=False):
        number, color, emoji = self.get_slot(position)
        value = f"{emoji}{number:02d}"

        if active:
            return f"⚪ {value}"

        return value

    def format_table(self, active_pos=None):
        rows = []
        row = []

        for position in range(self.total_slots):
            cell = self.format_slot(position, active_pos == position)
            row.append(cell)

            if len(row) == 5:
                rows.append("  ".join(row))
                row = []

        if row:
            rows.append("  ".join(row))

        return "```text\n" + "\n".join(rows) + "\n```"

    def format_strip(self, ball_pos):
        slots = []

        for offset in range(-3, 4):
            position = (ball_pos + offset) % self.total_slots
            active = offset == 0
            slots.append(self.format_slot(position, active))

        return "```text\n" + " | ".join(slots) + "\n```"

    def progress_bar(self, current, total):
        size = 14
        filled = max(1, int((current / total) * size))
        filled = min(filled, size)
        return "▰" * filled + "▱" * (size - filled)

    def build_spin_text(self, user_name, chosen_color, bet, ball_pos, step, total_steps):
        chosen_label = self.color_names.get(chosen_color, chosen_color)
        chosen_emoji = self.color_emojis.get(chosen_color, "🎲")
        progress = self.progress_bar(step, total_steps)

        return (
            f"### 🎡 Ruletka kasyna\n\n"
            f"Gracz: **{user_name}**\n"
            f"Stawka: `{bet} monet`\n"
            f"Wybrany kolor: {chosen_emoji} **{chosen_label}**\n\n"
            f"{self.format_strip(ball_pos)}\n"
            f"**Kręcenie:** `{progress}`"
        )

    def build_result_text(self, user_name, chosen_color, bet, final_pos, win_total, balance):
        number, result_color, result_emoji = self.get_slot(final_pos)
        chosen_label = self.color_names.get(chosen_color, chosen_color)
        chosen_emoji = self.color_emojis.get(chosen_color, "🎲")
        result_label = self.color_names.get(result_color, result_color)

        if win_total > 0:
            title = "### 🟢 Wygrana w ruletce"
            result_line = f"**Wygrana:** `{win_total} monet`"
        else:
            title = "### 🔴 Brak wygranej w ruletce"
            result_line = f"**Wygrana:** `0 monet`"

        return (
            f"{title}\n\n"
            f"Gracz: **{user_name}**\n"
            f"**Stawka:** `{bet} monet`\n"
            f"Wybrano: {chosen_emoji} **{chosen_label}**\n"
            f"Wypadło: {result_emoji} **{number}**, kolor **{result_label}**\n\n"
            f"{self.format_table(final_pos)}\n"
            f"{result_line}\n"
            f"**Saldo po grze:** `{balance} monet`"
        )

    async def animate_spin(self, interaction, chosen_color, bet, db, user_name):
        api_num = await self.fetch_api_number()

        win_chance = self.settings["roulette_settings"].get("win_rate", 0.2)
        is_win = api_num <= int(win_chance * 1000)

        win_slots = [
            i for i, (_, color) in enumerate(self.wheel_layout)
            if color == chosen_color
        ]
        lose_slots = [
            i for i, (_, color) in enumerate(self.wheel_layout)
            if color != chosen_color
        ]

        possible_slots = win_slots if is_win else lose_slots
        final_pos = possible_slots[api_num % len(possible_slots)]

        total_steps = self.total_slots * 2 + final_pos
        msg = await interaction.edit_original_response(
            view=CardView(
                self.build_spin_text(user_name, chosen_color, bet, 0, 1, total_steps),
                discord.Color.gold()
            )
        )

        frame = 0
        for step in range(0, total_steps + 1, 4):
            frame += 1
            text = self.build_spin_text(
                user_name,
                chosen_color,
                bet,
                step % self.total_slots,
                min(step, total_steps),
                total_steps
            )
            await msg.edit(view=CardView(text, discord.Color.gold()))

            if total_steps - step > 20:
                await asyncio.sleep(0.16)
            else:
                await asyncio.sleep(0.32)

        number, result_color, result_emoji = self.get_slot(final_pos)
        is_actually_win = result_color == chosen_color
        multiplier = 14 if result_color == "green" else 2
        win_total = int(bet * multiplier) if is_actually_win else 0

        if is_actually_win:
            await db.update_balance(interaction.user.id, win_total)

        await db.add_log(interaction.user.id, "ROULETTE", bet, win_total)

        user_data = await db.get_user(interaction.user.id)
        logger.info(
            f"RULETKA | User: {user_name} | Bet: {bet} | Win: {win_total} | "
            f"Number: {number} | Color: {result_color} | RandomNumber: {self.last_api_num}"
        )

        card_color = discord.Color.green() if is_actually_win else discord.Color.red()
        text = self.build_result_text(
            user_name,
            chosen_color,
            bet,
            final_pos,
            win_total,
            user_data["balance"]
        )

        await msg.edit(view=CardView(text, card_color))


class RouletteView(discord.ui.LayoutView):
    def __init__(self, roulette_instance, user_id, user_name, bet, db):
        super().__init__(timeout=60.0)
        self.roulette = roulette_instance
        self.user_id = user_id
        self.user_name = user_name
        self.bet = bet
        self.db = db
        self.message = None
        self.render()

    def build_menu_text(self, disabled=False, chosen=None):
        status = "Gra startuje, przyciski zostały zablokowane." if disabled else "Wybierz kolor, na który chcesz postawić."

        chosen_text = ""
        if chosen:
            emoji = self.roulette.color_emojis.get(chosen, "🎲")
            label = self.roulette.color_names.get(chosen, chosen)
            chosen_text = f"\nWybrano: {emoji} **{label}**\n"

        return (
            f"### 🎡 Ruletka kasyna\n\n"
            f"Gracz: **{self.user_name}**\n"
            f"Stawka: `{self.bet} monet`\n"
            f"Możliwa wygrana na 🟥/⬛: `{self.bet * 2} monet`\n"
            f"Możliwa wygrana na 🟩: `{self.bet * 14} monet`\n"
            f"{chosen_text}\n"
            f"{self.roulette.format_table()}\n"
            f"**Status:** {status}"
        )

    def render(self, disabled=False, chosen=None):
        self.clear_items()

        red_button = discord.ui.Button(
            label="Czerwony x2",
            style=discord.ButtonStyle.danger,
            emoji="🟥",
            disabled=disabled
        )
        red_button.callback = self.red

        black_button = discord.ui.Button(
            label="Czarny x2",
            style=discord.ButtonStyle.secondary,
            emoji="⬛",
            disabled=disabled
        )
        black_button.callback = self.black

        green_button = discord.ui.Button(
            label="Zielony x14",
            style=discord.ButtonStyle.success,
            emoji="🟩",
            disabled=disabled
        )
        green_button.callback = self.green

        self.add_item(
            make_container(
                self.build_menu_text(disabled, chosen),
                discord.Color.dark_purple(),
                red_button,
                black_button,
                green_button
            )
        )

    async def interaction_check(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                view=CardView("### ❌ Komunikat\n\nTo nie jest Twoja gra!", discord.Color.red()),
                ephemeral=True
            )
            return False

        return True

    async def red(self, interaction: discord.Interaction):
        await self.start_game(interaction, "red")

    async def black(self, interaction: discord.Interaction):
        await self.start_game(interaction, "black")

    async def green(self, interaction: discord.Interaction):
        await self.start_game(interaction, "green")

    async def start_game(self, interaction, color):
        self.render(disabled=True, chosen=color)
        await interaction.response.edit_message(view=self)
        await self.roulette.animate_spin(
            interaction,
            color,
            self.bet,
            self.db,
            self.user_name
        )

    async def on_timeout(self):
        self.render(disabled=True)
