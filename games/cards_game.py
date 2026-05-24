import discord
import random
import logging
from views.card_view import CardView, make_container

logger = logging.getLogger("EconomyBot")
CURRENCY = "respektu"


class CardsView(discord.ui.LayoutView):
    def __init__(self, game_instance, user_id, entry_cost, db, status="Twoja kolej...", color=discord.Color.blue()):
        super().__init__(timeout=60.0)
        self.game = game_instance
        self.user_id = user_id
        self.entry_cost = entry_cost
        self.db = db
        self.render(status, color)

    def render(self, status, color, show_host=False):
        self.clear_items()

        draw_button = discord.ui.Button(label="Dobierz", style=discord.ButtonStyle.primary, emoji="🃏")
        draw_button.callback = self.draw

        stop_button = discord.ui.Button(label="Zostań", style=discord.ButtonStyle.secondary, emoji="🛑")
        stop_button.callback = self.stop

        self.add_item(make_container(self.game.create_text(status, show_host), color, draw_button, stop_button))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                view=CardView("### ❌ Komunikat\n\nTo nie Twoje rozdanie.", discord.Color.red()),
                ephemeral=True
            )
            return False
        return True

    async def draw(self, interaction: discord.Interaction):
        await interaction.response.defer()
        card = await self.game.draw_card()
        self.game.player_hand.append(card)
        score = self.game.calculate_score(self.game.player_hand)

        if score > 21:
            await self.game.end(
                interaction,
                "Przekroczono 21 punktów.",
                discord.Color.red(),
                0
            )
        else:
            self.render("Dobierasz czy zostajesz?", discord.Color.blue())
            await interaction.edit_original_response(view=self)

    async def stop(self, interaction: discord.Interaction):
        await interaction.response.defer()
        await self.game.host_turn(interaction)


class CardsGame:
    def __init__(self, settings=None, random_queue=None):
        self.settings = settings or {}
        self.random_queue = random_queue
        self.suits = ["♠️", "♥️", "♦️", "♣️"]
        self.ranks = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"]
        self.deck = self.generate_deck()
        self.player_hand = []
        self.host_hand = []
        self.entry_cost = 0
        self.api_numbers = []
        self.last_api_num = "N/A"

    def generate_deck(self):
        return [f"{rank}{suit}" for rank in self.ranks for suit in self.suits]

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
            "2": 2, "3": 3, "4": 4, "5": 5, "6": 6,
            "7": 7, "8": 8, "9": 9, "10": 10,
            "J": 10, "Q": 10, "K": 10, "A": 11
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
        return ", ".join(str(number) for number in self.api_numbers[-6:])

    async def start(self, interaction, entry_cost, db):
        self.entry_cost = entry_cost
        self.player_hand = [await self.draw_card(), await self.draw_card()]
        self.host_hand = [await self.draw_card(), await self.draw_card()]

        if self.calculate_score(self.player_hand) == 21:
            reward = int(entry_cost * 2.5)
            await db.update_balance(interaction.user.id, reward)
            await db.add_log(interaction.user.id, "CARDS", entry_cost, reward)
            await self.end(interaction, "Karty dały idealny wynik.", discord.Color.gold(), reward, is_start=True)
            return

        view = CardsView(self, interaction.user.id, entry_cost, db)
        if interaction.response.is_done():
            await interaction.edit_original_response(view=view)
        else:
            await interaction.response.send_message(view=view)

    def create_text(self, status, show_host=False):
        player_score = self.calculate_score(self.player_hand)

        if show_host:
            host_score = self.calculate_score(self.host_hand)
            host_line = f"**Bot ({host_score}):** {self.format_hand(self.host_hand)}"
        else:
            host_line = f"**Bot (??):** {self.format_hand(self.host_hand, hide_first=True)}"

        return (
            f"### 🃏 Karty\n\n"
            f"{status}\n\n"
            f"{host_line}\n"
            f"**Ty ({player_score}):** {self.format_hand(self.player_hand)}"
        )

    async def host_turn(self, interaction):
        while self.calculate_score(self.host_hand) < 17:
            self.host_hand.append(await self.draw_card())

        player_score = self.calculate_score(self.player_hand)
        host_score = self.calculate_score(self.host_hand)

        if host_score > 21:
            await self.end(interaction, "Bot przekroczył 21 punktów.", discord.Color.green(), self.entry_cost * 2, is_edit=True)
        elif host_score > player_score:
            await self.end(interaction, "Bot ma wyższy wynik.", discord.Color.red(), 0, is_edit=True)
        elif host_score < player_score:
            await self.end(interaction, "Masz wyższy wynik.", discord.Color.green(), self.entry_cost * 2, is_edit=True)
        else:
            await self.end(interaction, "Remis. Koszt rundy wraca na konto.", discord.Color.light_gray(), self.entry_cost, is_edit=True)

    def build_result_summary(self, reward):
        return (
            f"**Koszt rundy:** `{self.entry_cost} {CURRENCY}`\n"
            f"**Nagroda:** `{reward} {CURRENCY}`"
        )

    async def end(self, interaction, title, color, reward, is_start=False, is_edit=False):
        if reward > 0 and not is_start:
            await interaction.client.db.update_balance(interaction.user.id, reward)

        if not is_start:
            await interaction.client.db.add_log(interaction.user.id, "CARDS", self.entry_cost, reward)

        user_data = await interaction.client.db.get_user(interaction.user.id)
        text = (
            f"{self.create_text(title, show_host=True)}\n\n"
            f"{self.build_result_summary(reward)}\n"
            f"**Stan konta:** `{user_data['balance']} {CURRENCY}`"
        )
        view = CardView(text, color)

        logger.info(
            "KARTY | User: %s | Cost: %s | Reward: %s | RandomNumbers: %s",
            interaction.user,
            self.entry_cost,
            reward,
            self.format_api_numbers()
        )

        if is_start:
            if interaction.response.is_done():
                await interaction.edit_original_response(view=view)
            else:
                await interaction.response.send_message(view=view)
        else:
            await interaction.edit_original_response(view=view)
