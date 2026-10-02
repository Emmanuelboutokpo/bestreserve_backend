import redis.asyncio as aioredis
from app.config import settings

token_blacklist = aioredis.StrictRedis(
    host=settings.redis_host, 
    port=settings.redis_port, 
    db=0, 
    decode_responses=True
)

async def add_jti_to_blacklist(
    jti: str,
    expires_in: int | None = None,
):
    expiry = expires_in or settings.jti_expiration_seconds
    await token_blacklist.set(jti, "blacklisted", ex=max(1, expiry))

async def token_in_blacklist(jti: str) -> bool:
    result = await token_blacklist.exists(jti)
    return result == 1

async def save_otp(email: str, otp: str, expiry: int = 600):
    try :
        await token_blacklist.set(f"otp:{email}", otp, ex=expiry)
    except Exception:
        print(f"⚠️ Redis est éteint. OTP pour {email} : {otp} (affiché ici faute de mieux)")

async def get_otp(email: str):
    return await token_blacklist.get(f"otp:{email}")

async def delete_otp(email: str):
    await token_blacklist.delete(f"otp:{email}")

async def get_resend_cooldown(email: str):
    return await token_blacklist.get(f"otp:resend:{email}")

async def set_resend_cooldown(email: str, seconds: int = 60):
    await token_blacklist.set(f"otp:resend:{email}", "1", ex=seconds)

async def save_reset_token(email: str, token: str, expiry: int = 1800):
    await token_blacklist.set(f"reset:{token}", email, ex=expiry)

async def get_email_from_reset_token(token: str):
    return await token_blacklist.get(f"reset:{token}")

async def delete_reset_token(token: str):
    await token_blacklist.delete(f"reset:{token}")