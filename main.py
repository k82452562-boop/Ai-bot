
import os
import json
import asyncio
import discord
from discord.ext import commands
from discord import app_commands

# =========================================================
# إعدادات عامة
# =========================================================

TOKEN = os.getenv("TOKEN")

NAME_CHANNEL_ID = 1569992736759877732
PLAY_ROLE_ID = 1569980718262784101

CITIZEN_ROLE_ID = 1562060450017972305
MILITARY_ROLE_ID = 1567933281301700628
ADMIN_ROLE_ID = 1567943636413321419

RULES_CHANNEL_ID = 1569788828296679565

# روم الفويس الذي يجب أن يبقى البوت داخله
VOICE_CHANNEL_ID = 1570498914140819546

ALLOWED_CHANNELS = [
    1569992736759877732,
    1561852188186124519,
    1561852197812043886,
    1561852196641833050
]

CITIZEN_LIMIT = 7
MILITARY_LIMIT = 2

VOTES_FILE = "votes.json"
TICKET_CONFIG_FILE = "ticket_config.json"
TICKETS_FILE = "tickets.json"

vote_lock = asyncio.Lock()
ticket_lock = asyncio.Lock()


def read_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else default.copy()
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return default.copy()


def write_json(path, data):
    temp_path = path + ".tmp"
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    os.replace(temp_path, path)


votes_data = read_json(VOTES_FILE, {"voters": {}, "message_id": None})
votes_data.setdefault("voters", {})
votes_data.setdefault("message_id", None)

DEFAULT_TICKET_CONFIG = {
    "title": "نظام التذاكر",
    "description": "اضغط على الزر لفتح تذكرة جديدة.",
    "footer": "",
    "image": "",
    "panel_type": "button",
    "button_name": "فتح تذكرة 🎫",
    "category_id": None,
    "admin_roles": [],
    "ask_reason": False,
    "support_limit": "infinite",
    "admin_limit": "infinite",
    "open_title": "مرحباً بك في التذكرة",
    "open_desc": "يرجى الانتظار لحين رد الإدارة عليك.",
    "open_image": None
}

ticket_config = read_json(TICKET_CONFIG_FILE, DEFAULT_TICKET_CONFIG)
for key, value in DEFAULT_TICKET_CONFIG.items():
    ticket_config.setdefault(key, value)

tickets_data = read_json(TICKETS_FILE, {"tickets": {}})
tickets_data.setdefault("tickets", {})


def save_votes():
    write_json(VOTES_FILE, votes_data)


def save_ticket_config():
    write_json(TICKET_CONFIG_FILE, ticket_config)


def save_tickets():
    write_json(TICKETS_FILE, tickets_data)


# =========================================================
# إعداد البوت
# =========================================================

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix=("-", "."), intents=intents)


# =========================================================
# نظام البقاء في روم الفويس
# =========================================================

async def keep_bot_in_voice():
    await bot.wait_until_ready()

    while not bot.is_closed():
        try:
            channel = bot.get_channel(VOICE_CHANNEL_ID)

            if channel is None:
                try:
                    channel = await bot.fetch_channel(VOICE_CHANNEL_ID)
                except discord.NotFound:
                    print("Voice channel not found.")
                    await asyncio.sleep(30)
                    continue

            if not isinstance(
                channel,
                (discord.VoiceChannel, discord.StageChannel)
            ):
                print("The selected channel is not a voice channel.")
                await asyncio.sleep(30)
                continue

            voice_client = channel.guild.voice_client

            if voice_client is None:
                await channel.connect(
                    timeout=30,
                    reconnect=True
                )
                print("Bot joined the voice channel.")

            elif not voice_client.is_connected():
                try:
                    await voice_client.disconnect(force=True)
                except discord.HTTPException:
                    pass

                await channel.connect(
                    timeout=30,
                    reconnect=True
                )
                print("Voice connection restored.")

            elif voice_client.channel.id != VOICE_CHANNEL_ID:
                await voice_client.move_to(channel)
                print("Bot returned to the configured voice channel.")

        except discord.Forbidden:
            print("Missing permission to join the voice channel.")

        except discord.HTTPException as error:
            print(f"Discord voice error: {error}")

        except asyncio.CancelledError:
            raise

        except Exception as error:
            print(f"Voice system error: {error}")

        await asyncio.sleep(15)


