import os
import json
import random
import discord
from discord.ext import commands
from discord import app_commands

DATA_DIR = "data"

def load_surah_file(surah: int) -> str:
    # Pour commencer on ne gère que Al-Kahf (18)
    # Ensuite tu pourras ajouter d'autres fichiers selon le même format
    if surah == 18:
        return os.path.join(DATA_DIR, "qcm_al_kahf.json")
    return os.path.join(DATA_DIR, f"qcm_surah_{surah}.json")

def load_bank(surah: int):
    path = load_surah_file(surah)
    if not os.path.exists(path):
        return None, path
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f), path

def save_bank(path: str, bank: dict):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(bank, f, ensure_ascii=False, indent=2)

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

# --- Sessions quiz (par serveur + utilisateur) ---
SESSIONS = {}  # key=(guild_id, user_id) -> dict

class QCMView(discord.ui.View):
    def __init__(self, author_id: int, correct_index: int, on_pick):
        super().__init__(timeout=45)
        self.author_id = author_id
        self.correct_index = correct_index
        self.on_pick = on_pick
        self.answered = False

        for idx, label in enumerate(["A", "B", "C", "D"]):
            self.add_item(QCMButton(label=label, idx=idx))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("❌ Ce QCM n’est pas pour toi 🙂", ephemeral=True)
            return False
        return True

class QCMButton(discord.ui.Button):
    def __init__(self, label: str, idx: int):
        super().__init__(style=discord.ButtonStyle.primary, label=label)
        self.idx = idx

    async def callback(self, interaction: discord.Interaction):
        view: QCMView = self.view  # type: ignore
        if view.answered:
            await interaction.response.send_message("⚠️ Déjà répondu.", ephemeral=True)
            return

        view.answered = True

        # disable + color good/bad
        for i, item in enumerate(view.children):
            if isinstance(item, discord.ui.Button):
                item.disabled = True
                if i == view.correct_index:
                    item.style = discord.ButtonStyle.success
                elif i == self.idx:
                    item.style = discord.ButtonStyle.danger

        await interaction.response.edit_message(view=view)
        await view.on_pick(interaction, self.idx)

async def send_next_question(channel: discord.abc.Messageable, guild_id: int, user: discord.User):
    key = (guild_id, user.id)
    sess = SESSIONS.get(key)
    if not sess:
        return

    if sess["i"] >= len(sess["pool"]):
        score = sess["score"]
        total = len(sess["pool"])
        del SESSIONS[key]
        await channel.send(f"✅ Quiz terminé {user.mention} — Score: **{score}/{total}**")
        return

    q = sess["pool"][sess["i"]]

    # Shuffle choices but keep correct
    indices = list(range(4))
    random.shuffle(indices)
    choices = [q["choices"][i] for i in indices]
    correct_index = indices.index(q["answer"])

    embed = discord.Embed(
        title=f"🧠 Quran QCM — {sess['surah_name']}",
        description=f"{user.mention}\n**Question {sess['i']+1}/{len(sess['pool'])}**\n\n{q['question']}"
    )
    for letter, choice in zip(["A", "B", "C", "D"], choices):
        embed.add_field(name=letter, value=choice, inline=False)

    async def on_pick(interaction: discord.Interaction, picked_idx: int):
        ok = (picked_idx == correct_index)
        if ok:
            sess["score"] += 1
            await channel.send("✅ Correct ✅")
        else:
            good_letter = ["A", "B", "C", "D"][correct_index]
            exp = q.get("explanation", "📌 Révise l'histoire/les leçons de ce passage.")
            await channel.send(f"❌ Faux ❌ — Bonne réponse : **{good_letter}**\n📌 **Correction :** {exp}")

        sess["i"] += 1
        await send_next_question(channel, guild_id, user)

    view = QCMView(author_id=user.id, correct_index=correct_index, on_pick=on_pick)
    msg = await channel.send(embed=embed, view=view)

    await view.wait()
    if not view.answered:
        # timeout
        for item in view.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True
        await msg.edit(view=view)
        good_letter = ["A", "B", "C", "D"][correct_index]
        exp = q.get("explanation", "📌 Révise l'histoire/les leçons de ce passage.")
        await channel.send(f"⏰ Temps écoulé.\n✅ Bonne réponse : **{good_letter}**\n📌 **Correction :** {exp}")
        sess["i"] += 1
        await send_next_question(channel, guild_id, user)

@bot.event
async def on_ready():
    synced = await bot.tree.sync()
    print(f"✅ Connecté: {bot.user} | Slash sync: {len(synced)}")

# -------- COMMANDES SLASH --------

