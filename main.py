
import os
import json
import time
import asyncio
import discord

from discord.ext import commands

# =========================================================
# الإعدادات العامة
# =========================================================

TOKEN = os.getenv("TOKEN")

NAME_CHANNEL_ID = 1569992736759877732
PLAY_ROLE_ID = 1569980718262784101

CITIZEN_ROLE_ID = 1562060450017972305
MILITARY_ROLE_ID = 1567933281301700628
ADMIN_ROLE_ID = 1567943636413321419

RULES_CHANNEL_ID = 1569788828296679565

VOICE_CHANNEL_ID = 1570498914140819546

ALLOWED_CHANNELS = [
    1569992736759877732,
    1561852188186124519,
    1561852197812043886,
    1561852196641833050
]

# =========================================================
# إعدادات التصويت
# =========================================================

CITIZEN_LIMIT = 7
MILITARY_LIMIT = 2

VOTES_FILE = "votes.json"

# =========================================================
# إعدادات الحماية ANTI-NUKE
# =========================================================

PROTECTION_FILE = "protection_data.json"

ALERT_USER_IDS = [
    391638472022163456,
    1058818503106375755
]

BAN_HOURLY_LIMIT = 5
BAN_DAILY_LIMIT = 5

HOUR_SECONDS = 60 * 60
DAY_SECONDS = 24 * 60 * 60

# =========================================================
# الأقفال
# =========================================================

vote_lock = asyncio.Lock()
protection_lock = asyncio.Lock()
audit_lock = asyncio.Lock()

# =========================================================
# أدوات JSON
# =========================================================

def read_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as file:
            data = json.load(file)

            if isinstance(data, dict):
                return data

            return default.copy()

    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return default.copy()


def write_json(path, data):
    temp_path = path + ".tmp"

    with open(temp_path, "w", encoding="utf-8") as file:
        json.dump(
            data,
            file,
            ensure_ascii=False,
            indent=4
        )

    os.replace(temp_path, path)


# =========================================================
# بيانات التصويت
# =========================================================

votes_data = read_json(
    VOTES_FILE,
    {
        "voters": {},
        "message_id": None
    }
)

votes_data.setdefault("voters", {})
votes_data.setdefault("message_id", None)


def save_votes():
    write_json(VOTES_FILE, votes_data)


# =========================================================
# بيانات الحماية
# =========================================================

protection_data = read_json(
    PROTECTION_FILE,
    {
        "ban_history": {},
        "processed_audit": []
    }
)

protection_data.setdefault("ban_history", {})
protection_data.setdefault("processed_audit", [])


def save_protection():
    write_json(PROTECTION_FILE, protection_data)


# =========================================================
# إعداد البوت
# =========================================================

intents = discord.Intents.default()

intents.guilds = True
intents.members = True
intents.message_content = True
intents.moderation = True

bot = commands.Bot(
    command_prefix=("-", "."),
    intents=intents
)


# =========================================================
# أدوات التنبيهات الخاصة
# =========================================================

async def send_protection_alert(
    guild,
    title,
    description,
    color=discord.Color.red()
):
    embed = discord.Embed(
        title=f"🛡️ {title}",
        description=description,
        color=color,
        timestamp=discord.utils.utcnow()
    )

    embed.add_field(
        name="السيرفر",
        value=f"{guild.name}\n`{guild.id}`",
        inline=False
    )

    embed.set_footer(
        text="NJ | نظام الحماية الآلي"
    )

    for user_id in ALERT_USER_IDS:
        try:
            user = await bot.fetch_user(user_id)

            await user.send(
                embed=embed,
                allowed_mentions=discord.AllowedMentions.none()
            )

        except discord.Forbidden:
            print(
                f"Cannot DM alert recipient: {user_id}"
            )

        except discord.NotFound:
            print(
                f"Alert recipient not found: {user_id}"
            )

        except discord.HTTPException as error:
            print(
                f"Alert DM error: {error}"
            )


# =========================================================
# سجل عمليات Audit Log
# =========================================================