# =========================================================
# نظام التصويت
# =========================================================

def get_vote_counts():
    citizens = sum(v == "citizen" for v in votes_data["voters"].values())
    military = sum(v == "military" for v in votes_data["voters"].values())
    return citizens, military


def create_vote_embed():
    citizens, military = get_vote_counts()

    embed = discord.Embed(
        title="🎮 رول بلاي | منتدى نجد",
        description="اختر القسم المناسب حسب رتبتك.",
        color=discord.Color.from_rgb(105, 65, 125)
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
        value=f"يرجى قراءة القوانين قبل التصويت.\n📌 <#{RULES_CHANNEL_ID}>",
        inline=False
    )

    embed.add_field(
        name="📌 التعليمات",
        value=(
            "• يجب امتلاك الرتبة المطلوبة للتصويت.\n"
            "• لكل عضو تصويت واحد فقط.\n"
            "• يمكنك تغيير تصويتك أو إلغاؤه.\n"
            "• العدد الحالي مفتوح ولا يوجد حد أقصى للمصوتين."
        ),
        inline=False
    )

    embed.set_footer(text="منتدى نجد | نظام التصويت الرسمي")
    return embed


class RoleVoteView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def process_vote(self, interaction, vote_type):
        if interaction.guild is None or not isinstance(
            interaction.user, discord.Member
        ):
            return await interaction.response.send_message(
                "هذا التصويت متاح داخل السيرفر فقط.",
                ephemeral=True
            )

        if interaction.message.id != votes_data.get("message_id"):
            return await interaction.response.send_message(
                "هذا التصويت غير فعال.",
                ephemeral=True
            )

        member = interaction.user
        required_role = (
            CITIZEN_ROLE_ID if vote_type == "citizen"
            else MILITARY_ROLE_ID
        )

        if not any(role.id == required_role for role in member.roles):
            return await interaction.response.send_message(
                "❌ لا تمتلك الرتبة المطلوبة للتصويت.",
                ephemeral=True
            )

        user_id = str(member.id)

        async with vote_lock:
            previous = votes_data["voters"].get(user_id)

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
    async def citizen_button(self, interaction, button):
        await self.process_vote(interaction, "citizen")

    @discord.ui.button(
        label="العساكر",
        emoji="🚔",
        style=discord.ButtonStyle.primary,
        custom_id="nj_military_vote",
        row=0
    )
    async def military_button(self, interaction, button):
        await self.process_vote(interaction, "military")

    @discord.ui.button(
        label="إلغاء تصويتي",
        emoji="❌",
        style=discord.ButtonStyle.danger,
        custom_id="nj_cancel_vote",
        row=1
    )
    async def cancel_button(self, interaction, button):
        if interaction.message.id != votes_data.get("message_id"):
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


