import os
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer

import discord
from discord import app_commands


# ============================================================
# CONFIGURAÇÃO
# ============================================================

TOKEN = os.getenv("TOKEN")

if not TOKEN:
    raise RuntimeError("A variável TOKEN não foi encontrada no Render.")


# ============================================================
# SERVIDOR HTTP PARA O RENDER
# ============================================================

class HealthHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(
            "⚔️ Iron Souls Herói Bot está online!".encode("utf-8")
        )

    def log_message(self, format, *args):
        return


def run_web_server():
    port = int(os.getenv("PORT", "10000"))

    server = HTTPServer(
        ("0.0.0.0", port),
        HealthHandler
    )

    print(f"🌐 Servidor HTTP rodando na porta {port}")
    server.serve_forever()


threading.Thread(
    target=run_web_server,
    daemon=True
).start()


# ============================================================
# BANCO DE DADOS
# ============================================================

DB_FILE = "heroes.db"

db = sqlite3.connect(
    DB_FILE,
    check_same_thread=False
)

db.row_factory = sqlite3.Row

db.execute("""
CREATE TABLE IF NOT EXISTS stars (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    giver_id INTEGER NOT NULL,
    receiver_id INTEGER NOT NULL,
    reason TEXT NOT NULL,
    created_at TEXT NOT NULL
)
""")

db.commit()

db_lock = threading.Lock()


# ============================================================
# CONFIGURAÇÃO DOS NÍVEIS
# ============================================================

RANKS = [
    {
        "min": 50,
        "role": "👑 Iron Souls Hero — Lendário",
        "name": "Lendário",
        "emoji": "👑"
    },
    {
        "min": 30,
        "role": "🥇 Iron Souls Hero — Ouro",
        "name": "Ouro",
        "emoji": "🥇"
    },
    {
        "min": 15,
        "role": "🥈 Iron Souls Hero — Prata",
        "name": "Prata",
        "emoji": "🥈"
    },
    {
        "min": 5,
        "role": "🥉 Iron Souls Hero — Bronze",
        "name": "Bronze",
        "emoji": "🥉"
    },
    {
        "min": 1,
        "role": "⭐ Iron Souls Hero",
        "name": "Herói",
        "emoji": "⭐"
    }
]


def get_rank(stars):

    for rank in RANKS:
        if stars >= rank["min"]:
            return rank

    return {
        "min": 0,
        "role": None,
        "name": "Sem classificação",
        "emoji": "⚪"
    }


# ============================================================
# INTENTS
# ============================================================

intents = discord.Intents.default()
intents.members = True


# ============================================================
# BOT
# ============================================================

class IronSoulsBot(discord.Client):

    def __init__(self):
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        await self.tree.sync()
        print("✅ Comandos slash sincronizados.")

    async def on_ready(self):
        print(f"🤖 Bot conectado como {self.user}")
        print(f"🆔 ID do bot: {self.user.id}")
        print("⚔️ Iron Souls Herói Bot está pronto!")


bot = IronSoulsBot()


# ============================================================
# FUNÇÕES DO BANCO
# ============================================================

def get_star_count(user_id):

    with db_lock:
        result = db.execute(
            """
            SELECT COUNT(*) AS total
            FROM stars
            WHERE receiver_id = ?
            """,
            (user_id,)
        ).fetchone()

    return result["total"]


def get_given_today(user_id):

    now = datetime.now(timezone.utc)
    start = now.replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0
    ).isoformat()

    with db_lock:
        result = db.execute(
            """
            SELECT COUNT(*) AS total
            FROM stars
            WHERE giver_id = ?
            AND created_at >= ?
            """,
            (user_id, start)
        ).fetchone()

    return result["total"]


def already_gave_recently(giver_id, receiver_id):

    limit = (
        datetime.now(timezone.utc)
        - timedelta(hours=24)
    ).isoformat()

    with db_lock:
        result = db.execute(
            """
            SELECT id
            FROM stars
            WHERE giver_id = ?
            AND receiver_id = ?
            AND created_at >= ?
            LIMIT 1
            """,
            (
                giver_id,
                receiver_id,
                limit
            )
        ).fetchone()

    return result is not None


