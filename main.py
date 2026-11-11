
import discord
from discord.ext import commands
import os
import json
import asyncio

# =====================================
# إعدادات البوت - منتدى نجد
# =====================================

TOKEN = os.getenv("TOKEN")

NAME_CHANNEL_ID = 1569992736759877732
NAME_ROLE_ID = 1569980718262784101

CITIZEN_ROLE_ID = 1569980718262784101
MILITARY_ROLE_ID = 1567933281301700628
ADMIN_ROLE_ID = 1567943636413321419

RULES_CHANNEL_ID = 1569788828296679565

CITIZEN_LIMIT = 7
MILITARY_LIMIT = 4

VOTES_FILE = "votes.json"

vote_lock = asyncio.Lock()

# =====================================
# إعداد الصلاحيات
# =====================================

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(
    command_prefix="-",
    intents=intents
)

# =====================================
# نظام حفظ الأصوات
# =====================================

def load_votes():

    default_data = {
        "voters": {},
        "message_id": None
    }

    if os.path.exists(VOTES_FILE):
        try:
            with open(VOTES_FILE, "r", encoding="utf-8") as file:
                data = json.load(file)

                if isinstance(data, dict):
                    data.setdefault("voters", {})
                    data.setdefault("message_id", None)
                    return data

        except (json.JSONDecodeError, OSError):
            print("Could not load votes file.")

    return default_data


votes_data = load_votes()


def save_votes():

    with open(VOTES_FILE, "w", encoding="utf-8") as file:
        json.dump(
            votes_data,
            file,
            ensure_ascii=False,
            indent=4
        )


def get_counts():

    voters = votes_data["voters"]

    citizens = sum(
        1 for vote in voters.values()
        if vote == "citizen"
    )

    military = sum(
        1 for vote in voters.values()
        if vote == "military"
    )

    return citizens, military


# =====================================
# تصميم رسالة التصويت
# =====================================

def create_embed():

    citizens, military = get_counts()

    embed = discord.Embed(
        title="🎮 رول بلاي | منتدى نجد",
        description=(
            "مرحباً بكم في نظام التصويت الرسمي لمنتدى نجد.\n"
            "يرجى اختيار التصويت المناسب حسب رتبتك."
        ),
        color=discord.Color.from_rgb(105, 65, 125)
    )

    embed.add_field(
        name="👤 تصويت المواطنين",
        value=(
            f"العدد المطلوب: **{CITIZEN_LIMIT}**\n"
            f"الرتبة المطلوبة: <@&{CITIZEN_ROLE_ID}>\n"
            f"عدد المصوتين: **{citizens} / {CITIZEN_LIMIT}**\n"
            "━━━━━━━━━━━━━━━━━━━━"
        ),
        inline=False
    )

    embed.add_field(
        name="🚔 تصويت العساكر",
        value=(
            f"العدد المطلوب: **{MILITARY_LIMIT}**\n"
            f"الرتبة المطلوبة: <@&{MILITARY_ROLE_ID}>\n"
            f"عدد المصوتين: **{military} / {MILITARY_LIMIT}**\n"
            "━━━━━━━━━━━━━━━━━━━━"
        ),
        inline=False
    )

    embed.add_field(
        name="📜 قوانين الرول بلاي",
        value=(
            "يرجى قراءة قوانين الرول بلاي قبل التصويت.\n"
            f"📌 <#{RULES_CHANNEL_ID}>"
        ),
        inline=False
    )

    embed.add_field(
        name="📌 تعليمات التصويت",
        value=(
            "• يجب امتلاك الرتبة المطلوبة للتصويت.\n"
            "• يسمح لكل عضو بتصويت واحد فقط.\n"
            "• لا يمكنك التصويت كمواطن وعسكري معاً.\n"
            "• لا يمكن تغيير التصويت بعد اعتماده."
        ),
        inline=False
    )

    embed.set_footer(
        text="منتدى نجد | نظام التصويت الرسمي"
    )

    return embed


# =====================================
# أزرار التصويت
# =====================================