@bot.command(name="رول")
async def create_role_poll(ctx):
    member = ctx.author

    if not isinstance(member, discord.Member):
        return

    allowed = (
        member.guild_permissions.administrator
        or any(role.id == ADMIN_ROLE_ID for role in member.roles)
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
            content=f"<@&{CITIZEN_ROLE_ID}> <@&{MILITARY_ROLE_ID}>",
            embed=create_vote_embed(),
            view=RoleVoteView(),
            allowed_mentions=discord.AllowedMentions(roles=True)
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

    citizen_role = guild.get_role(CITIZEN_ROLE_ID)

    if citizen_role is None:
        return await ctx.reply("❌ لم أجد رتبة المواطن.")

    await ctx.reply("⏳ جاري ضبط صلاحيات رتبة المواطن...")

    success = 0
    failed = 0

    for channel in guild.channels:
        try:
            overwrite = channel.overwrites_for(citizen_role)
            overwrite.view_channel = channel.id in ALLOWED_CHANNELS

            await channel.set_permissions(
                citizen_role,
                overwrite=overwrite,
                reason="NJ Citizen Channel Visibility"
            )

            success += 1

        except (discord.Forbidden, discord.HTTPException):
            failed += 1

    found = sum(
        1 for c in guild.channels
        if c.id in ALLOWED_CHANNELS
    )

    missing = [
        cid for cid in ALLOWED_CHANNELS
        if guild.get_channel(cid) is None
    ]

    result = (
        "✅ **تم تنفيذ أمر الإخفاء.**\n"
        f"🔓 الرومات المسموحة الموجودة: **{found}/4**\n"
        f"🔧 القنوات التي تمت معالجتها: **{success}**\n"
        f"❌ القنوات التي فشل تعديلها: **{failed}**"
    )

    if missing:
        result += "\n⚠️ IDs غير موجودة:\n" + "\n".join(
            f"`{x}`" for x in missing
        )

    await ctx.send(result)


@hide_citizen_channels.error
async def hide_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.reply("❌ هذا الأمر مخصص للإداريين فقط.")


# =========================================================
# نظام تسجيل الاسم وإعطاء تصريح لعب
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
        play_role = message.guild.get_role(PLAY_ROLE_ID)

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
            print(f"Registration error: {error}")

    await bot.process_commands(message)


# =========================================================
# نوافذ إعداد التذاكر (Modals)
# =========================================================

class TicketPanelModal(discord.ui.Modal, title="إعداد بانل التكت"):
    panel_title = discord.ui.TextInput(
        label="عنوان البانل",
        required=True
    )

    panel_description = discord.ui.TextInput(
        label="وصف البانل",
        style=discord.TextStyle.paragraph,
        required=True
    )

    panel_footer = discord.ui.TextInput(
        label="الذيل (اختياري)",
        required=False
    )

    panel_image = discord.ui.TextInput(
        label="رابط صورة البانل (اختياري)",
        required=False
    )

    async def on_submit(self, interaction):
        ticket_config["title"] = self.panel_title.value
        ticket_config["description"] = self.panel_description.value
        ticket_config["footer"] = self.panel_footer.value or ""
        ticket_config["image"] = self.panel_image.value or ""

        save_ticket_config()

        await interaction.response.send_message(
            "✅ تم حفظ إعدادات البانل.",
            ephemeral=True
        )


class ButtonNameModal(discord.ui.Modal, title="اسم زر فتح التذكرة"):
    item_name = discord.ui.TextInput(
        label="اسم الزر / الخيار",
        required=True
    )

    async def on_submit(self, interaction):
        ticket_config["button_name"] = self.item_name.value
        save_ticket_config()

        await interaction.response.send_message(
            f"✅ تم تغيير الاسم إلى `{self.item_name.value}`.",
            ephemeral=True
        )


class OpenTicketModal(discord.ui.Modal, title="إعداد رسالة التذكرة"):
    ticket_title = discord.ui.TextInput(
        label="عنوان التذكرة",
        required=True
    )

    ticket_desc = discord.ui.TextInput(
        label="وصف التذكرة",
        style=discord.TextStyle.paragraph,
        required=True
    )

    async def on_submit(self, interaction):
        ticket_config["open_title"] = self.ticket_title.value
        ticket_config["open_desc"] = self.ticket_desc.value
        save_ticket_config()

        await interaction.response.send_message(
            "✅ تم حفظ إعدادات رسالة التذكرة.",
            ephemeral=True
        )


class TicketReasonModal(discord.ui.Modal, title="سبب فتح التذكرة"):
    reason = discord.ui.TextInput(
        label="سبب فتح التذكرة",
        style=discord.TextStyle.paragraph,
        required=True
    )

    async def on_submit(self, interaction):
        await interaction.response.defer(ephemeral=True)
        await create_ticket(interaction, self.reason.value)


# =========================================================
# قوائم اختيار الرتب والكاتيجوري والحدود
# =========================================================

class RoleSelectView(discord.ui.View):
    def __init__(self, guild):
        super().__init__(timeout=180)

        roles = [
            r for r in guild.roles
            if not r.is_default()
        ][:25]

        options = [
            discord.SelectOption(
                label=r.name[:100],
                value=str(r.id)
            )
            for r in roles
        ]

        if not options:
            options = [
                discord.SelectOption(
                    label="لا توجد رتب",
                    value="none"
                )
            ]

        select = discord.ui.Select(
            placeholder="اختر رتب الإدارة (حتى 5)",
            min_values=1,
            max_values=min(5, len(options)),
            options=options
        )

        select.callback = self.select_callback
        self.add_item(select)

    async def select_callback(self, interaction):
        selected = [
            int(v)
            for v in interaction.data["values"]
            if v != "none"
        ]

        ticket_config["admin_roles"] = selected
        save_ticket_config()

        mentions = " ".join(
            f"<@&{rid}>" for rid in selected
        ) or "لا توجد رتب"

        await interaction.response.send_message(
            f"✅ تم تحديد رتب الإدارة: {mentions}",
            ephemeral=True
        )


class CategorySelectView(discord.ui.View):
    def __init__(self, guild):
        super().__init__(timeout=180)

        categories = guild.categories[:25]

        options = [
            discord.SelectOption(
                label=c.name[:100],
                value=str(c.id)
            )
            for c in categories
        ]

        if not options:
            options = [
                discord.SelectOption(
                    label="لا توجد كاتيجوري",
                    value="none"
                )
            ]

        select = discord.ui.Select(
            placeholder="اختر كاتيجوري التذاكر",
            min_values=1,
            max_values=1,
            options=options
        )

        select.callback = self.select_callback
        self.add_item(select)

    async def select_callback(self, interaction):
        value = interaction.data["values"][0]

        if value == "none":
            return await interaction.response.send_message(
                "❌ لا توجد كاتيجوري للاختيار.",
                ephemeral=True
            )

        category = interaction.guild.get_channel(int(value))

        if not isinstance(category, discord.CategoryChannel):
            return await interaction.response.send_message(
                "❌ الكاتيجوري غير موجودة.",
                ephemeral=True
            )

        ticket_config["category_id"] = category.id
        save_ticket_config()

        await interaction.response.send_message(
            f"✅ تم تحديد الكاتيجوري: **{category.name}**",
            ephemeral=True
        )


class LimitSelectView(discord.ui.View):
    def __init__(self, limit_key):
        super().__init__(timeout=180)
        self.limit_key = limit_key

        select = discord.ui.Select(
            placeholder="حدد عدد المرات",
            options=[
                discord.SelectOption(label="مرة واحدة", value="1"),
                discord.SelectOption(label="مرتين", value="2"),
                discord.SelectOption(label="3 مرات", value="3"),
                discord.SelectOption(label="4 مرات", value="4"),
                discord.SelectOption(label="5 مرات", value="5"),
                discord.SelectOption(label="لا نهائي", value="infinite")
            ]
        )

        select.callback = self.select_callback
        self.add_item(select)

    async def select_callback(self, interaction):
        value = interaction.data["values"][0]
        ticket_config[self.limit_key] = value
        save_ticket_config()

        label = (
            "لا نهائي"
            if value == "infinite"
            else f"{value} مرات"
        )

        await interaction.response.send_message(
            f"✅ تم تحديد الحد: **{label}**",
            ephemeral=True
        )


# =========================================================
# أدوات التذاكر
# =========================================================

def is_ticket_admin(member):
    if not isinstance(member, discord.Member):
        return False

    admin_roles = ticket_config.get("admin_roles", [])

    return member.guild_permissions.administrator or any(
        role.id in admin_roles
        for role in member.roles
    )


def get_limit_value(key):
    value = ticket_config.get(key, "infinite")

    if value in ("infinite", None, float("inf")):
        return None

    try:
        return int(value)
    except (TypeError, ValueError):
        return None


async def create_ticket(interaction, reason=None):
    guild = interaction.guild

    if guild is None:
        return await interaction.followup.send(
            "❌ هذا الأمر داخل السيرفر فقط.",
            ephemeral=True
        )

    async with ticket_lock:
        for channel_id, data in tickets_data["tickets"].items():
            if data.get("owner_id") == interaction.user.id:
                channel = guild.get_channel(int(channel_id))

                if channel:
                    return await interaction.followup.send(
                        f"❌ لديك تذكرة مفتوحة بالفعل: {channel.mention}",
                        ephemeral=True
                    )

        category_id = ticket_config.get("category_id")
        category = (
            guild.get_channel(category_id)
            if category_id else None
        )

        if category_id and not isinstance(
            category, discord.CategoryChannel
        ):
            return await interaction.followup.send(
                "❌ كاتيجوري التذاكر غير موجودة. أعد تحديدها من لوحة التحكم.",
                ephemeral=True
            )

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(
                view_channel=False
            ),
            interaction.user: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True
            )
        }

        bot_member = guild.me

        if bot_member:
            overwrites[bot_member] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                manage_channels=True
            )

        admin_mentions = []

        for role_id in ticket_config.get("admin_roles", []):
            role = guild.get_role(role_id)

            if role:
                overwrites[role] = discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True
                )
                admin_mentions.append(role.mention)

        safe_name = "".join(
            ch.lower() if ch.isalnum() else "-"
            for ch in interaction.user.name
        )

        channel = await guild.create_text_channel(
            name=f"ticket-{safe_name[:80]}",
            category=category,
            overwrites=overwrites,
            reason=f"Ticket opened by {interaction.user}"
        )

        tickets_data["tickets"][str(channel.id)] = {
            "owner_id": interaction.user.id,
            "claimed_by": None,
            "support_uses": 0,
            "admin_uses": 0,
            "message_id": None
        }

        save_tickets()

    await interaction.followup.send(
        f"✅ تم فتح التذكرة: {channel.mention}",
        ephemeral=True
    )

    embed = discord.Embed(
        title=ticket_config.get(
            "open_title",
            "تذكرة جديدة"
        ),
        description=ticket_config.get(
            "open_desc",
            "مرحباً بك!"
        ),
        color=discord.Color.blue()
    )

    if reason:
        embed.add_field(
            name="سبب فتح التذكرة",
            value=reason[:1024],
            inline=False
        )

    if ticket_config.get("open_image"):
        try:
            embed.set_image(url=ticket_config["open_image"])
        except discord.HTTPException:
            pass

    content = (
        f"{interaction.user.mention} "
        + " ".join(admin_mentions)
    )

    view = InsideTicketView()

    msg = await channel.send(
        content=content,
        embed=embed,
        view=view,
        allowed_mentions=discord.AllowedMentions(
            users=True,
            roles=True
        )
    )

    tickets_data["tickets"][str(channel.id)]["message_id"] = msg.id
    save_tickets()