def add_star(giver_id, receiver_id, reason):

    created_at = datetime.now(timezone.utc).isoformat()

    with db_lock:
        db.execute(
            """
            INSERT INTO stars
            (giver_id, receiver_id, reason, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (
                giver_id,
                receiver_id,
                reason,
                created_at
            )
        )

        db.commit()


def remove_star(star_id):

    with db_lock:

        result = db.execute(
            """
            SELECT *
            FROM stars
            WHERE id = ?
            """,
            (star_id,)
        ).fetchone()

        if result is None:
            return None

        db.execute(
            """
            DELETE FROM stars
            WHERE id = ?
            """,
            (star_id,)
        )

        db.commit()

    return result


def get_recent_stars(user_id, limit=10):

    with db_lock:

        results = db.execute(
            """
            SELECT *
            FROM stars
            WHERE receiver_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (
                user_id,
                limit
            )
        ).fetchall()

    return results


def get_ranking(limit=10):

    with db_lock:

        results = db.execute(
            """
            SELECT
                receiver_id,
                COUNT(*) AS total
            FROM stars
            GROUP BY receiver_id
            ORDER BY total DESC
            LIMIT ?
            """,
            (limit,)
        ).fetchall()

    return results


# ============================================================
# ATUALIZAÇÃO DO CARGO
# ============================================================

async def update_hero_role(member):

    if member.bot:
        return

    stars = get_star_count(member.id)
    rank = get_rank(stars)

    guild = member.guild

    hero_roles = []

    for rank_data in RANKS:

        role = discord.utils.get(
            guild.roles,
            name=rank_data["role"]
        )

        if role:
            hero_roles.append(role)

    # Remove cargos antigos
    roles_to_remove = [
        role
        for role in member.roles
        if role in hero_roles
    ]

    if roles_to_remove:

        try:
            await member.remove_roles(
                *roles_to_remove,
                reason="Atualização do nível de Herói"
            )
        except discord.Forbidden:
            print(
                f"❌ Não consegui remover cargo de {member}"
            )

    # Adiciona novo cargo
    if rank["role"]:

        role = discord.utils.get(
            guild.roles,
            name=rank["role"]
        )

        if role:

            try:
                await member.add_roles(
                    role,
                    reason="Atualização automática do nível de Herói"
                )

            except discord.Forbidden:
                print(
                    f"❌ Não consegui adicionar cargo {role.name}"
                )


# ============================================================
# /TESTE
# ============================================================

@bot.tree.command(
    name="teste",
    description="Testa se o Iron Souls Herói Bot está funcionando."
)
async def teste(interaction: discord.Interaction):

    await interaction.response.send_message(
        "⚔️ **Iron Souls Herói Bot está online!** ⭐"
    )


# ============================================================
# /ESTRELA
# ============================================================

