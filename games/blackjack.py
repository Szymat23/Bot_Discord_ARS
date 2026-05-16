import discord
import random
import logging
from views.card_view import CardView, make_container

logger = logging.getLogger("CasinoBot")


class BlackjackView(discord.ui.LayoutView):
    def __init__(self, game_instance, user_id, bet, db, status="Twoja kolej...", color=discord.Color.blue()):
        super().__init__(timeout=60.0)
        self.game = game_instance
        self.user_id = user_id
        self.bet = bet
        self.db = db
        self.render(status, color)

    def render(self, status, color, show_dealer=False):
        self.clear_items()

        hit_button = discord.ui.Button(label="Dobierz (Hit)", style=discord.ButtonStyle.primary, emoji="🃏")
        hit_button.callback = self.hit

        stand_button = discord.ui.Button(label="Pas (Stand)", style=discord.ButtonStyle.secondary, emoji="🛑")
        stand_button.callback = self.stand

        self.add_item(
            make_container(
                self.game.create_text(status, show_dealer),
                color,
                hit_button,
                stand_button
            )
        )

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                view=CardView("### ❌ Komunikat\n\nTo nie Twoje rozdanie!", discord.Color.red()),
                ephemeral=True
            )
            return False
        return True

    async def hit(self, interaction: discord.Interaction):
        await interaction.response.defer()

        card = await self.game.draw_card()
        self.game.player_hand.append(card)
        score = self.game.calculate_score(self.game.player_hand)

        if score > 21:
            await self.game.end_game(
                interaction,
                "FURA (Bust) 💀 - Przekroczyłeś 21!",
                discord.Color.red(),
                0
            )
        else:
            self.render("Dobierasz czy pasujesz?", discord.Color.blue())
            await interaction.edit_original_response(view=self)

    async def stand(self, interaction: discord.Interaction):
        await interaction.response.defer()
        await self.game.dealer_turn(interaction)


class Blackjack:
    def __init__(self, settings=None, random_queue=None):
        self.settings = settings or {}
        self.random_queue = random_queue
        self.suits = ["♠️", "♥️", "♦️", "♣️"]
        self.ranks = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"]
        self.deck = self.generate_deck()
        self.player_hand = []
        self.dealer_hand = []
        self.bet = 0
        self.api_numbers = []
        self.last_api_num = "N/A"

    def generate_deck(self):
        return [f"{r}{s}" for r in self.ranks for s in self.suits]

    async def fetch_api_number(self):
        if self.random_queue:
            number = await self.random_queue.get_number()
        else:
            number = random.randint(1, 1000)

        self.last_api_num = number
        self.api_numbers.append(number)
        return number

    async def draw_card(self):
        if not self.deck:
            self.deck = self.generate_deck()

        api_num = await self.fetch_api_number()
        card_index = api_num % len(self.deck)
        return self.deck.pop(card_index)

    def calculate_score(self, hand):
        score = 0
        aces = 0
        values = {
            "2": 2,
            "3": 3,
            "4": 4,
            "5": 5,
            "6": 6,
            "7": 7,
            "8": 8,
            "9": 9,
            "10": 10,
            "J": 10,
            "Q": 10,
            "K": 10,
            "A": 11
        }

        for card in hand:
            rank = card[:-2]
            score += values[rank]
            if rank == "A":
                aces += 1

        while score > 21 and aces:
            score -= 10
            aces -= 1

        return score

    def format_hand(self, hand, hide_first=False):
        if hide_first:
            return f"🎴, {hand[1]}"
        return ", ".join(hand)

    def format_api_numbers(self):
        if not self.api_numbers:
            return "brak"

        numbers = [str(number) for number in self.api_numbers[-6:]]
        return ", ".join(numbers)

    async def start_game(self, interaction, bet, db):
        self.bet = bet
        self.player_hand = [await self.draw_card(), await self.draw_card()]
        self.dealer_hand = [await self.draw_card(), await self.draw_card()]

        if self.calculate_score(self.player_hand) == 21:
            payout = int(bet * 2.5)
            await db.update_balance(interaction.user.id, payout)
            await db.add_log(interaction.user.id, "BLACKJACK", bet, payout)
            await self.end_game(
                interaction,
                "BLACKJACK! 🃏✨",
                discord.Color.gold(),
                payout,
                is_start=True
            )
            return

        view = BlackjackView(self, interaction.user.id, bet, db)

        if interaction.response.is_done():
            await interaction.edit_original_response(view=view)
        else:
            await interaction.response.send_message(view=view)

    def create_text(self, status, show_dealer=False):
        p_score = self.calculate_score(self.player_hand)

        if show_dealer:
            d_score = self.calculate_score(self.dealer_hand)
            dealer_line = f"**Krupier ({d_score}):** {self.format_hand(self.dealer_hand)}"
        else:
            dealer_line = f"**Krupier (??):** {self.format_hand(self.dealer_hand, hide_first=True)}"

        return (
            f"### 🃏 BLACKJACK\n\n"
            f"{status}\n\n"
            f"{dealer_line}\n"
            f"**Ty ({p_score}):** {self.format_hand(self.player_hand)}"
        )

    async def dealer_turn(self, interaction):
        while self.calculate_score(self.dealer_hand) < 17:
            self.dealer_hand.append(await self.draw_card())

        p_score = self.calculate_score(self.player_hand)
        d_score = self.calculate_score(self.dealer_hand)

        if d_score > 21:
            await self.end_game(interaction, "KRUPIER PRZEGRAŁ! 🤑 - Przekroczył 21.", discord.Color.green(), self.bet * 2, is_edit=True)
        elif d_score > p_score:
            await self.end_game(interaction, "PRZEGRAŁEŚ! 💀 - Krupier ma lepsze karty.", discord.Color.red(), 0, is_edit=True)
        elif d_score < p_score:
            await self.end_game(interaction, "WYGRAŁEŚ! 💰 - Masz lepsze karty.", discord.Color.green(), self.bet * 2, is_edit=True)
        else:
            await self.end_game(interaction, "REMIS! 🤝 - Odzyskujesz stawkę.", discord.Color.light_gray(), self.bet, is_edit=True)

    def build_result_summary(self, payout):
        return (
            f"**Stawka:** `{self.bet} monet`\n"
            f"**Wygrana:** `{payout} monet`"
        )

    async def end_game(self, interaction, title, color, payout, is_start=False, is_edit=False):
        if payout > 0 and not is_start:
            await interaction.client.db.update_balance(interaction.user.id, payout)

        if not is_start:
            await interaction.client.db.add_log(interaction.user.id, "BLACKJACK", self.bet, payout)

        user_data = await interaction.client.db.get_user(interaction.user.id)
        text = (
            f"{self.create_text(title, show_dealer=True)}\n\n"
            f"{self.build_result_summary(payout)}\n"
            f"**Saldo po grze:** `{user_data['balance']} monet`"
        )
        view = CardView(text, color)

        logger.info(
            "BLACKJACK | User: %s | Bet: %s | Win: %s | RandomNumbers: %s",
            interaction.user,
            self.bet,
            payout,
            self.format_api_numbers()
        )

        if is_start:
            if interaction.response.is_done():
                await interaction.edit_original_response(view=view)
            else:
                await interaction.response.send_message(view=view)
        else:
            await interaction.edit_original_response(view=view)