# =========================================================
# أزرار التذكرة الداخلية
# =========================================================

class InsideTicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    def ticket_data(self, interaction):
        return tickets_data["tickets"].get(
            str(interaction.channel_id)
        )

    @discord.ui.button(
        label="استلام التذكرة 📌",
        style=discord.ButtonStyle.primary,
        custom_id="nj_ticket_claim"
    )
    async def claim_ticket(self, interaction, button):
        data = self.ticket_data(interaction)

        if not data:
            return await interaction.response.send_message(
                "❌ بيانات التذكرة غير موجودة.",
                ephemeral=True
            )

        if not is_ticket_admin(interaction.user):
            return await interaction.response.send_message(
                "❌ هذا الزر للإدارة فقط.",
                ephemeral=True
            )

        if data.get("claimed_by"):
            return await interaction.response.send_message(
                "❌ التذكرة مستلمة بالفعل.",
                ephemeral=True
            )

        data["claimed_by"] = interaction.user.id
        save_tickets()

        await interaction.response.send_message(
            f"📌 تم استلام التذكرة بواسطة {interaction.user.mention}."
        )

        await interaction.message.edit(view=self)

    @discord.ui.button(
        label="إلغاء الاستلام",
        style=discord.ButtonStyle.secondary,
        custom_id="nj_ticket_unclaim"
    )
    async def unclaim_ticket(self, interaction, button):
        data = self.ticket_data(interaction)

        if not data:
            return await interaction.response.send_message(
                "❌ بيانات التذكرة غير موجودة.",
                ephemeral=True
            )

        if not is_ticket_admin(interaction.user):
            return await interaction.response.send_message(
                "❌ هذا الزر للإدارة فقط.",
                ephemeral=True
            )

        if (
            data.get("claimed_by") != interaction.user.id
            and not interaction.user.guild_permissions.administrator
        ):
            return await interaction.response.send_message(
                "❌ فقط مستلم التذكرة أو المدير يمكنه إلغاء الاستلام.",
                ephemeral=True
            )

        data["claimed_by"] = None
        save_tickets()

        await interaction.response.send_message(
            "🔄 تم إلغاء استلام التذكرة."
        )

        await interaction.message.edit(view=self)

    @discord.ui.button(
        label="طلب الدعم 📢",
        style=discord.ButtonStyle.success,
        custom_id="nj_ticket_support"
    )
    async def request_support(self, interaction, button):
        data = self.ticket_data(interaction)

        if not data:
            return await interaction.response.send_message(
                "❌ بيانات التذكرة غير موجودة.",
                ephemeral=True
            )

        if interaction.user.id != data["owner_id"]:
            return await interaction.response.send_message(
                "❌ هذا الزر لصاحب التذكرة فقط.",
                ephemeral=True
            )

        limit = get_limit_value("support_limit")

        if limit is not None and data["support_uses"] >= limit:
            return await interaction.response.send_message(
                "❌ وصلت للحد الأقصى لطلب الدعم.",
                ephemeral=True
            )

        data["support_uses"] += 1
        save_tickets()

        roles = [
            interaction.guild.get_role(rid)
            for rid in ticket_config.get("admin_roles", [])
        ]

        mentions = " ".join(
            r.mention for r in roles if r
        )

        await interaction.response.send_message(
            f"📢 **طلب دعم من {interaction.user.mention}**\n{mentions}",
            allowed_mentions=discord.AllowedMentions(
                roles=True,
                users=True
            )
        )

    @discord.ui.button(
        label="طلب الإداري",
        style=discord.ButtonStyle.primary,
        custom_id="nj_ticket_admin"
    )
    async def request_admin(self, interaction, button):
        data = self.ticket_data(interaction)

        if not data:
            return await interaction.response.send_message(
                "❌ بيانات التذكرة غير موجودة.",
                ephemeral=True
            )

        if interaction.user.id != data["owner_id"]:
            return await interaction.response.send_message(
                "❌ هذا الزر لصاحب التذكرة فقط.",
                ephemeral=True
            )

        limit = get_limit_value("admin_limit")

        if limit is not None and data["admin_uses"] >= limit:
            return await interaction.response.send_message(
                "❌ وصلت للحد الأقصى لطلب الإداري.",
                ephemeral=True
            )

        data["admin_uses"] += 1
        save_tickets()

        roles = [
            interaction.guild.get_role(rid)
            for rid in ticket_config.get("admin_roles", [])
        ]

        mentions = " ".join(
            r.mention for r in roles if r
        )

        await interaction.response.send_message(
            f"🔔 طلب صاحب التذكرة {interaction.user.mention} حضور إداري.\n{mentions}",
            allowed_mentions=discord.AllowedMentions(
                roles=True,
                users=True
            )
        )

    @discord.ui.button(
        label="إغلاق التذكرة ⛔",
        style=discord.ButtonStyle.danger,
        custom_id="nj_ticket_close"
    )
    async def close_ticket(self, interaction, button):
        if not is_ticket_admin(interaction.user):
            return await interaction.response.send_message(
                "❌ إغلاق التذكرة للإدارة فقط.",
                ephemeral=True
            )

        await interaction.response.send_message(
            "⛔ سيتم حذف التذكرة خلال 5 ثوانٍ."
        )

        await asyncio.sleep(5)

        tickets_data["tickets"].pop(
            str(interaction.channel_id),
            None
        )

        save_tickets()

        await interaction.channel.delete(
            reason=f"Ticket closed by {interaction.user}"
        )