@bot.tree.command(
    name="estrela",
    description="Dê uma estrela para alguém que ajudou a comunidade."
)
@app_commands.describe(
    membro="Pessoa que você quer reconhecer",
    motivo="Explique por que essa pessoa merece a estrela"
)
async def estrela(
    interaction: discord.Interaction,
    membro: discord.Member,
    motivo: str
):

    giver = interaction.user

    # ----------------------------------------
    # Não permitir bots
    # ----------------------------------------

    if membro.bot:

        await interaction.response.send_message(
            "🤖 Você não pode dar estrelas para bots.",
            ephemeral=True
        )

        return

    # ----------------------------------------
    # Não permitir autoestrela
    # ----------------------------------------

    if membro.id == giver.id:

        await interaction.response.send_message(
            "❌ Você não pode dar uma estrela para si mesmo!",
            ephemeral=True
        )

        return

    # ----------------------------------------
    # Limite do motivo
    # ----------------------------------------

    motivo = motivo.strip()

    if len(motivo) < 5:

        await interaction.response.send_message(
            "❌ O motivo precisa ter pelo menos **5 caracteres**.",
            ephemeral=True
        )

        return

    if len(motivo) > 300:

        await interaction.response.send_message(
            "❌ O motivo pode ter no máximo **300 caracteres**.",
            ephemeral=True
        )

        return

    # ----------------------------------------
    # Limite diário
    # ----------------------------------------

    given_today = get_given_today(giver.id)

    if given_today >= 3:

        await interaction.response.send_message(
            "🛑 Você já deu **3 estrelas hoje**.\n"
            "Volte amanhã para reconhecer mais heróis!",
            ephemeral=True
        )

        return

    # ----------------------------------------
    # Evitar spam na mesma pessoa
    # ----------------------------------------

    if already_gave_recently(
        giver.id,
        membro.id
    ):

        await interaction.response.send_message(
            "⏳ Você já deu uma estrela para essa pessoa "
            "nas últimas **24 horas**.",
            ephemeral=True
        )

        return

    # ----------------------------------------
    # Quantidade antes
    # ----------------------------------------

    old_stars = get_star_count(membro.id)

    old_rank = get_rank(old_stars)

    # ----------------------------------------
    # Registrar
    # ----------------------------------------

    add_star(
        giver.id,
        membro.id,
        motivo
    )

    new_stars = get_star_count(membro.id)

    new_rank = get_rank(new_stars)

    # ----------------------------------------
    # Atualizar cargo
    # ----------------------------------------

    await update_hero_role(membro)

    # ----------------------------------------
    # Mensagem
    # ----------------------------------------

    embed = discord.Embed(
        title="⭐ Herói reconhecido!",
        description=(
            f"{membro.mention} recebeu uma estrela de "
            f"{giver.mention}!"
        ),
        color=discord.Color.gold()
    )

    embed.add_field(
        name="💬 Motivo",
        value=motivo,
        inline=False
    )

    embed.add_field(
        name="⭐ Total de estrelas",
        value=f"**{new_stars}**",
        inline=True
    )

    embed.add_field(
        name="🏅 Nível",
        value=(
            f"{new_rank['emoji']} "
            f"**{new_rank['name']}**"
        ),
        inline=True
    )

    # ----------------------------------------
    # Level up
    # ----------------------------------------

    if (
        new_rank["name"] != old_rank["name"]
        and new_rank["role"] is not None
    ):

        embed.add_field(
            name="🎉 PROMOÇÃO!",
            value=(
                f"{membro.mention} alcançou o nível "
                f"**{new_rank['name']}**!"
            ),
            inline=False
        )

    await interaction.response.send_message(
        embed=embed
    )


# ============================================================
# /PERFIL
# ============================================================

@bot.tree.command(
    name="perfil",
    description="Veja o perfil de Herói de um membro."
)
@app_commands.describe(
    membro="Membro que você quer consultar"
)
async def perfil(
    interaction: discord.Interaction,
    membro: discord.Member
):

    stars = get_star_count(membro.id)
    rank = get_rank(stars)

    embed = discord.Embed(
        title="⚔️ Perfil de Herói",
        description=membro.mention,
        color=discord.Color.gold()
    )

    embed.set_thumbnail(
        url=membro.display_avatar.url
    )

    embed.add_field(
        name="⭐ Estrelas",
        value=f"**{stars}**",
        inline=True
    )

    embed.add_field(
        name="🏅 Nível",
        value=(
            f"{rank['emoji']} **{rank['name']}**"
        ),
        inline=True
    )

    if rank["min"] == 0:

        next_rank = RANKS[-1]

    else:

        current_index = None

        for i, rank_data in enumerate(RANKS):

            if rank_data["name"] == rank["name"]:
                current_index = i
                break

        if current_index is not None and current_index > 0:

            next_rank = RANKS[current_index - 1]

        else:

            next_rank = None

    if next_rank:

        remaining = max(
            0,
            next_rank["min"] - stars
        )

        embed.add_field(
            name="🎯 Próximo nível",
            value=(
                f"{next_rank['emoji']} "
                f"**{next_rank['name']}**\n"
                f"Faltam **{remaining} estrelas**."
            ),
            inline=False
        )

    else:

        embed.add_field(
            name="👑 Status",
            value="Você chegou ao nível máximo!",
            inline=False
        )

    await interaction.response.send_message(
        embed=embed
    )


# ============================================================
# /HEROIS
# ============================================================

