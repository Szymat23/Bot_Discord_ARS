import discord


def make_container(text: str, color: discord.Color, *children: discord.ui.Item):
    items = [discord.ui.TextDisplay(text)]

    if children:
        items.append(discord.ui.Separator())
        items.append(discord.ui.ActionRow(*children))

    return discord.ui.Container(
        *items,
        accent_color=color
    )


class CardView(discord.ui.LayoutView):
    def __init__(self, text: str, color: discord.Color = discord.Color.blurple(), timeout=None, buttons=None):
        super().__init__(timeout=timeout)

        if buttons is None:
            buttons = []

        self.add_item(make_container(text, color, *buttons))