class RoleVoteView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    async def process_vote(self, interaction, vote_type):

        if interaction.guild is None:
            await interaction.response.send_message(
                "هذا التصويت متاح داخل السيرفر فقط.",
                ephemeral=True
            )
            return

        if interaction.message.id != votes_data.get("message_id"):
            await interaction.response.send_message(
                "هذا التصويت غير فعال.",
                ephemeral=True
            )
            return

        member = interaction.user

        if not isinstance(member, discord.Member):
            return

        if vote_type == "citizen":
            required_role = CITIZEN_ROLE_ID
            vote_name = "مواطن"
        else:
            required_role = MILITARY_ROLE_ID
            vote_name = "عسكري"

        # التحقق من الرتبة
        if not any(
            role.id == required_role
            for role in member.roles
        ):
            await interaction.response.send_message(
                "❌ لا تمتلك الرتبة المطلوبة للتصويت.",
                ephemeral=True
            )
            return

        user_id = str(member.id)

        # منع التصويت المكرر ومنع التصويت بالقسمين
        async with vote_lock:

            if user_id in votes_data["voters"]:

                previous_vote = votes_data["voters"][user_id]

                if previous_vote == vote_type:
                    message = "لقد قمت بالتصويت مسبقاً."
                else:
                    message = "❌ لا يمكنك التصويت كمواطن وعسكري معاً."

                await interaction.response.send_message(
                    message,
                    ephemeral=True
                )
                return

            citizens, military = get_counts()

            # التحقق من العدد المطلوب
            if vote_type == "citizen" and citizens >= CITIZEN_LIMIT:
                await interaction.response.send_message(
                    "اكتمل العدد المطلوب من المواطنين.",
                    ephemeral=True
                )
                return

            if vote_type == "military" and military >= MILITARY_LIMIT:
                await interaction.response.send_message(
                    "اكتمل العدد المطلوب من العساكر.",
                    ephemeral=True
                )
                return

            # حفظ التصويت
            votes_data["voters"][user_id] = vote_type
            save_votes()

            await interaction.response.edit_message(
                embed=create_embed(),
                view=self
            )

            print(f"{member} voted as {vote_name}")

    @discord.ui.button(
        label="المواطنين",
        emoji="✅",
        style=discord.ButtonStyle.success,
        custom_id="nj_citizen_vote"
    )
    async def citizen_button(self, interaction, button):

        await self.process_vote(
            interaction,
            "citizen"
        )

    @discord.ui.button(
        label="العساكر",
        emoji="🚔",
        style=discord.ButtonStyle.primary,
        custom_id="nj_military_vote"
    )
    async def military_button(self, interaction, button):

        await self.process_vote(
            interaction,
            "military"
        )


# =====================================
# تشغيل البوت واستعادة الأزرار
# =====================================

@bot.event
async def on_ready():

    if not getattr(bot, "view_registered", False):

        bot.add_view(RoleVoteView())
        bot.view_registered = True

    print(f"Bot Online: {bot.user}")
    print("NJ Systems Started")


# =====================================
# أمر -رول
# =====================================

@bot.command(name="رول")
async def create_role_poll(ctx):

    member = ctx.author

    if not isinstance(member, discord.Member):
        return

    # صلاحية Administrator أو الرتبة المحددة
    is_admin = member.guild_permissions.administrator

    has_admin_role = any(
        role.id == ADMIN_ROLE_ID
        for role in member.roles
    )

    if not (is_admin or has_admin_role):
        await ctx.reply(
            "❌ ليس لديك صلاحية استخدام هذا الأمر."
        )
        return

    # التأكد من عدم وجود تصويت نشط سابق
    votes_data["voters"] = {}
    votes_data["message_id"] = None
    save_votes()

    # إنشاء التصويت
    message = await ctx.send(
        content=(
            f"<@&{CITIZEN_ROLE_ID}> "
            f"<@&{MILITARY_ROLE_ID}>"
        ),
        embed=create_embed(),
        view=RoleVoteView(),
        allowed_mentions=discord.AllowedMentions(
            roles=True
        )
    )

    votes_data["message_id"] = message.id
    save_votes()

    print("NJ Poll Created Successfully")


# =====================================
# نظام تسجيل الأسماء
# =====================================

@bot.event
async def on_message(message):

    if message.author.bot:
        return

    if message.guild is None:
        return

    # معالجة الأوامر قبل نظام التسجيل
    if message.content.startswith("-"):
        await bot.process_commands(message)
        return

    # روم تسجيل الأسماء
    if message.channel.id == NAME_CHANNEL_ID:

        name = message.content.strip()

        if not name:
            return

        if len(name) > 25:
            await message.reply(
                "❌ الاسم طويل جداً، الحد الأقصى 25 حرف."
            )
            return

        member = message.author
        role = message.guild.get_role(NAME_ROLE_ID)

        if role is None:
            await message.reply(
                "❌ رتبة التسجيل غير موجودة."
            )
            return

        try:

            # إعطاء الرتبة
            await member.add_roles(
                role,
                reason="NJ Name Registration"
            )

            # تغيير اللقب
            await member.edit(
                nick=f"NJ | {name}",
                reason="NJ Name Registration"
            )

            # حذف رسالة التسجيل
            await message.delete()

            print(f"Registered: {member} -> NJ | {name}")

        except discord.Forbidden:
            print("Missing permissions for registration")

        except discord.HTTPException as error:
            print(f"Registration Error: {error}")

    await bot.process_commands(message)


# =====================================
# تشغيل البوت
# =====================================

if not TOKEN:
    raise ValueError(
        "TOKEN environment variable is missing!"
    )

bot.run(TOKEN)