@bot.tree.command(
    name="herois",
    description="Mostra o ranking dos maiores Heróis da comunidade."
)
async def herois(
    interaction: discord.Interaction
):

    ranking = get_ranking(10)

    if not ranking:

        await interaction.response.send_message(
            "⭐ Ainda não existem Heróis registrados!"
        )

        return

    embed = discord.Embed(
        title="🏆 Hall dos Heróis",
        description="Os maiores ajudantes da comunidade Iron Souls BR",
        color=discord.Color.gold()
    )

    medals = [
        "🥇",
        "🥈",
        "🥉"
    ]

    lines = []

    for index, row in enumerate(ranking):

        member = interaction.guild.get_member(
            row["receiver_id"]
        )

        if member:

            if index < 3:
                prefix = medals[index]
            else:
                prefix = f"**{index + 1}.**"

            rank = get_rank(row["total"])

            lines.append(
                f"{prefix} {member.mention} — "
                f"**{row['total']} ⭐** "
                f"{rank['emoji']}"
            )

    if not lines:

        lines.append(
            "Nenhum Herói encontrado."
        )

    embed.add_field(
        name="⚔️ Ranking",
        value="\n".join(lines),
        inline=False
    )

    await interaction.response.send_message(
        embed=embed
    )


# ============================================================
# /AJUDAS
# ============================================================

@bot.tree.command(
    name="ajudas",
    description="Veja o histórico de estrelas recebidas por um membro."
)
@app_commands.describe(
    membro="Membro que você quer consultar"
)
async def ajudas(
    interaction: discord.Interaction,
    membro: discord.Member
):

    history = get_recent_stars(
        membro.id,
        10
    )

    if not history:

        await interaction.response.send_message(
            f"📜 {membro.mention} ainda não recebeu estrelas."
        )

        return

    embed = discord.Embed(
        title="📜 Histórico de Ajudas",
        description=(
            f"Últimos reconhecimentos de {membro.mention}"
        ),
        color=discord.Color.blue()
    )

    lines = []

    for row in history:

        giver = interaction.guild.get_member(
            row["giver_id"]
        )

        giver_name = (
            giver.mention
            if giver
            else "Membro desconhecido"
        )

        try:

            date = datetime.fromisoformat(
                row["created_at"]
            )

            date_text = date.strftime(
                "%d/%m/%Y %H:%M"
            )

        except Exception:

            date_text = "Data desconhecida"

        lines.append(
            f"⭐ {giver_name}\n"
            f"💬 {row['reason']}\n"
            f"🕐 {date_text}\n"
            f"🆔 Registro #{row['id']}"
        )

    embed.add_field(
        name="Reconhecimentos",
        value="\n\n".join(lines),
        inline=False
    )

    await interaction.response.send_message(
        embed=embed
    )


# ============================================================
# /REMOVERESTRELA
# ============================================================

@bot.tree.command(
    name="removerestrela",
    description="Remove uma estrela registrada incorretamente."
)
@app_commands.describe(
    registro="Número do registro da estrela que será removida",
    motivo="Motivo da remoção"
)
@app_commands.checks.has_permissions(
    manage_guild=True
)
async def removerestrela(
    interaction: discord.Interaction,
    registro: int,
    motivo: str
):

    removed = remove_star(registro)

    if removed is None:

        await interaction.response.send_message(
            "❌ Não encontrei esse registro.",
            ephemeral=True
        )

        return

    member = interaction.guild.get_member(
        removed["receiver_id"]
    )

    if member:

        await update_hero_role(member)

    await interaction.response.send_message(
        "🛡️ **Estrela removida com sucesso.**\n\n"
        f"🆔 Registro: `#{registro}`\n"
        f"👤 Destinatário: <@{removed['receiver_id']}>\n"
        f"👤 Autor: <@{removed['giver_id']}>\n"
        f"💬 Motivo da remoção: {motivo}"
    )


# ============================================================
# ERROS DE PERMISSÃO
# ============================================================

@removerestrela.error
async def removerestrela_error(
    interaction: discord.Interaction,
    error
):

    if isinstance(
        error,
        app_commands.errors.MissingPermissions
    ):

        await interaction.response.send_message(
            "🛡️ Você precisa ter a permissão "
            "**Gerenciar Servidor** para remover estrelas.",
            ephemeral=True
        )

    else:

        print(
            f"❌ Erro no comando removerestrela: {error}"
        )

        if not interaction.response.is_done():

            await interaction.response.send_message(
                "❌ Ocorreu um erro ao executar o comando.",
                ephemeral=True
            )


# ============================================================
# INICIAR BOT
# ============================================================

bot.run(TOKEN)