# =========================================================
# زر فتح التذكرة في البانل
# =========================================================

class TicketLauncherView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

        label = ticket_config.get(
            "button_name",
            "فتح تذكرة 🎫"
        )[:80]

        if ticket_config.get("panel_type") == "select":
            select = discord.ui.Select(
                placeholder="اختر لفتح تذكرة...",
                options=[
                    discord.SelectOption(
                        label=label,
                        value="open_ticket"
                    )
                ],
                custom_id="nj_ticket_open_select"
            )

            select.callback = self.open_ticket
            self.add_item(select)

        else:
            button = discord.ui.Button(
                label=label,
                style=discord.ButtonStyle.success,
                custom_id="nj_ticket_open_button"
            )

            button.callback = self.open_ticket
            self.add_item(button)

    async def open_ticket(self, interaction):
        if ticket_config.get("ask_reason"):
            await interaction.response.send_modal(
                TicketReasonModal()
            )
        else:
            await interaction.response.defer(ephemeral=True)
            await create_ticket(interaction)


# =========================================================
# لوحة تحكم إعداد التذاكر
# =========================================================

class SetupControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)

    @discord.ui.button(
        label="إعداد بانل التكت",
        style=discord.ButtonStyle.primary,
        row=0
    )
    async def config_panel(self, interaction, button):
        await interaction.response.send_modal(
            TicketPanelModal()
        )

    @discord.ui.button(
        label="نوع البانل",
        style=discord.ButtonStyle.secondary,
        row=0
    )
    async def config_type(self, interaction, button):
        ticket_config["panel_type"] = (
            "select"
            if ticket_config.get("panel_type") == "button"
            else "button"
        )

        save_ticket_config()

        await interaction.response.send_message(
            f"🔄 نوع البانل الآن: **{ticket_config['panel_type'].upper()}**",
            ephemeral=True
        )

    @discord.ui.button(
        label="اسم الزر / الخيار",
        style=discord.ButtonStyle.primary,
        row=0
    )
    async def config_button_name(self, interaction, button):
        await interaction.response.send_modal(
            ButtonNameModal()
        )

    @discord.ui.button(
        label="تحديد Category",
        style=discord.ButtonStyle.secondary,
        row=1
    )
    async def config_category(self, interaction, button):
        await interaction.response.send_message(
            "اختر كاتيجوري التذاكر:",
            view=CategorySelectView(interaction.guild),
            ephemeral=True
        )

    @discord.ui.button(
        label="تحديد رتب الإدارة",
        style=discord.ButtonStyle.primary,
        row=1
    )
    async def config_roles(self, interaction, button):
        await interaction.response.send_message(
            "اختر رتب الإدارة (حتى 5):",
            view=RoleSelectView(interaction.guild),
            ephemeral=True
        )

    @discord.ui.button(
        label="تفعيل / تعطيل طلب السبب",
        style=discord.ButtonStyle.danger,
        row=1
    )
    async def toggle_reason(self, interaction, button):
        ticket_config["ask_reason"] = not ticket_config.get(
            "ask_reason",
            False
        )

        save_ticket_config()

        status = (
            "مفعل 🟢"
            if ticket_config["ask_reason"]
            else "متعطل 🔴"
        )

        await interaction.response.send_message(
            f"طلب السبب الآن: **{status}**",
            ephemeral=True
        )

    @discord.ui.button(
        label="حد طلب الدعم",
        style=discord.ButtonStyle.secondary,
        row=2
    )
    async def config_support_limit(self, interaction, button):
        await interaction.response.send_message(
            "حدد عدد مرات طلب الدعم:",
            view=LimitSelectView("support_limit"),
            ephemeral=True
        )

    @discord.ui.button(
        label="حد طلب الإداري",
        style=discord.ButtonStyle.secondary,
        row=2
    )
    async def config_admin_limit(self, interaction, button):
        await interaction.response.send_message(
            "حدد عدد مرات طلب الإداري:",
            view=LimitSelectView("admin_limit"),
            ephemeral=True
        )

    @discord.ui.button(
        label="تحديد وصف التكت",
        style=discord.ButtonStyle.primary,
        row=3
    )
    async def config_open_desc(self, interaction, button):
        await interaction.response.send_modal(
            OpenTicketModal()
        )

    @discord.ui.button(
        label="تحديد صورة التكت",
        style=discord.ButtonStyle.secondary,
        row=3
    )
    async def config_open_image(self, interaction, button):
        await interaction.response.send_message(
            "أرسل رابط الصورة أو صورة كمرفق خلال 60 ثانية، أو اكتب `تخطي`.",
            ephemeral=True
        )

        def check(msg):
            return (
                msg.author.id == interaction.user.id
                and msg.channel.id == interaction.channel.id
            )

        try:
            msg = await bot.wait_for(
                "message",
                check=check,
                timeout=60
            )

            if msg.content.strip() == "تخطي":
                ticket_config["open_image"] = None

            elif msg.attachments:
                ticket_config["open_image"] = msg.attachments[0].url

            elif msg.content.strip().startswith(("https://", "http://")):
                ticket_config["open_image"] = msg.content.strip()

            else:
                return await interaction.followup.send(
                    "❌ لم أتعرف على الصورة أو الرابط.",
                    ephemeral=True
                )

            save_ticket_config()

            await interaction.followup.send(
                "✅ تم حفظ الصورة.",
                ephemeral=True
            )

        except asyncio.TimeoutError:
            await interaction.followup.send(
                "⏰ انتهى وقت إرسال الصورة.",
                ephemeral=True
            )

    @discord.ui.button(
        label="📩 إرسال البانل الآن",
        style=discord.ButtonStyle.success,
        row=4
    )
    async def send_final_panel(self, interaction, button):
        embed = discord.Embed(
            title=ticket_config["title"],
            description=ticket_config["description"],
            color=discord.Color.blue()
        )

        if ticket_config.get("footer"):
            embed.set_footer(
                text=ticket_config["footer"]
            )

        if ticket_config.get("image"):
            embed.set_image(
                url=ticket_config["image"]
            )

        await interaction.channel.send(
            embed=embed,
            view=TicketLauncherView()
        )

        await interaction.response.send_message(
            "✅ تم إرسال بانل التذاكر.",
            ephemeral=True
        )