async def get_audit_entry(
    guild,
    action,
    target_id,
    retries=4
):
    async with audit_lock:

        for attempt in range(retries):

            try:
                async for entry in guild.audit_logs(
                    limit=15,
                    action=action
                ):

                    target = entry.target

                    if target is None:
                        continue

                    if getattr(target, "id", None) != target_id:
                        continue

                    age = (
                        discord.utils.utcnow() - entry.created_at
                    ).total_seconds()

                    if age > 30:
                        continue

                    entry_id = str(entry.id)

                    if entry_id in protection_data["processed_audit"]:
                        continue

                    protection_data["processed_audit"].append(
                        entry_id
                    )

                    protection_data["processed_audit"] = (
                        protection_data["processed_audit"][-3000:]
                    )

                    save_protection()

                    return entry

            except discord.Forbidden:
                print(
                    "Missing View Audit Log permission."
                )
                return None

            except discord.HTTPException as error:
                print(
                    f"Audit log error: {error}"
                )

            if attempt < retries - 1:
                await asyncio.sleep(1.5)

    return None


# =========================================================
# نظام طرد المخالف
# =========================================================

async def punish_executor(
    guild,
    executor,
    reason
):
    if executor is None:
        return False

    if executor.bot:
        return False

    try:
        await guild.kick(
            executor,
            reason=f"NJ Anti-Nuke: {reason}"
        )

        return True

    except discord.Forbidden:
        print(
            f"Cannot kick executor: {executor.id}"
        )

    except discord.HTTPException as error:
        print(
            f"Kick error: {error}"
        )

    return False


# =========================================================
# نظام حماية الباند
# =========================================================

async def register_ban(
    guild,
    executor,
    target
):
    if executor is None or executor.bot:
        return

    now = time.time()

    guild_key = str(guild.id)
    executor_key = str(executor.id)

    async with protection_lock:

        if guild_key not in protection_data["ban_history"]:
            protection_data["ban_history"][guild_key] = {}

        history = protection_data["ban_history"][guild_key]

        if executor_key not in history:
            history[executor_key] = []

        timestamps = history[executor_key]

        # الاحتفاظ بآخر 24 ساعة فقط
        timestamps = [
            stamp for stamp in timestamps
            if now - stamp < DAY_SECONDS
        ]

        timestamps.append(now)

        history[executor_key] = timestamps

        hourly_count = sum(
            now - stamp < HOUR_SECONDS
            for stamp in timestamps
        )

        daily_count = len(timestamps)

        exceeded = (
            hourly_count > BAN_HOURLY_LIMIT
            or daily_count > BAN_DAILY_LIMIT
        )

        save_protection()

    if exceeded:

        kicked = await punish_executor(
            guild,
            executor,
            "تجاوز حد عمليات الباند"
        )

        status = (
            "تم طرد منفّذ العملية."
            if kicked
            else "تعذر طرد منفّذ العملية."
        )

        description = (
            f"**الشخص المسؤول:** {executor.mention}\n"
            f"**الشخص الذي تم تبنيده:** `{target}`\n"
            f"**عدد الباندات خلال الساعة:** {hourly_count}/5\n"
            f"**عدد الباندات خلال 24 ساعة:** {daily_count}/5\n"
            f"**الإجراء:** {status}"
        )

        await send_protection_alert(
            guild,
            "تجاوز حد الباند!",
            description
        )

    else:

        description = (
            f"**الشخص المسؤول:** {executor.mention}\n"
            f"**العضو الذي تم تبنيده:** `{target}`\n"
            f"**الباندات خلال الساعة:** {hourly_count}/5\n"
            f"**الباندات خلال 24 ساعة:** {daily_count}/5\n"
            f"**الحالة:** ضمن الحد المسموح."
        )

        await send_protection_alert(
            guild,
            "عملية باند جديدة",
            description,
            discord.Color.orange()
        )


@bot.event
async def on_member_ban(guild, user):

    entry = await get_audit_entry(
        guild,
        discord.AuditLogAction.ban,
        user.id
    )

    if entry is None:
        print(
            f"Could not identify ban executor for {user.id}"
        )
        return

    await register_ban(
        guild,
        entry.user,
        user
    )


