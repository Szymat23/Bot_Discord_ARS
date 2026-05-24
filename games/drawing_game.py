import discord
import asyncio
import random
import logging
from views.card_view import CardView, make_container

logger = logging.getLogger("EconomyBot")
CURRENCY = "respektu"


class BonusView(discord.ui.LayoutView):
    def __init__(self, game_instance, user_id, user_name, current_reward, db, settings, entry_cost, result_text, color):
        super().__init__(timeout=30.0)
        self.game = game_instance
        self.user_id = user_id
        self.user_name = user_name
        self.current_reward = current_reward
        self.db = db
        self.settings = settings
        self.entry_cost = entry_cost
        self.result_text = result_text
        self.color = color
        self.render()

    def render(self):
        self.clear_items()

        bonus_button = discord.ui.Button(
            label="SPRÓBUJ BONUS x2",
            style=discord.ButtonStyle.danger,
            emoji="✨"
        )
        bonus_button.callback = self.bonus_round

        collect_button = discord.ui.Button(
            label="ODBIERZ NAGRODĘ",
            style=discord.ButtonStyle.green,
            emoji="⭐"
        )
        collect_button.callback = self.collect

        display_text = (
            f"{self.result_text}\n\n"
            f"Możesz wykonać dodatkową próbę o **x2**."
        )

        self.add_item(make_container(display_text, self.color, bonus_button, collect_button))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                view=CardView("### ❌ Komunikat\n\nTo nie Twoja runda.", discord.Color.red()),
                ephemeral=True
            )
            return False
        return True

    async def bonus_round(self, interaction: discord.Interaction):
        await interaction.response.edit_message(
            view=CardView("### 🔥 Runda dodatkowa\n\nRozpoczyna się bonusowe losowanie...", discord.Color.gold())
        )
        success_rate = self.settings.get("bonus_success_rate", self.settings.get("success_rate", 0.2))
        await self.game.animate_bonus(interaction, success_rate, self.current_reward, self.entry_cost, self.db)

    async def collect(self, interaction: discord.Interaction):
        logger.info(
            "RUNDA ZAKOŃCZONA | User: %s | Cost: %s | Reward: %s | RandomNumber: %s",
            self.user_name,
            self.entry_cost,
            self.current_reward,
            getattr(self.game, "last_api_num", "N/A")
        )

        text = f"### ⭐ Nagroda odebrana\n\n{self.result_text}"
        await interaction.response.edit_message(view=CardView(text, discord.Color.green()))


