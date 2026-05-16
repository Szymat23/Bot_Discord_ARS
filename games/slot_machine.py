import discord
import asyncio
import random
import logging
from views.card_view import CardView, make_container

logger = logging.getLogger("CasinoBot")


class GambleView(discord.ui.LayoutView):
    def __init__(self, sm_instance, user_id, user_name, current_win, db, settings, bet, result_text, color):
        super().__init__(timeout=30.0)
        self.sm = sm_instance
        self.user_id = user_id
        self.user_name = user_name
        self.current_win = current_win
        self.db = db
        self.settings = settings
        self.bet = bet
        self.result_text = result_text
        self.color = color
        self.render()

    def render(self):
        self.clear_items()

        gamble_button = discord.ui.Button(
            label="RYZYKUJ (Bonus Spin x2)",
            style=discord.ButtonStyle.danger,
            emoji="🎰"
        )
        gamble_button.callback = self.gamble

        collect_button = discord.ui.Button(
            label="ZABIERZ WYGRANĄ",
            style=discord.ButtonStyle.green,
            emoji="💰"
        )
        collect_button.callback = self.collect

        display_text = (
            f"{self.result_text}\n\n"
            f"Czy ryzykujesz ponowny spin o **x2**?"
        )

        self.add_item(
            make_container(
                display_text,
                self.color,
                gamble_button,
                collect_button
            )
        )

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                view=CardView("### ❌ Komunikat\n\nTo nie Twoja gra!", discord.Color.red()),
                ephemeral=True
            )
            return False
        return True

    async def gamble(self, interaction: discord.Interaction):
        await interaction.response.edit_message(
            view=CardView("### 🔥 Runda dodatkowa\n\nRozpoczyna się bonusowy spin...", discord.Color.gold())
        )
        win_rate = self.settings.get("bonus_win_rate", self.settings.get("win_rate", 0.2))
        await self.sm.animate_gamble_spin(interaction, win_rate, self.current_win, self.bet, self.db)

    async def collect(self, interaction: discord.Interaction):
        user_data = await self.db.get_user(interaction.user.id)

        logger.info(
            f"GRA ZAKOŃCZONA | User: {self.user_name} | Bet: {self.bet} | "
            f"Wygrana: {self.current_win} | RandomNumber: {getattr(self.sm, 'last_api_num', 'N/A')}"
        )

        text = (
            f"### 💰 Wygrana odebrana\n\n"
            f"{self.result_text}"
        )
        await interaction.response.edit_message(
            view=CardView(text, discord.Color.green())
        )


