"""安全工具：密码哈希 + JWT token 生成与验证"""
from datetime import datetime, timedelta
from typing import Optional

from jose import jwt, JWTError
from passlib.context import CryptContext

from app.core.config import settings

# 密码哈希上下文：使用 bcrypt 算法
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """把明文密码哈希成密文（存数据库用这个）"""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证明文密码是否和哈希值匹配"""
    return pwd_context.verify(plain_password, hashed_password)


def normalize_answer(answer: str) -> str:
    """统一密保答案格式：去掉首尾空格并转小写。

    用户答题时大小写、空格习惯不一致，统一归一化后再哈希/比对，
    避免"正确答案却校验不通过"。
    """
    return answer.strip().lower()


def create_access_token(subject: str, expires_minutes: Optional[int] = None) -> str:
    """生成 JWT access token。

    subject 通常放用户 id（字符串形式）。
    """
    expire = datetime.utcnow() + timedelta(
        minutes=expires_minutes or settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    payload = {"sub": subject, "exp": expire}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)



def decode_access_token(token: str) -> Optional[str]:
    """解析 JWT，返回 subject（用户 id）。失败返回 None。"""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload.get("sub")
    except JWTError:
        return None