# =========================================================
# حماية إضافة البوتات
# =========================================================

@bot.event
async def on_member_join(member):

    if not member.bot:
        return

    guild = member.guild

    entry = await get_audit_entry(
        guild,
        discord.AuditLogAction.bot_add,
        member.id
    )

    if entry is None:
        await send_protection_alert(
            guild,
            "إضافة بوت غير معروفة",
            (
                f"**البوت:** {member.mention}\n"
                "تعذر تحديد الشخص الذي أضاف البوت من سجل التدقيق.\n"
                "يرجى مراجعة سجل Audit Log يدوياً."
            )
        )
        return

    executor = entry.user

    if executor is None or executor.bot:
        return

    # طرد الشخص الذي أضاف البوت
    actor_kicked = await punish_executor(
        guild,
        executor,
        "إضافة بوت غير مصرح به"
    )

    # طرد البوت الجديد
    bot_kicked = False

    try:
        await guild.kick(
            member,
            reason="NJ Anti-Nuke: Unauthorized bot"
        )

        bot_kicked = True

    except discord.Forbidden:
        print(
            f"Cannot kick added bot: {member.id}"
        )

    except discord.HTTPException as error:
        print(
            f"Added bot kick error: {error}"
        )

    description = (
        f"**الشخص الذي أضاف البوت:** {executor.mention}\n"
        f"**البوت المضاف:** {member.mention}\n\n"
        f"**طرد الشخص:** {'تم' if actor_kicked else 'تعذر'}\n"
        f"**طرد البوت:** {'تم' if bot_kicked else 'تعذر'}"
    )

    await send_protection_alert(
        guild,
        "إضافة بوت غير مصرح به!",
        description
    )


# =========================================================
# حماية حذف الرتب
# =========================================================

@bot.event
async def on_guild_role_delete(role):

    guild = role.guild

    entry = await get_audit_entry(
        guild,
        discord.AuditLogAction.role_delete,
        role.id
    )

    if entry is None:
        await send_protection_alert(
            guild,
            "حذف رتبة",
            (
                f"**الرتبة المحذوفة:** `{role.name}`\n"
                "تعذر تحديد المسؤول من سجل التدقيق."
            )
        )
        return

    executor = entry.user

    if executor is None or executor.bot:
        return

    kicked = await punish_executor(
        guild,
        executor,
        "حذف رتبة من السيرفر"
    )

    description = (
        f"**الشخص المسؤول:** {executor.mention}\n"
        f"**الرتبة المحذوفة:** `{role.name}`\n"
        f"**معرف الرتبة:** `{role.id}`\n"
        f"**الإجراء:** {'تم الطرد' if kicked else 'تعذر الطرد'}"
    )

    await send_protection_alert(
        guild,
        "تم حذف رتبة!",
        description
    )


# =========================================================
# حماية حذف الرومات
# =========================================================

@bot.event
async def on_guild_channel_delete(channel):

    guild = channel.guild

    entry = await get_audit_entry(
        guild,
        discord.AuditLogAction.channel_delete,
        channel.id
    )

    if entry is None:
        await send_protection_alert(
            guild,
            "حذف روم",
            (
                f"**الروم المحذوف:** `{channel.name}`\n"
                "تعذر تحديد المسؤول من سجل التدقيق."
            )
        )
        return

    executor = entry.user

    if executor is None or executor.bot:
        return

    kicked = await punish_executor(
        guild,
        executor,
        "حذف روم من السيرفر"
    )

    description = (
        f"**الشخص المسؤول:** {executor.mention}\n"
        f"**الروم المحذوف:** `{channel.name}`\n"
        f"**معرف الروم:** `{channel.id}`\n"
        f"**الإجراء:** {'تم الطرد' if kicked else 'تعذر الطرد'}"
    )

    await send_protection_alert(
        guild,
        "تم حذف روم!",
        description
    )


# =========================================================
# نظام البقاء في روم الفويس
# =========================================================

