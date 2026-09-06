import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import discord
from discord import app_commands


TOKEN = os.getenv("TOKEN")

if not TOKEN:
    raise RuntimeError("A variável TOKEN não foi encontrada no Render.")


# Servidor HTTP simples para o Render
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Iron Souls Hero Bot is online!")

    def log_message(self, format, *args):
        return


def run_web_server():
    port = int(os.getenv("PORT", "10000"))
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    server.serve_forever()


# Inicia a porta do Render
threading.Thread(target=run_web_server, daemon=True).start()


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
