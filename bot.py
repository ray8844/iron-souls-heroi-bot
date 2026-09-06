import os
import discord
from discord import app_commands

TOKEN = os.getenv("TOKEN")

if not TOKEN:
    raise RuntimeError("A variável TOKEN não foi encontrada no Render.")

intents = discord.Intents.default()
intents.members = True

class IronSoulsBot(discord.Client):
    def __init__(self):
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        await self.tree.sync()

    async def on_ready(self):
        print(f"🤖 Bot conectado como {self.user}")

bot = IronSoulsBot()

@bot.tree.command(
    name="teste",
    description="Testa se o Iron Souls Herói Bot está funcionando."
)
async def teste(interaction: discord.Interaction):
    await interaction.response.send_message(
        "⚔️ **Iron Souls Herói Bot está online!** ⭐"
    )

bot.run(TOKEN)