class DrawingGame:
    number_to_emoji = {1: "🍒", 2: "🍋", 3: "⭐", 4: "💎", 5: "🍉"}

    def __init__(self, settings, random_queue=None):
        self.settings = settings
        self.random_queue = random_queue
        self.matrix = [[0] * 3 for _ in range(3)]
        self.final_matrix = [[0] * 3 for _ in range(3)]
        self.last_api_num = "N/A"

    async def fetch_api_number(self):
        if self.random_queue:
            self.last_api_num = await self.random_queue.get_number()
        else:
            self.last_api_num = random.randint(1, 1000)
        return self.last_api_num

    def prepare_result(self, success_chance: float, api_num: int):
        is_success = api_num <= (success_chance * 1000) if api_num else random.random() < success_chance
        self._fill_random_final()
        if is_success:
            target_line = random.randint(0, 4)
            success_symbol = random.randint(1, 5)
            if target_line < 3:
                self.final_matrix[target_line] = [success_symbol] * 3
            elif target_line == 3:
                for i in range(3):
                    self.final_matrix[i][i] = success_symbol
            else:
                for i in range(3):
                    self.final_matrix[i][2 - i] = success_symbol

    def _fill_random_final(self):
        for row in range(3):
            for col in range(3):
                self.final_matrix[row][col] = random.randint(1, 5)

    def check_lines(self):
        lines = []
        matrix = self.final_matrix
        for index in range(3):
            if matrix[index][0] == matrix[index][1] == matrix[index][2]:
                lines.append(index)
            if matrix[0][index] == matrix[1][index] == matrix[2][index]:
                lines.append(index)
        if matrix[0][0] == matrix[1][1] == matrix[2][2]:
            lines.append("d1")
        if matrix[0][2] == matrix[1][1] == matrix[2][0]:
            lines.append("d2")
        return lines

    def format_matrix(self, use_final=False):
        source = self.final_matrix if use_final else self.matrix
        rows = ["`╔══════════════╗`"]
        for row in source:
            row_emoji = [self.number_to_emoji[num] for num in row]
            rows.append(f"`║ ` {' | '.join(row_emoji)} ` ║`")
        rows.append("`╚══════════════╝`")
        return "\n".join(rows)

    async def animate(self, interaction: discord.Interaction, success_rate: float, entry_cost: int, db):
        user_name = interaction.user.name
        api_num = await self.fetch_api_number()
        self.prepare_result(success_rate, api_num)

        await interaction.response.send_message(
            view=CardView("### 🎲 Losowanie...\n\nPlansza zaczyna losować.", discord.Color.gold())
        )
        msg = await interaction.original_response()

        for _ in range(3):
            for row in range(3):
                for col in range(3):
                    self.matrix[row][col] = random.randint(1, 5)

            text = (
                f"### 🎲 Losowanie...\n\n"
                f"**Koszt rundy:** `{entry_cost} {CURRENCY}`\n\n"
                f"{self.format_matrix(use_final=False)}"
            )
            await msg.edit(view=CardView(text, discord.Color.gold()))
            await asyncio.sleep(0.7)

        lines = self.check_lines()
        is_success = len(lines) > 0
        multiplier = self.settings.get("multiplier", 1.5)
        reward_total = int(entry_cost * len(lines) * multiplier) if is_success else 0

        if is_success:
            await db.update_balance(interaction.user.id, reward_total)

        await db.add_log(interaction.user.id, "DRAWING_MAIN", entry_cost, reward_total)
        user_data = await db.get_user(interaction.user.id)

        if is_success:
            final_text = (
                f"### 🎲 Wynik\n\n"
                f"{self.format_matrix(use_final=True)}\n\n"
                f"⭐ **Trafiono linię!**\n"
                f"**Koszt rundy:** `{entry_cost} {CURRENCY}`\n"
                f"**Nagroda:** `{reward_total} {CURRENCY}`\n"
                f"**Stan konta:** `{user_data['balance']} {CURRENCY}`"
            )
            view = BonusView(self, interaction.user.id, user_name, reward_total, db, self.settings, entry_cost, final_text, discord.Color.green())
            await msg.edit(view=view)
        else:
            final_text = (
                f"### 🎲 Wynik\n\n"
                f"{self.format_matrix(use_final=True)}\n\n"
                f"➖ **Brak trafionej linii**\n"
                f"**Koszt rundy:** `{entry_cost} {CURRENCY}`\n"
                f"**Nagroda:** `0 {CURRENCY}`\n"
                f"**Stan konta:** `{user_data['balance']} {CURRENCY}`"
            )
            await msg.edit(view=CardView(final_text, discord.Color.red()))

    async def animate_bonus(self, interaction, success_rate, current_reward, entry_cost: int, db):
        user_name = interaction.user.name
        api_num = await self.fetch_api_number()
        self.prepare_result(success_rate, api_num)
        msg = interaction.message

        for _ in range(3):
            for row in range(3):
                for col in range(3):
                    self.matrix[row][col] = random.randint(1, 5)

            text = (
                f"### 🔥 Runda dodatkowa: losowanie...\n\n"
                f"{self.format_matrix(use_final=False)}\n\n"
                f"**Czekaj na wynik...**"
            )
            await msg.edit(view=CardView(text, discord.Color.gold()))
            await asyncio.sleep(0.7)

        lines = self.check_lines()
        success = len(lines) > 0

        if success:
            new_reward = current_reward * 2
            await db.update_balance(interaction.user.id, current_reward)
            await db.add_log(interaction.user.id, "BONUS_OK", current_reward, new_reward)
            user_data = await db.get_user(interaction.user.id)
            logger.info("BONUS OK | User: %s | Cost: %s | Reward: %s | RandomNumber: %s", user_name, entry_cost, new_reward, self.last_api_num)

            text = (
                f"### 🎊 Bonus trafiony\n\n"
                f"{self.format_matrix(use_final=True)}\n\n"
                f"**Nagroda przed bonusem:** `{current_reward} {CURRENCY}`\n"
                f"**Nagroda po bonusie:** `{new_reward} {CURRENCY}`\n"
                f"**Stan konta:** `{user_data['balance']} {CURRENCY}`"
            )
            color = discord.Color.gold()
        else:
            await db.update_balance(interaction.user.id, -current_reward)
            await db.add_log(interaction.user.id, "BONUS_EMPTY", current_reward, 0)
            user_data = await db.get_user(interaction.user.id)
            logger.info("BONUS EMPTY | User: %s | Cost: %s | Reward: 0 | RandomNumber: %s", user_name, entry_cost, self.last_api_num)

            text = (
                f"### ➖ Bonus nietrafiony\n\n"
                f"{self.format_matrix(use_final=True)}\n\n"
                f"**Nagroda:** `0 {CURRENCY}`\n"
                f"**Stan konta:** `{user_data['balance']} {CURRENCY}`"
            )
            color = discord.Color.red()

        await msg.edit(view=CardView(text, color))