async def keep_bot_in_voice():

    await bot.wait_until_ready()

    while not bot.is_closed():

        try:
            channel = bot.get_channel(
                VOICE_CHANNEL_ID
            )

            if channel is None:
                try:
                    channel = await bot.fetch_channel(
                        VOICE_CHANNEL_ID
                    )

                except discord.NotFound:
                    print("Voice channel not found.")
                    await asyncio.sleep(30)
                    continue

            if not isinstance(
                channel,
                (
                    discord.VoiceChannel,
                    discord.StageChannel
                )
            ):
                print("Selected channel is not voice.")
                await asyncio.sleep(30)
                continue

            voice_client = channel.guild.voice_client

            if voice_client is None:

                await channel.connect(
                    timeout=30,
                    reconnect=True
                )

                print("Bot joined voice channel.")

            elif not voice_client.is_connected():

                try:
                    await voice_client.disconnect(
                        force=True
                    )

                except discord.HTTPException:
                    pass

                await channel.connect(
                    timeout=30,
                    reconnect=True
                )

                print("Voice connection restored.")

            elif voice_client.channel.id != VOICE_CHANNEL_ID:

                await voice_client.move_to(channel)

                print("Bot returned to configured voice.")

        except discord.Forbidden:
            print("Missing voice permissions.")

        except discord.HTTPException as error:
            print(f"Voice error: {error}")

        except asyncio.CancelledError:
            raise

        except Exception as error:
            print(f"Voice system error: {error}")

        await asyncio.sleep(15)


# =========================================================
# نظام التصويت
# =========================================================

def get_vote_counts():

    citizens = sum(
        value == "citizen"
        for value in votes_data["voters"].values()
    )

    military = sum(
        value == "military"
        for value in votes_data["voters"].values()
    )

    return citizens, military


def create_vote_embed():

    citizens, military = get_vote_counts()

    embed = discord.Embed(
        title="🎮 رول بلاي | منتدى نجد",
        description="اختر القسم المناسب حسب رتبتك.",
        color=discord.Color.from_rgb(
            105,
            65,
            125
        )
    )

    embed.add_field(
        name="👤 تصويت المواطنين",
        value=(
            f"العدد المطلوب لفتح الروم: **{CITIZEN_LIMIT}**\n"
            f"العدد الحالي: **{citizens}**"
        ),
        inline=False
    )

    embed.add_field(
        name="🚔 تصويت العساكر",
        value=(
            f"العدد المطلوب لفتح الروم: **{MILITARY_LIMIT}**\n"
            f"العدد الحالي: **{military}**"
        ),
        inline=False
    )

    embed.add_field(
        name="📜 قوانين الرول بلاي",
        value=(
            f"يرجى قراءة القوانين قبل التصويت.\n"
            f"📌 <#{RULES_CHANNEL_ID}>"
        ),
        inline=False
    )

    embed.add_field(
        name="📌 التعليمات",
        value=(
            "• يجب امتلاك الرتبة المطلوبة للتصويت.\n"
            "• لكل عضو تصويت واحد فقط.\n"
            "• يمكنك تغيير تصويتك أو إلغاؤه.\n"
            "• لا يوجد حد أقصى للمصوتين."
        ),
        inline=False
    )

    embed.set_footer(
        text="منتدى نجد | نظام التصويت الرسمي"
    )

    return embed


