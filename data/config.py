from environs import Env

# environs kutubxonasidan foydalanish
env = Env()
env.read_env()
# .env fayl ichidan quyidagilarni o'qiymiz
BOT_TOKEN = env.str("BOT_TOKEN")  # Bot token
ADMINS = [973358587]  # Adminlar ro'yxati (int ga aylantiramiz)
IP = env.str("ip")


