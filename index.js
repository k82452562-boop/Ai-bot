const { Client, GatewayIntentBits, SlashCommandBuilder, REST, Routes } = require('discord.js');
const { GoogleGenAI } = require('@google/genai');
require('dotenv').config({ path: 'env.txt' });

const client = new Client({
    intents: [
        GatewayIntentBits.Guilds,
        GatewayIntentBits.GuildMessages,
        GatewayIntentBits.MessageContent
    ]
});

const ai = new GoogleGenAI({ apiKey: process.env.GEMINI_API_KEY });

// توجيهات الشخصية: صارم بالجد، وطقطوقة بالسخافة
const systemPrompt = `
أنت بوت ذكاء اصطناعي سعودي متطور جداً وخبير تقني. أسلوبك يعتمد على الموقف:
1. **في المواضيع الجدية (الذكاء الاصطناعي، البرمجة، التقنية، أو الأسئلة العلمية والعملية):** تصير انسان صارم، دقيق جداً، مهني، وتجاوب باحترافية تامة وبلهجة سعودية راكدة وجادة (مثل: "شوف، علمياً الموضوع كذا كذا...", "هذي لها أصولها البرمجية...").
2. **في الأسئلة التافهة أو السخيفة أو الخارجة عن الاختصاص (سوالف فاضية، أسئلة غبية، ضحك):** تقلب طقطقة واستهبال بأسلوب شبابي سعودي ساخر، وتسحب فيه بس بطريقة مضحكة (مثل: "من جدك أنت تسأل السؤال ذا؟", "والله لو جالس على دباب كان أسرع").
- لغتك الأساسية هي اللهجة السعودية العامية بكل حالاتك (جد أو طقطقة).
`;

// تسجيل أمر /ask
const commands = [
    new SlashCommandBuilder()
        .setName('ask')
        .setDescription('اسأل البوت أي سؤال (صارم في الجد، طقطقة في السخافة)')
        .addStringOption(option =>
            option.setName('question')
                .setDescription('السؤال أو الموضوع اللي تبي تطرحه')
                .setRequired(true)
        )
].map(command => command.toJSON());

client.once('ready', async () => {
    console.log(`✅ البوت اشتغل وجاهز يا طويل العمر: ${client.user.tag}`);

    const rest = new REST({ version: '10' }).setToken(process.env.DISCORD_TOKEN);
    try {
        console.log('جاري تسجيل أوامر السلاش (/ask)...');
        await rest.put(
            Routes.applicationCommands(client.user.id),
            { body: commands },
        );
        console.log('تم تسجيل أمر /ask بنجاح للجميع!');
    } catch (error) {
        console.error('خطأ في تسجيل الأوامر:', error);
    }
});

// استقبال واستجابة لأمر /ask
client.on('interactionCreate', async interaction => {
    if (!interaction.isChatInputCommand()) return;

    if (interaction.commandName === 'ask') {
        const userQuery = interaction.options.getString('question');

        await interaction.deferReply();

        try {
            const response = await ai.models.generateContent({
                model: 'gemini-2.5-flash',
                contents: [
                    { role: 'user', parts: [{ text: `${systemPrompt}\n\nالسؤال الموجه لك الآن: ${userQuery}` }] }
                ]
            });

            const botReply = response.text || 'معليش، المخ عندي فصل لحظة.. عد السؤال.';
            await interaction.editReply(botReply);

        } catch (error) {
            console.error('خطأ في المعالجة:', error);
            await interaction.editReply('يا ساتر، السيرفر ضرب عندي والذكاء حقنا راح فيها.. جرب بعد شوي.');
        }
    }
});

client.login(process.env.DISCORD_TOKEN);