class SlotMachine:
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

    def prepare_result(self, win_chance: float, api_num: int):
        is_win = api_num <= (win_chance * 1000) if api_num else random.random() < win_chance
        self._fill_random_final()
        if is_win:
            target_line = random.randint(0, 4)
            win_symbol = random.randint(1, 5)
            if target_line < 3:
                self.final_matrix[target_line] = [win_symbol] * 3
            elif target_line == 3:
                for i in range(3):
                    self.final_matrix[i][i] = win_symbol
            else:
                for i in range(3):
                    self.final_matrix[i][2 - i] = win_symbol

    def _fill_random_final(self):
        for r in range(3):
            for c in range(3):
                self.final_matrix[r][c] = random.randint(1, 5)

    def check_all_wins(self):
        wins = []
        m = self.final_matrix
        for r in range(3):
            if m[r][0] == m[r][1] == m[r][2]:
                wins.append(r)
            if m[0][r] == m[1][r] == m[2][r]:
                wins.append(r)
        if m[0][0] == m[1][1] == m[2][2]:
            wins.append("d1")
        if m[0][2] == m[1][1] == m[2][0]:
            wins.append("d2")
        return wins

    def format_matrix(self, use_final=False):
        source = self.final_matrix if use_final else self.matrix
        lines = ["`╔══════════════╗`"]
        for row in source:
            row_emoji = [self.number_to_emoji[num] for num in row]
            lines.append(f"`║ ` {' | '.join(row_emoji)} ` ║`")
        lines.append("`╚══════════════╝`")
        return "\n".join(lines)

    async def animate_spin(self, interaction: discord.Interaction, win_rate: float, bet: int, db):
        user_name = interaction.user.name
        api_num = await self.fetch_api_number()
        self.prepare_result(win_rate, api_num)

        await interaction.response.send_message(
            view=CardView("### 🎰 Losowanie...\n\nAutomat zaczyna kręcić.", discord.Color.gold())
        )
        msg = await interaction.original_response()

        for _ in range(3):
            for i in range(3):
                for j in range(3):
                    self.matrix[i][j] = random.randint(1, 5)

            text = (
                f"### 🎰 Losowanie...\n\n"
                f"**Stawka:** `{bet} monet`\n\n"
                f"{self.format_matrix(use_final=False)}"
            )
            await msg.edit(view=CardView(text, discord.Color.gold()))
            await asyncio.sleep(0.7)

        wins = self.check_all_wins()
        is_win = len(wins) > 0
        multiplier = self.settings.get("multiplier", 1.5)
        win_total = int(bet * len(wins) * multiplier) if is_win else 0

        if is_win:
            await db.update_balance(interaction.user.id, win_total)

        await db.add_log(interaction.user.id, "SLOTS_MAIN", bet, win_total)
        user_data = await db.get_user(interaction.user.id)

        if not is_win:
            logger.info(f"GRA ZAKOŃCZONA | User: {user_name} | Bet: {bet} | Wygrana: 0 | RandomNumber: {self.last_api_num}")

        if is_win:
            final_text = (
                f"### 🎰 Wynik\n\n"
                f"{self.format_matrix(use_final=True)}\n\n"
                f"💰 **Trafiono!**\n"
                f"**Stawka:** `{bet} monet`\n"
                f"**Wygrana:** `{win_total} monet`\n"
                f"**Saldo po grze:** `{user_data['balance']} monet`"
            )
            view = GambleView(self, interaction.user.id, user_name, win_total, db, self.settings, bet, final_text, discord.Color.green())
            await msg.edit(view=view)
        else:
            final_text = (
                f"### 🎰 Wynik\n\n"
                f"{self.format_matrix(use_final=True)}\n\n"
                f"😢 **Brak linii**\n"
                f"**Stawka:** `{bet} monet`\n"
                f"**Wygrana:** `0 monet`\n"
                f"**Saldo po grze:** `{user_data['balance']} monet`"
            )
            await msg.edit(view=CardView(final_text, discord.Color.red()))

    async def animate_gamble_spin(self, interaction, win_rate, current_win, bet: int, db):
        user_name = interaction.user.name
        api_num = await self.fetch_api_number()
        self.prepare_result(win_rate, api_num)
        msg = interaction.message

        for _ in range(3):
            for i in range(3):
                for j in range(3):
                    self.matrix[i][j] = random.randint(1, 5)

            text = (
                f"### 🔥 Runda dodatkowa: losowanie...\n\n"
                f"{self.format_matrix(use_final=False)}\n\n"
                f"**Czekaj na wynik...**"
            )
            await msg.edit(view=CardView(text, discord.Color.gold()))
            await asyncio.sleep(0.7)

        wins = self.check_all_wins()
        success = len(wins) > 0

        if success:
            new_win = current_win * 2
            await db.update_balance(interaction.user.id, current_win)
            await db.add_log(interaction.user.id, "GAMBLE_WIN", current_win, new_win)
            user_data = await db.get_user(interaction.user.id)
            logger.info(f"GRA ZAKOŃCZONA | User: {user_name} | Bet: GAMBLE({bet}) | Wygrana: {new_win} | RandomNumber: {self.last_api_num}")

            text = (
                f"### 🎊 Podwojono wygraną!\n\n"
                f"{self.format_matrix(use_final=True)}\n\n"
                f"**Wygrana przed bonusem:** `{current_win} monet`\n"
                f"**Wygrana po bonusie:** `{new_win} monet`\n"
                f"**Saldo po grze:** `{user_data['balance']} monet`"
            )
            color = discord.Color.gold()
        else:
            await db.update_balance(interaction.user.id, -current_win)
            await db.add_log(interaction.user.id, "GAMBLE_LOSS", current_win, 0)
            user_data = await db.get_user(interaction.user.id)
            logger.info(f"GRA ZAKOŃCZONA | User: {user_name} | Bet: GAMBLE({bet}) | Wygrana: 0 | RandomNumber: {self.last_api_num}")

            text = (
                f"### 💀 Przegrana w bonusie\n\n"
                f"{self.format_matrix(use_final=True)}\n\n"
                f"**Wygrana:** `0 monet`\n"
                f"**Saldo po grze:** `{user_data['balance']} monet`"
            )
            color = discord.Color.red()

        await msg.edit(view=CardView(text, color))


