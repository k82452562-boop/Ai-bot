const { Client, GatewayIntentBits } = require('discord.js');
const { GoogleGenAI } = require('@google/genai');

const client = new Client({
    intents: [
        GatewayIntentBits.Guilds,
        GatewayIntentBits.GuildMessages,
        GatewayIntentBits.MessageContent,
    ],
});

const ai = new GoogleGenAI({ apiKey: process.env.GEMINI_API_KEY });

client.once('ready', () => {
    logWithTimestamp(`تم تسجيل دخول البوت بنجاح باسم: ${client.user.tag}`);
});

client.on('messageCreate', async (message) => {
    if (message.author.bot) return;

    // يشتغل البوت لو منشنوه أو ردوا على رسالته، أو كتبوا في السيرفر
    if (message.content.startsWith('!ai') || message.mentions.has(client.user)) {
        try {
            await message.channel.sendTyping();
            const prompt = message.content.replace(/<@!?\d+>/g, '').replace('!ai', '').trim();

            if (!prompt) {
                return message.reply('هاه يا طويل العمر؟ امسحها بوجهي وقول وش بغيت؟');
            }

            const response = await ai.models.generateContent({
                model: 'gemini-2.5-flash',
                contents: prompt,
                config: {
                    systemInstruction: "أنت ذكاء اصطناعي سعودي صارم ودقيق بلهجة سعودية راكدة ومحترمة، وفي حال المزح أو الاستهبال تقلب طقطقة بأسلوب ساخر وممتع.",
                }
            });

            const replyText = response.text || 'عذراً، صار فيه خطأ بالرد يا الغالي.';
            
            if (replyText.length > 2000) {
                await message.reply(replyText.substring(0, 1999));
            } else {
                await message.reply(replyText);
            }
        } catch (error) {
            console.error('خطأ في توليد الرد:', error);
            await message.reply('عذراً، صار فيه التماس فكري دقايق واضبطك.');
        }
    }
});

function logWithTimestamp(message) {
    const timeString = new Date().toLocaleTimeString('en-US', { hour12: false });
    console.log(`[${timeString}] ${message}`);
}

client.login(process.env.DISCORD_TOKEN);
