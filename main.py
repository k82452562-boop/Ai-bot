
import discord
from discord.ext import commands
import os

# إعدادات البوت
TOKEN = os.getenv("TOKEN")

NAME_CHANNEL_ID = 1569992736759877732
ROLE_ID = 1569980718262784101

# الصلاحيات
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(
    command_prefix="!",
    intents=intents
)


@bot.event
async def on_ready():
    print(f"Bot Online: {bot.user}")
    print("NJ Registration System Started")


@bot.event
async def on_message(message):

    # تجاهل رسائل البوتات
    if message.author.bot:
        return

    # التأكد من روم التسجيل
    if message.channel.id != NAME_CHANNEL_ID:
        await bot.process_commands(message)
        return

    name = message.content.strip()

    # منع الاسم الفارغ
    if not name:
        return

    # تحديد طول الاسم
    if len(name) > 25:
        await message.reply(
            "الاسم طويل جداً، الحد الأقصى 25 حرف."
        )
        return

    member = message.author
    guild = message.guild

    try:
        # تغيير لقب العضو
        await member.edit(
            nick=f"NJ | {name}",
            reason="NJ Name Registration"
        )

        # جلب الرتبة
        role = guild.get_role(ROLE_ID)

        if role is None:
            await message.reply("لم يتم العثور على الرتبة.")
            return

        # إعطاء الرتبة
        await member.add_roles(
            role,
            reason="NJ Name Registration"
        )

        # حذف رسالة التسجيل
        await message.delete()

        print(f"Registered: {member} -> NJ | {name}")

    except discord.Forbidden:
        print("Error: Missing permissions")

    except discord.HTTPException as error:
        print(f"Discord Error: {error}")

    await bot.process_commands(message)


# تشغيل البوت
if not TOKEN:
    raise ValueError("TOKEN environment variable is missing!")

bot.run(TOKEN)