@bot.tree.command(name="themes", description="Liste les thèmes disponibles d’une sourate")
@app_commands.describe(sourate="Ex: 18 pour Al-Kahf")
async def themes(interaction: discord.Interaction, sourate: int):
    bank, path = load_bank(sourate)
    if not bank:
        await interaction.response.send_message(f"❌ Fichier introuvable: `{path}`", ephemeral=True)
        return
    topics = bank.get("topics", [])
    if not topics:
        await interaction.response.send_message("❌ Aucun thème trouvé dans ce fichier.", ephemeral=True)
        return
    txt = "\n".join([f"- `{t['id']}` : {t.get('label','')}" for t in topics])
    await interaction.response.send_message(f"📌 Thèmes pour **{bank.get('name','Sourate')}** :\n{txt}", ephemeral=True)

@bot.tree.command(name="quiz_story", description="Lancer un QCM par thème (histoire/leçons)")
@app_commands.describe(
    sourate="Ex: 18 pour Al-Kahf",
    theme="Ex: musa_khidr, ashab_al_kahf, two_gardens, dhul_qarnayn",
    nb="Nombre de questions (max 20)",
    difficulty="0 = mix, 1 = facile, 2 = moyen"
)
async def quiz_story(interaction: discord.Interaction, sourate: int, theme: str, nb: int = 8, difficulty: int = 0):
    nb = max(1, min(20, nb))
    key = (interaction.guild_id, interaction.user.id)
    if key in SESSIONS:
        await interaction.response.send_message("⚠️ Tu as déjà un quiz en cours. Fais `/stopquiz`.", ephemeral=True)
        return

    bank, path = load_bank(sourate)
    if not bank:
        await interaction.response.send_message(f"❌ Fichier introuvable: `{path}`", ephemeral=True)
        return

    topic = next((t for t in bank.get("topics", []) if t.get("id") == theme), None)
    if not topic:
        available = ", ".join([t.get("id", "?") for t in bank.get("topics", [])])
        await interaction.response.send_message(f"❌ Thème introuvable. Dispo: {available}", ephemeral=True)
        return

    pool_all = topic.get("questions", [])
    if difficulty in (1, 2):
        pool_all = [q for q in pool_all if q.get("difficulty", 1) == difficulty] or pool_all

    picks = random.sample(pool_all, k=min(nb, len(pool_all)))

    SESSIONS[key] = {
        "surah_name": bank.get("name", f"Sourate {sourate}"),
        "pool": picks,
        "i": 0,
        "score": 0
    }

    await interaction.response.send_message(
        f"✅ Quiz lancé : **{bank.get('name','Sourate')}** — thème **{topic.get('label', theme)}**\n"
        f"Questions: **{len(picks)}**",
        ephemeral=False
    )

    await send_next_question(interaction.channel, interaction.guild_id, interaction.user)

@bot.tree.command(name="stopquiz", description="Arrêter ton quiz en cours")
async def stopquiz(interaction: discord.Interaction):
    key = (interaction.guild_id, interaction.user.id)
    if key in SESSIONS:
        del SESSIONS[key]
        await interaction.response.send_message("🛑 Quiz arrêté.", ephemeral=True)
    else:
        await interaction.response.send_message("ℹ️ Aucun quiz en cours.", ephemeral=True)

# --- Admin: ajouter une question sans toucher au code ---
@bot.tree.command(name="add_question", description="[Admin] Ajouter une question dans un thème")
@app_commands.describe(
    sourate="Ex: 18",
    theme="Thème id (ex: musa_khidr)",
    question="La question",
    a="Choix A",
    b="Choix B",
    c="Choix C",
    d="Choix D",
    answer="Réponse (A/B/C/D)",
    explanation="Explication/correction",
    difficulty="1 facile / 2 moyen"
)
async def add_question(
    interaction: discord.Interaction,
    sourate: int, theme: str,
    question: str, a: str, b: str, c: str, d: str,
    answer: str, explanation: str = "", difficulty: int = 1
):
    if not interaction.user.guild_permissions.manage_guild:
        await interaction.response.send_message("❌ Permission requise : Gérer le serveur.", ephemeral=True)
        return

    bank, path = load_bank(sourate)
    if not bank:
        await interaction.response.send_message(f"❌ Fichier introuvable: `{path}`", ephemeral=True)
        return

    topic = next((t for t in bank.get("topics", []) if t.get("id") == theme), None)
    if not topic:
        await interaction.response.send_message("❌ Thème introuvable. Fais `/themes`.", ephemeral=True)
        return

    answer_map = {"A": 0, "B": 1, "C": 2, "D": 3}
    ans = answer_map.get(answer.strip().upper())
    if ans is None:
        await interaction.response.send_message("❌ answer doit être A, B, C ou D.", ephemeral=True)
        return

    new_q = {
        "id": f"{theme}_{random.randint(10000,99999)}",
        "difficulty": 2 if difficulty == 2 else 1,
        "question": question,
        "choices": [a, b, c, d],
        "answer": ans,
        "explanation": explanation or "📌 Relis le passage correspondant et retente."
    }
    topic.setdefault("questions", []).append(new_q)
    save_bank(path, bank)

    await interaction.response.send_message("✅ Question ajoutée !", ephemeral=True)

if __name__ == "__main__":
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise RuntimeError("DISCORD_TOKEN manquant (Railway Variables).")
    bot.run(token)