class MultiDrawingGame:
    def __init__(self, count, settings, random_queue=None):
        self.count = count
        self.random_queue = random_queue
        self.machines = [DrawingGame(settings, random_queue) for _ in range(count)]
        self.settings = settings
        self.last_api_num = "N/A"

    async def fetch_api_numbers(self):
        for machine in self.machines:
            await machine.fetch_api_number()

    def prepare_results(self, success_chance: float):
        for machine in self.machines:
            api_num = machine.last_api_num if isinstance(machine.last_api_num, int) else None
            machine.prepare_result(success_chance, api_num)

    def check_all_lines(self):
        total_lines = 0
        for machine in self.machines:
            total_lines += len(machine.check_lines())
        return total_lines

    def format_matrix(self, use_final=False):
        matrices = [machine.format_matrix(use_final).split("\n") for machine in self.machines]
        combined_lines = []
        for index in range(5):
            line_parts = [matrices[j][index] for j in range(self.count)]
            combined_lines.append("   ".join(line_parts))
        return "\n".join(combined_lines)

    async def animate(self, interaction: discord.Interaction, success_rate: float, entry_cost: int, db):
        user_name = interaction.user.name
        await self.fetch_api_numbers()
        self.prepare_results(success_rate)

        await interaction.response.send_message(
            view=CardView("### 🎲 Losowanie...\n\nLosowania zaczynają się wykonywać.", discord.Color.gold())
        )
        msg = await interaction.original_response()

        for _ in range(3):
            for machine in self.machines:
                for row in range(3):
                    for col in range(3):
                        machine.matrix[row][col] = random.randint(1, 5)

            text = (
                f"### 🎲 Losowanie...\n\n"
                f"**Koszt:** `{entry_cost} {CURRENCY}` dla jednego losowania\n\n"
                f"{self.format_matrix(use_final=False)}"
            )
            await msg.edit(view=CardView(text, discord.Color.gold()))
            await asyncio.sleep(0.7)

        total_lines = self.check_all_lines()
        is_success = total_lines > 0
        multiplier = self.settings.get("multiplier", 1.5)
        reward_total = int(entry_cost * total_lines * multiplier) if is_success else 0

        if is_success:
            await db.update_balance(interaction.user.id, reward_total)

        await db.add_log(interaction.user.id, "DRAWING_MULTI", entry_cost, reward_total)
        user_data = await db.get_user(interaction.user.id)
        total_cost = entry_cost * self.count

        if is_success:
            final_text = (
                f"### 🎲 Wynik\n\n"
                f"{self.format_matrix(use_final=True)}\n\n"
                f"⭐ **Trafiono!**\n"
                f"**Koszt łączny:** `{total_cost} {CURRENCY}`\n"
                f"**Nagroda:** `{reward_total} {CURRENCY}`\n"
                f"**Liczba trafionych linii:** `{total_lines}`\n"
                f"**Stan konta:** `{user_data['balance']} {CURRENCY}`"
            )
            view = BonusView(self, interaction.user.id, user_name, reward_total, db, self.settings, entry_cost, final_text, discord.Color.green())
            await msg.edit(view=view)
        else:
            final_text = (
                f"### 🎲 Wynik\n\n"
                f"{self.format_matrix(use_final=True)}\n\n"
                f"➖ **Brak trafionej linii**\n"
                f"**Koszt łączny:** `{total_cost} {CURRENCY}`\n"
                f"**Nagroda:** `0 {CURRENCY}`\n"
                f"**Stan konta:** `{user_data['balance']} {CURRENCY}`"
            )
            await msg.edit(view=CardView(final_text, discord.Color.red()))

    async def animate_bonus(self, interaction, success_rate, current_reward, entry_cost: int, db):
        user_name = interaction.user.name
        await self.fetch_api_numbers()
        self.prepare_results(success_rate)
        msg = interaction.message

        for _ in range(3):
            for machine in self.machines:
                for row in range(3):
                    for col in range(3):
                        machine.matrix[row][col] = random.randint(1, 5)

            text = (
                f"### 🔥 Runda dodatkowa: losowanie...\n\n"
                f"{self.format_matrix(use_final=False)}\n\n"
                f"**Czekaj na wynik...**"
            )
            await msg.edit(view=CardView(text, discord.Color.gold()))
            await asyncio.sleep(0.7)

        total_lines = self.check_all_lines()
        success = total_lines > 0

        if success:
            new_reward = current_reward * 2
            await db.update_balance(interaction.user.id, current_reward)
            await db.add_log(interaction.user.id, "BONUS_OK", current_reward, new_reward)
            user_data = await db.get_user(interaction.user.id)
            logger.info("BONUS OK | User: %s | Cost: %s | Reward: %s | Lines: %s", user_name, entry_cost, new_reward, total_lines)

            text = (
                f"### 🎊 Bonus trafiony\n\n"
                f"{self.format_matrix(use_final=True)}\n\n"
                f"**Nagroda przed bonusem:** `{current_reward} {CURRENCY}`\n"
                f"**Nagroda po bonusie:** `{new_reward} {CURRENCY}`\n"
                f"**Liczba trafionych linii:** `{total_lines}`\n"
                f"**Stan konta:** `{user_data['balance']} {CURRENCY}`"
            )
            color = discord.Color.gold()
        else:
            await db.update_balance(interaction.user.id, -current_reward)
            await db.add_log(interaction.user.id, "BONUS_EMPTY", current_reward, 0)
            user_data = await db.get_user(interaction.user.id)
            logger.info("BONUS EMPTY | User: %s | Cost: %s | Reward: 0 | Lines: %s", user_name, entry_cost, total_lines)

            text = (
                f"### ➖ Bonus nietrafiony\n\n"
                f"{self.format_matrix(use_final=True)}\n\n"
                f"**Nagroda:** `0 {CURRENCY}`\n"
                f"**Stan konta:** `{user_data['balance']} {CURRENCY}`"
            )
            color = discord.Color.red()

        await msg.edit(view=CardView(text, color))