class MultiSlotMachine:
    def __init__(self, num_slots, settings, random_queue=None):
        self.num_slots = num_slots
        self.random_queue = random_queue
        self.machines = [SlotMachine(settings, random_queue) for _ in range(num_slots)]
        self.settings = settings
        self.last_api_num = "N/A"

    async def fetch_api_numbers(self):
        for machine in self.machines:
            await machine.fetch_api_number()

    def prepare_results(self, win_chance: float):
        for machine in self.machines:
            api_num = machine.last_api_num if isinstance(machine.last_api_num, int) else None
            machine.prepare_result(win_chance, api_num)

    def check_all_wins(self):
        total_wins = 0
        for machine in self.machines:
            wins = machine.check_all_wins()
            total_wins += len(wins)
        return total_wins

    def format_matrix(self, use_final=False):
        matrices = [machine.format_matrix(use_final).split("\n") for machine in self.machines]
        combined_lines = []
        for i in range(5):
            line_parts = [matrices[j][i] for j in range(self.num_slots)]
            combined_lines.append("   ".join(line_parts))
        return "\n".join(combined_lines)

    async def animate_spin(self, interaction: discord.Interaction, win_rate: float, bet: int, db):
        user_name = interaction.user.name
        await self.fetch_api_numbers()
        self.prepare_results(win_rate)

        await interaction.response.send_message(
            view=CardView("### 🎰 Losowanie...\n\nAutomaty zaczynają kręcić.", discord.Color.gold())
        )
        msg = await interaction.original_response()

        for _ in range(3):
            for machine in self.machines:
                for i in range(3):
                    for j in range(3):
                        machine.matrix[i][j] = random.randint(1, 5)

            text = (
                f"### 🎰 Losowanie...\n\n"
                f"**Stawka:** `{bet} monet` dla jednej maszyny\n\n"
                f"{self.format_matrix(use_final=False)}"
            )
            await msg.edit(view=CardView(text, discord.Color.gold()))
            await asyncio.sleep(0.7)

        total_wins = self.check_all_wins()
        is_win = total_wins > 0
        multiplier = self.settings.get("multiplier", 1.5)
        win_total = int(bet * total_wins * multiplier) if is_win else 0

        if is_win:
            await db.update_balance(interaction.user.id, win_total)

        await db.add_log(interaction.user.id, "SLOTS_MULTI", bet, win_total)
        user_data = await db.get_user(interaction.user.id)
        total_bet = bet * self.num_slots

        if not is_win:
            logger.info(f"GRA ZAKOŃCZONA | User: {user_name} | Bet: {bet} | Wygrana: 0 | Slots: {self.num_slots}")

        if is_win:
            final_text = (
                f"### 🎰 Wynik\n\n"
                f"{self.format_matrix(use_final=True)}\n\n"
                f"💰 **Trafiono!**\n"
                f"**Stawka łączna:** `{total_bet} monet`\n"
                f"**Wygrana:** `{win_total} monet`\n"
                f"**Liczba linii:** `{total_wins}`\n"
                f"**Saldo po grze:** `{user_data['balance']} monet`"
            )
            view = GambleView(self, interaction.user.id, user_name, win_total, db, self.settings, bet, final_text, discord.Color.green())
            await msg.edit(view=view)
        else:
            final_text = (
                f"### 🎰 Wynik\n\n"
                f"{self.format_matrix(use_final=True)}\n\n"
                f"😢 **Brak linii**\n"
                f"**Stawka łączna:** `{total_bet} monet`\n"
                f"**Wygrana:** `0 monet`\n"
                f"**Saldo po grze:** `{user_data['balance']} monet`"
            )
            await msg.edit(view=CardView(final_text, discord.Color.red()))

    async def animate_gamble_spin(self, interaction, win_rate, current_win, bet: int, db):
        user_name = interaction.user.name
        await self.fetch_api_numbers()
        self.prepare_results(win_rate)
        msg = interaction.message

        for _ in range(3):
            for machine in self.machines:
                for i in range(3):
                    for j in range(3):
                        machine.matrix[i][j] = random.randint(1, 5)

            text = (
                f"### 🔥 Runda dodatkowa: losowanie...\n\n"
                f"{self.format_matrix(use_final=False)}\n\n"
                f"**Czekaj na wynik...**"
            )
            await msg.edit(view=CardView(text, discord.Color.gold()))
            await asyncio.sleep(0.7)

        total_wins = self.check_all_wins()
        success = total_wins > 0

        if success:
            new_win = current_win * 2
            await db.update_balance(interaction.user.id, current_win)
            await db.add_log(interaction.user.id, "GAMBLE_WIN", current_win, new_win)
            user_data = await db.get_user(interaction.user.id)
            logger.info(f"GRA ZAKOŃCZONA | User: {user_name} | Bet: GAMBLE({bet}) | Wygrana: {new_win} | Slots: {self.num_slots}")

            text = (
                f"### 🎊 Podwojono wygraną!\n\n"
                f"{self.format_matrix(use_final=True)}\n\n"
                f"**Wygrana przed bonusem:** `{current_win} monet`\n"
                f"**Wygrana po bonusie:** `{new_win} monet`\n"
                f"**Liczba linii:** `{total_wins}`\n"
                f"**Saldo po grze:** `{user_data['balance']} monet`"
            )
            color = discord.Color.gold()
        else:
            await db.update_balance(interaction.user.id, -current_win)
            await db.add_log(interaction.user.id, "GAMBLE_LOSS", current_win, 0)
            user_data = await db.get_user(interaction.user.id)
            logger.info(f"GRA ZAKOŃCZONA | User: {user_name} | Bet: GAMBLE({bet}) | Wygrana: 0 | Slots: {self.num_slots}")

            text = (
                f"### 💀 Przegrana w bonusie\n\n"
                f"{self.format_matrix(use_final=True)}\n\n"
                f"**Wygrana:** `0 monet`\n"
                f"**Saldo po grze:** `{user_data['balance']} monet`"
            )
            color = discord.Color.red()

        await msg.edit(view=CardView(text, color))