# =========================================================
# أمر السلاش لفتح لوحة تحكم التذاكر
# =========================================================

class TicketSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="نظام-تذاكر",
        description="فتح لوحة التحكم بنظام التذاكر"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def setup_ticket(self, interaction):
        embed = discord.Embed(
            title="⚙️ لوحة التحكم وإعداد نظام التذاكر",
            description="استخدم الأزرار لتخصيص البانل ثم أرسله.",
            color=discord.Color.gold()
        )

        await interaction.response.send_message(
            embed=embed,
            view=SetupControlView(),
            ephemeral=True
        )


@bot.tree.error
async def on_app_command_error(interaction, error):
    if isinstance(error, app_commands.MissingPermissions):
        message = "❌ هذا الأمر مخصص للإداريين فقط."
    else:
        print(f"Slash command error: {error}")
        message = "❌ حدث خطأ أثناء تنفيذ الأمر."

    if interaction.response.is_done():
        await interaction.followup.send(
            message,
            ephemeral=True
        )
    else:
        await interaction.response.send_message(
            message,
            ephemeral=True
        )


# =========================================================
# تهيئة ومزامنة أوامر السلاش واستعادة الأزرار
# =========================================================

@bot.event
async def on_ready():
    if not getattr(bot, "_systems_initialized", False):
        await bot.add_cog(TicketSystem(bot))
        await bot.tree.sync()

        bot.add_view(RoleVoteView())
        bot.add_view(TicketLauncherView())
        bot.add_view(InsideTicketView())

        bot._systems_initialized = True

    if not getattr(bot, "_voice_task_started", False):
        bot._voice_task_started = True
        bot.loop.create_task(keep_bot_in_voice())

    print(f"Bot Online: {bot.user}")
    print("NJ Registration, Voting, Hide Channels and Ticket Systems Started")
    print("Voice Auto-Reconnect Started")


# =========================================================
# تشغيل البوت
# =========================================================

if not TOKEN:
    raise ValueError("TOKEN environment variable is missing!")

bot.run(TOKEN)
