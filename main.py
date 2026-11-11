
import discord
from discord.ext import commands
import os
import json
import asyncio

# =====================================
# إعدادات منتدى نجد
# =====================================

TOKEN = os.getenv("TOKEN")

# تسجيل الأسماء
NAME_CHANNEL_ID = 1569992736759877732
PLAY_ROLE_ID = 1569980718262784101

# الرتب
CITIZEN_ROLE_ID = 1562060450017972305
MILITARY_ROLE_ID = 1567933281301700628
ADMIN_ROLE_ID = 1567943636413321419

# روم القوانين
RULES_CHANNEL_ID = 1569788828296679565

# الرومات المسموحة للمواطن
ALLOWED_CHANNELS = [
    1569992736759877732,
    1561852188186124519,
    1561852197812043886,
    1561852196641833050
]

# أعداد التصويت
CITIZEN_LIMIT = 7
MILITARY_LIMIT = 2

# ملف حفظ الأصوات
VOTES_FILE = "votes.json"

vote_lock = asyncio.Lock()

# =====================================
# إعداد البوت
# =====================================

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(
    command_prefix=("-", "."),
    intents=intents
)

# =====================================
# حفظ واسترجاع التصويت
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
            print("Could not load votes file")

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
            "يرجى اختيار القسم المناسب حسب رتبتك."
        ),
        color=discord.Color.from_rgb(105, 65, 125)
    )

    embed.add_field(
        name="👤 تصويت المواطنين",
        value=(
            f"العدد المطلوب: **{CITIZEN_LIMIT}**\n"
            f"الرتبة المطلوبة: <@&{CITIZEN_ROLE_ID}>\n"
            f"عدد المصوتين: **{citizens} / {CITIZEN_LIMIT}**"
        ),
        inline=False
    )

    embed.add_field(
        name="🚔 تصويت العساكر",
        value=(
            f"العدد المطلوب: **{MILITARY_LIMIT}**\n"
            f"الرتبة المطلوبة: <@&{MILITARY_ROLE_ID}>\n"
            f"عدد المصوتين: **{military} / {MILITARY_LIMIT}**"
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
            "• يمكنك تغيير تصويتك أو إلغاؤه.\n"
            "• لا يمكن تجاوز العدد المطلوب لكل قسم."
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

        # التحقق من الرتبة المطلوبة
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

        async with vote_lock:

            previous_vote = votes_data["voters"].get(user_id)

            # منع تكرار نفس التصويت
            if previous_vote == vote_type:
                await interaction.response.send_message(
                    "أنت مصوت في هذا القسم بالفعل.",
                    ephemeral=True
                )
                return

            citizens, military = get_counts()

            # احتساب المقعد بعد إزالة التصويت القديم
            if previous_vote == "citizen":
                citizens -= 1

            elif previous_vote == "military":
                military -= 1

            # التحقق من المقاعد المتاحة
            if vote_type == "citizen" and citizens >= CITIZEN_LIMIT:
                await interaction.response.send_message(
                    "❌ اكتمل العدد المطلوب من المواطنين.",
                    ephemeral=True
                )
                return

            if vote_type == "military" and military >= MILITARY_LIMIT:
                await interaction.response.send_message(
                    "❌ اكتمل العدد المطلوب من العساكر.",
                    ephemeral=True
                )
                return

            # حفظ التصويت الجديد
            votes_data["voters"][user_id] = vote_type
            save_votes()

            await interaction.response.edit_message(
                embed=create_embed(),
                view=self
            )

            print(f"{member} voted as {vote_name}")

    # زر المواطنين
    @discord.ui.button(
        label="المواطنين",
        emoji="✅",
        style=discord.ButtonStyle.success,
        custom_id="nj_citizen_vote",
        row=0
    )
    async def citizen_button(self, interaction, button):

        await self.process_vote(
            interaction,
            "citizen"
        )

    # زر العساكر
    @discord.ui.button(
        label="العساكر",
        emoji="🚔",
        style=discord.ButtonStyle.primary,
        custom_id="nj_military_vote",
        row=0
    )
    async def military_button(self, interaction, button):

        await self.process_vote(
            interaction,
            "military"
        )

    # زر إلغاء التصويت
    @discord.ui.button(
        label="إلغاء تصويتي",
        emoji="❌",
        style=discord.ButtonStyle.danger,
        custom_id="nj_cancel_vote",
        row=1
    )
    async def cancel_button(self, interaction, button):

        user_id = str(interaction.user.id)

        async with vote_lock:

            if interaction.message.id != votes_data.get("message_id"):
                await interaction.response.send_message(
                    "هذا التصويت غير فعال.",
                    ephemeral=True
                )
                return

            if user_id not in votes_data["voters"]:
                await interaction.response.send_message(
                    "ليس لديك تصويت لإلغائه.",
                    ephemeral=True
                )
                return

            # حذف تصويت العضو
            del votes_data["voters"][user_id]
            save_votes()

            await interaction.response.edit_message(
                embed=create_embed(),
                view=self
            )

            print(f"Vote cancelled: {interaction.user}")


# =====================================
# تشغيل البوت واستعادة الأزرار
# =====================================

@bot.event
async def on_ready():

    if not getattr(bot, "view_registered", False):

        message_id = votes_data.get("message_id")

        if message_id:
            bot.add_view(
                RoleVoteView(),
                message_id=int(message_id)
            )
        else:
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

    async with vote_lock:

        # تصفير التصويت القديم
        votes_data["voters"] = {}
        votes_data["message_id"] = None
        save_votes()

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
# أمر .اخفاء
# =====================================

@bot.command(name="اخفاء")
@commands.has_permissions(administrator=True)
async def hide_citizen_channels(ctx):

    guild = ctx.guild

    if guild is None:
        return

    citizen_role = guild.get_role(CITIZEN_ROLE_ID)

    if citizen_role is None:
        await ctx.reply(
            "❌ لم أجد رتبة المواطن."
        )
        return

    await ctx.reply(
        "⏳ جاري ضبط صلاحيات مشاهدة الرومات لرتبة المواطن..."
    )

    success = 0
    failed = 0

    for channel in guild.channels:

        try:

            overwrite = channel.overwrites_for(citizen_role)

            if channel.id in ALLOWED_CHANNELS:
                overwrite.view_channel = True
            else:
                overwrite.view_channel = False

            await channel.set_permissions(
                citizen_role,
                overwrite=overwrite,
                reason="NJ Citizen Channel Visibility"
            )

            success += 1

        except discord.Forbidden:
            failed += 1

        except discord.HTTPException:
            failed += 1

    found_channels = [
        channel.id
        for channel in guild.channels
        if channel.id in ALLOWED_CHANNELS
    ]

    missing_channels = [
        channel_id
        for channel_id in ALLOWED_CHANNELS
        if channel_id not in found_channels
    ]

    result = (
        "✅ **تم تنفيذ أمر الإخفاء.**\n\n"
        f"👤 الرتبة المستهدفة: {citizen_role.mention}\n"
        f"🔓 الرومات المسموحة: **{len(found_channels)} / 4**\n"
        f"🔒 الرومات التي تمت معالجتها: **{success}**\n"
        f"❌ الرومات التي فشل تعديلها: **{failed}**"
    )

    if missing_channels:
        result += (
            "\n\n⚠️ الرومات غير الموجودة:\n"
            + "\n".join(
                f"`{channel_id}`"
                for channel_id in missing_channels
            )
        )

    await ctx.send(result)

    print("NJ Citizen Hide System Completed")


@hide_citizen_channels.error
async def hide_error(ctx, error):

    if isinstance(error, commands.MissingPermissions):
        await ctx.reply(
            "❌ هذا الأمر مخصص للإداريين فقط."
        )


# =====================================
# تسجيل الأسماء وإعطاء تصريح لعب
# =====================================

@bot.event
async def on_message(message):

    if message.author.bot:
        return

    if message.guild is None:
        return

    # معالجة الأوامر
    if message.content.startswith(("-", ".")):
        await bot.process_commands(message)
        return

    # روم تسجيل الاسم
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

        play_role = message.guild.get_role(PLAY_ROLE_ID)

        if play_role is None:
            await message.reply(
                "❌ لم يتم العثور على رتبة تصريح لعب."
            )
            return

        try:

            # تغيير لقب العضو
            await member.edit(
                nick=f"NJ | {name}",
                reason="NJ Name Registration"
            )

            # إعطاء رتبة تصريح لعب فقط
            if play_role not in member.roles:
                await member.add_roles(
                    play_role,
                    reason="NJ Name Registration"
                )

            # حذف رسالة التسجيل
            await message.delete()

            print(
                f"Registered: {member} -> NJ | {name}"
            )

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
