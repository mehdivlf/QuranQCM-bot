import discord
from discord.ext import commands
from discord import app_commands
import json
import os
import random

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

def load_questions(surah):
    with open(f"data/{surah}.json", "r", encoding="utf-8") as f:
        return json.load(f)["questions"]

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"Connecté en tant que {bot.user}")

@bot.tree.command(name="qcm", description="Lancer un QCM de compréhension du Coran")
@app_commands.describe(sourate="Nom de la sourate (ex: al_kahf)")
async def qcm(interaction: discord.Interaction, sourate: str):
    try:
        questions = load_questions(sourate)
    except FileNotFoundError:
        await interaction.response.send_message(
            f"Sourate `{sourate}` introuvable.", ephemeral=True
        )
        return

    question = random.choice(questions)

    embed = discord.Embed(
        title="📖 Quran QCM",
        description=question["question"],
        color=0x2ECC71
    )

    for i, choice in enumerate(question["choices"]):
        embed.add_field(
            name=f"{chr(65+i)}",
            value=choice,
            inline=False
        )

    await interaction.response.send_message(embed=embed)

TOKEN = os.getenv("DISCORD_TOKEN")

if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN manquant")

bot.run(TOKEN)