class RoleVoteView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    async def process_vote(
        self,
        interaction,
        vote_type
    ):

        if interaction.guild is None or not isinstance(
            interaction.user,
            discord.Member
        ):

            return await interaction.response.send_message(
                "هذا التصويت متاح داخل السيرفر فقط.",
                ephemeral=True
            )

        if interaction.message.id != votes_data.get(
            "message_id"
        ):

            return await interaction.response.send_message(
                "هذا التصويت غير فعال.",
                ephemeral=True
            )

        member = interaction.user

        required_role = (
            CITIZEN_ROLE_ID
            if vote_type == "citizen"
            else MILITARY_ROLE_ID
        )

        if not any(
            role.id == required_role
            for role in member.roles
        ):

            return await interaction.response.send_message(
                "❌ لا تمتلك الرتبة المطلوبة للتصويت.",
                ephemeral=True
            )

        user_id = str(member.id)

        async with vote_lock:

            previous = votes_data["voters"].get(
                user_id
            )

            if previous == vote_type:

                return await interaction.response.send_message(
                    "أنت مصوت في هذا القسم بالفعل.",
                    ephemeral=True
                )

            votes_data["voters"][user_id] = vote_type

            save_votes()

            await interaction.response.edit_message(
                embed=create_vote_embed(),
                view=self
            )

    @discord.ui.button(
        label="المواطنين",
        emoji="✅",
        style=discord.ButtonStyle.success,
        custom_id="nj_citizen_vote",
        row=0
    )
    async def citizen_button(
        self,
        interaction,
        button
    ):
        await self.process_vote(
            interaction,
            "citizen"
        )

    @discord.ui.button(
        label="العساكر",
        emoji="🚔",
        style=discord.ButtonStyle.primary,
        custom_id="nj_military_vote",
        row=0
    )
    async def military_button(
        self,
        interaction,
        button
    ):
        await self.process_vote(
            interaction,
            "military"
        )

    @discord.ui.button(
        label="إلغاء تصويتي",
        emoji="❌",
        style=discord.ButtonStyle.danger,
        custom_id="nj_cancel_vote",
        row=1
    )
    async def cancel_button(
        self,
        interaction,
        button
    ):

        if interaction.message.id != votes_data.get(
            "message_id"
        ):

            return await interaction.response.send_message(
                "هذا التصويت غير فعال.",
                ephemeral=True
            )

        user_id = str(interaction.user.id)

        async with vote_lock:

            if user_id not in votes_data["voters"]:

                return await interaction.response.send_message(
                    "ليس لديك تصويت لإلغائه.",
                    ephemeral=True
                )

            del votes_data["voters"][user_id]

            save_votes()

            await interaction.response.edit_message(
                embed=create_vote_embed(),
                view=self
            )


# =========================================================
# أمر إنشاء التصويت
# =========================================================

@bot.command(name="رول")
async def create_role_poll(ctx):

    member = ctx.author

    if not isinstance(member, discord.Member):
        return

    allowed = (
        member.guild_permissions.administrator
        or any(
            role.id == ADMIN_ROLE_ID
            for role in member.roles
        )
    )

    if not allowed:

        return await ctx.reply(
            "❌ ليس لديك صلاحية استخدام هذا الأمر."
        )

    async with vote_lock:

        votes_data["voters"] = {}
        votes_data["message_id"] = None

        save_votes()

        message = await ctx.send(
            content=(
                f"<@&{CITIZEN_ROLE_ID}> "
                f"<@&{MILITARY_ROLE_ID}>"
            ),
            embed=create_vote_embed(),
            view=RoleVoteView(),
            allowed_mentions=discord.AllowedMentions(
                roles=True
            )
        )

        votes_data["message_id"] = message.id

        save_votes()


# =========================================================
# إخفاء قنوات المواطن
# =========================================================

@bot.command(name="اخفاء")
@commands.has_permissions(administrator=True)
async def hide_citizen_channels(ctx):

    guild = ctx.guild

    if guild is None:
        return

    citizen_role = guild.get_role(
        CITIZEN_ROLE_ID
    )

    if citizen_role is None:

        return await ctx.reply(
            "❌ لم أجد رتبة المواطن."
        )

    await ctx.reply(
        "⏳ جاري ضبط صلاحيات رتبة المواطن..."
    )

    success = 0
    failed = 0

    for channel in guild.channels:

        try:

            overwrite = channel.overwrites_for(
                citizen_role
            )

            overwrite.view_channel = (
                channel.id in ALLOWED_CHANNELS
            )

            await channel.set_permissions(
                citizen_role,
                overwrite=overwrite,
                reason="NJ Citizen Channel Visibility"
            )

            success += 1

        except (
            discord.Forbidden,
            discord.HTTPException
        ):

            failed += 1

    found = sum(
        1
        for channel in guild.channels
        if channel.id in ALLOWED_CHANNELS
    )

    missing = [
        channel_id
        for channel_id in ALLOWED_CHANNELS
        if guild.get_channel(channel_id) is None
    ]

    result = (
        "✅ **تم تنفيذ أمر الإخفاء.**\n"
        f"🔓 الرومات المسموحة الموجودة: **{found}/4**\n"
        f"🔧 القنوات التي تمت معالجتها: **{success}**\n"
        f"❌ القنوات التي فشل تعديلها: **{failed}**"
    )

    if missing:

        result += (
            "\n⚠️ IDs غير موجودة:\n"
            + "\n".join(
                f"`{channel_id}`"
                for channel_id in missing
            )
        )

    await ctx.send(result)


