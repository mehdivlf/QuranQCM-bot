import discord
from discord.ext import commands
from discord import app_commands
import json
import os

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

def load_questions():
    with open("data/qcm_al_kahf.json", "r", encoding="utf-8") as f:
        return json.load(f)

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"Connecté en tant que {bot.user}")

@bot.tree.command(name="qcm", description="Lancer un QCM de compréhension du Coran")
async def qcm(interaction: discord.Interaction):
    data = load_questions()
    question = data["questions"][0]

    embed = discord.Embed(
        title="Quran QCM",
        description=question["question"],
        color=0x4CAF50
    )

    for i, choice in enumerate(question["choices"]):
        embed.add_field(name=f"Choix {i+1}", value=choice, inline=False)

    await interaction.response.send_message(embed=embed)

TOKEN = os.getenv("DISCORD_TOKEN")

if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN manquant")

bot.run(TOKEN)

discord.py