@hide_citizen_channels.error
async def hide_error(ctx, error):

    if isinstance(
        error,
        commands.MissingPermissions
    ):

        await ctx.reply(
            "❌ هذا الأمر مخصص للإداريين فقط."
        )


# =========================================================
# تسجيل الاسم وإعطاء تصريح اللعب
# =========================================================

@bot.event
async def on_message(message):

    if message.author.bot or message.guild is None:
        return

    if message.content.startswith(("-", ".")):

        await bot.process_commands(message)
        return

    if message.channel.id == NAME_CHANNEL_ID:

        name = message.content.strip()

        if not name:
            return

        if len(name) > 25:

            return await message.reply(
                "❌ الاسم طويل جداً، الحد الأقصى 25 حرف."
            )

        member = message.author

        play_role = message.guild.get_role(
            PLAY_ROLE_ID
        )

        if play_role is None:

            return await message.reply(
                "❌ لم يتم العثور على رتبة تصريح لعب."
            )

        try:

            await member.edit(
                nick=f"NJ | {name}",
                reason="NJ Name Registration"
            )

            if play_role not in member.roles:

                await member.add_roles(
                    play_role,
                    reason="NJ Name Registration"
                )

            await message.delete()

        except discord.Forbidden:

            await message.channel.send(
                "❌ البوت لا يملك صلاحية تعديل الاسم أو إعطاء الرتبة.",
                delete_after=8
            )

        except discord.HTTPException as error:

            print(
                f"Registration error: {error}"
            )

    await bot.process_commands(message)


# =========================================================
# معالجة أخطاء الأوامر
# =========================================================

@bot.event
async def on_command_error(ctx, error):

    if isinstance(
        error,
        commands.CommandNotFound
    ):
        return

    if isinstance(
        error,
        commands.MissingPermissions
    ):

        return await ctx.reply(
            "❌ ليس لديك الصلاحية المطلوبة."
        )

    print(
        f"Command error: {error}"
    )


# =========================================================
# تشغيل واستعادة الأنظمة
# =========================================================

@bot.event
async def on_ready():

    if not getattr(
        bot,
        "_systems_initialized",
        False
    ):

        bot.add_view(
            RoleVoteView()
        )

        bot._systems_initialized = True

    if not getattr(
        bot,
        "_voice_task_started",
        False
    ):

        bot._voice_task_started = True

        bot.loop.create_task(
            keep_bot_in_voice()
        )

    print("=" * 45)
    print(f"Bot Online: {bot.user}")
    print("NJ Registration: ON")
    print("NJ Voting System: ON")
    print("NJ Citizen Hide System: ON")
    print("NJ Voice Auto-Reconnect: ON")
    print("NJ Anti-Nuke Protection: ON")
    print("NJ Ban Protection: 5/hour + 5/day")
    print("NJ Bot Protection: ON")
    print("NJ Role Delete Protection: ON")
    print("NJ Channel Delete Protection: ON")
    print("NJ Private Alerts: ON")
    print("Ticket System: REMOVED")
    print("=" * 45)


# =========================================================
# تشغيل البوت
# =========================================================

if not TOKEN:
    raise ValueError(
        "TOKEN environment variable is missing!"
    )

bot.run(TOKEN)
