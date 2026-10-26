"""
services/ai_generator.py
Multi-provider AI text generation with automatic rate-limit failover.
Provider order: Gemini → Groq → DeepSeek
"""
import os
import re
import logging

logger = logging.getLogger(__name__)

# ─── Recipient normalization ──────────────────────────────────────────────────
RECIPIENT_MAP = {
    "it department": "إدارة تقنية المعلومات",
    "it": "إدارة تقنية المعلومات",
    "hr": "إدارة الموارد البشرية",
    "hr department": "إدارة الموارد البشرية",
    "finance department": "الإدارة المالية",
    "finance": "الإدارة المالية",
    "president": "السيد الأستاذ الدكتور/ رئيس الجامعة",
    "dean": "السيد الأستاذ الدكتور/ عميد الكلية",
    "vice dean": "السيد الأستاذ الدكتور/ وكيل الكلية",
}


def normalize_recipient(recipient: str) -> str:
    key = recipient.strip().lower()
    if key in RECIPIENT_MAP:
        return RECIPIENT_MAP[key]
    return recipient


# ─── System prompts ────────────────────────────────────────────────────────────
STYLE_DESCRIPTION = """الأسلوب الرسمي المطلوب: يجب أن يكون الخطاب مباشراً، مهنياً، وموجزاً قدر الإمكان.
تجنب الديباجات الطويلة، والمقدمات، والخواتيم المبالغ فيها. ركز على نقل المعلومات والطلبات بشكل دقيق ومباشر.
ابنِ الجمل بناءً على محتوى المسودة الفعلي أدناه فقط، دون إضافة أي حشو أو تفاصيل إنشائية غير ضرورية."""

LETTER_SYSTEM = f"""أنت محرر مراسلات رسمية محترف متخصص في صياغة الخطابات الإدارية باللغة العربية الفصحى الرسمية والمباشرة.
مهمتك: إعادة صياغة وتحرير النص المقدم إليك ليكون خطاباً رسمياً، دقيقاً، ومختصراً.

{STYLE_DESCRIPTION}

قواعد الصياغة:
1. الدخول في صلب الموضوع مباشرة بعد تحية قصيرة جداً إن لزم الأمر.
2. عرض السياق والطلب بناءً على المسودة حصرياً بشكل واضح وموجز.
3. اختتام الخطاب بعبارة شكر قصيرة جداً (مثل: وتفضلوا بقبول فائق الاحترام).

القواعد الصارمة:
- لا تضف أي فقرات ترحيبية أو إنشائية طويلة. كن مباشراً.
- استخدم اللغة العربية الفصحى الرسمية الواضحة والمباشرة.
- لا تضف أي نص، تعليقات، عناوين، أو أرقام فقرات خارج جسم الخطاب نفسه.
- لا تكتب أسطر المرسل أو المرسل إليه أو الموضوع أو التوقيع.
- أعد فقط نص جسم الخطاب.
- حافظ على جميع المعلومات التقنية والأسماء والأرقام كما هي.

{{attachment_instruction}}"""

REQUEST_SYSTEM = f"""أنت محرر مراسلات رسمية محترف متخصص في صياغة المذكرات والطلبات الإدارية باللغة العربية الفصحى الرسمية والمباشرة.
مهمتك: إعادة صياغة وتحرير النص المقدم إليك ليكون طلباً رسمياً، دقيقاً، ومختصراً.

{STYLE_DESCRIPTION}

قواعد الصياغة:
1. الدخول في صلب الموضوع مباشرة.
2. عرض المبررات والطلب بشكل واضح، مباشر، وموجز.
3. اختتام الطلب بعبارة شكر قصيرة جداً.

القواعد الصارمة:
- لا تضف أي فقرات ترحيبية أو إنشائية طويلة.
- استخدم اللغة العربية الفصحى الرسمية الواضحة والمباشرة.
- لا تضف أي نص، تعليقات، عناوين، أو أرقام فقرات.
- لا تكتب أسطر المرسل أو المرسل إليه أو التوقيع.
- أعد فقط نص جسم الطلب.
- حافظ على جميع الأرقام والأسماء كما هي تماماً.

{{attachment_instruction}}"""

EXTRACTION_SYSTEM = """أنت مساعد ذكي متخصص في تحليل المراسلات الرسمية والخطابات الإدارية باللغة العربية.
مهمتك: قراءة النص المستخرج من المستند المرفق واستخراج الحقول التالية منه بدقة تامة:

1. recipient (المرسل إليه / الجهة أو القسم): 
   - مثال: "مكتب السيد الأستاذ الدكتور / رئيس الجامعة" أو "كلية الهندسة".
   - استخرج اسم الجهة كاملاً كما هو مكتوب في الخطاب (مثلاً إذا كان مكتوباً "مكتب نائب رئيس الجامعة" اكتبها كاملة).
   - إذا كان الخطاب موجهاً لشخص بصفته، يمكن أن يكون الـ recipient هو الإدارة أو المكتب التابع له.

2. holder_name (اسم الشخص الموجه إليه الخطاب):
   - مثال: "السيد الأستاذ الدكتور / محمد عبدالعال الموقر" أو "أ.د/ فلان".
   - هذا الحقل مخصص للاسم الشخصي والألقاب التي تسبقه.

3. position (المنصب / صفة الشخص الموجه إليه الخطاب):
   - مثال: "نائب رئيس الجامعة لشئون التعليم والطلاب" أو "عميد الكلية".
   - هذا الحقل مخصص للمسمى الوظيفي للشخص الموجه إليه الخطاب.

4. subject (الموضوع):
   - موضوع الخطاب. قد يبدأ بكلمة "الموضوع:" أو "بشأن:"، ولكن إذا لم توجد هذه الكلمات، فابحث عن الجملة القصيرة التلخيصية التي تأتي عادة قبل بداية نص الخطاب (مثل "طلب الموافقة على..." أو "بخصوص..."). 
   - استنتج الموضوع من سياق الخطاب إذا لم يكن مكتوباً بشكل صريح! يجب ألا يكون فارغاً أبداً.

5. sender (المرسل):
   - المسمى الوظيفي الأساسي للمرسل (مثلاً: "مدير مركز الخدمات الإلكترونية والإبداع العلمي (ESSIC)").
   - لا تضمن الأسماء الشخصية.

6. full_body (نص الخطاب الرئيسي):
   - النص الرئيسي فقط، بدون الترويسة وبدون التوقيعات.

قواعد صارمة:
- أعد الناتج بتنسيق JSON فقط.
- المفاتيح يجب أن تكون: "sender", "recipient", "subject", "holder_name", "position", "full_body".

مثال للإخراج المطلوب:
```json
{
  "recipient": "مكتب السيد الأستاذ الدكتور / رئيس الجامعة",
  "holder_name": "السيد الأستاذ الدكتور / السعيد عبدالهادي الموقر",
  "position": "رئيس الجامعة",
  "subject": "طلب الموافقة على تجديد ترخيص البرامج",
  "sender": "مدير مركز الخدمات الإلكترونية",
  "full_body": "نتشرف بعرض الآتي على سيادتكم..."
}
```
"""


# ─── Text cleanup ─────────────────────────────────────────────────────────────
_GLITCH_SCRIPT_RE = re.compile(r'[\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]')
_GLUED_LATIN_RE = re.compile(r'(?<=[\u0600-\u06FF])[a-zA-Z]{1,6}(?=[\u0600-\u06FF])')
# Real abbreviations that legitimately appear embedded in Arabic sentences —
# never strip these even though they match the glitch-cleanup pattern above.
import os
_KNOWN_ABBREVIATIONS = set(os.environ.get("SYSTEM_KNOWN_ABBRS", "ESSIC,HUE,IT,HR").split(","))


def _clean_output(text: str) -> str:
    text = _GLITCH_SCRIPT_RE.sub('', text)

    def _strip_unless_known(m: 're.Match') -> str:
        return m.group(0) if m.group(0).upper() in _KNOWN_ABBREVIATIONS else ''

    text = _GLUED_LATIN_RE.sub(_strip_unless_known, text)
    # Extract from <text>...</text> tags if present
    match = re.search(r'<text>(.*?)</text>', text, re.DOTALL)
    if match:
        text = match.group(1).strip()
    text = re.sub(r'\n{3,}', '\n\n', text).strip()
    return text


# ─── API Key helpers ──────────────────────────────────────────────────────────
DEFAULT_FERNET_KEY = b"L0E_NAQjJiC0Pqc-8R_zODA2hsHIjTJlZq26eOqLk4M="

def _get_fernet():
    """Return a Fernet cipher for encrypting/decrypting API keys."""
    from cryptography.fernet import Fernet
    key = os.environ.get("FERNET_KEY")
    if not key:
        try:
            from dotenv import load_dotenv
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            load_dotenv(os.path.join(base_dir, "core_app", ".env"))
            key = os.environ.get("FERNET_KEY")
        except Exception:
            pass
    if not key:
        key = DEFAULT_FERNET_KEY
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt_api_key(raw_key: str) -> str:
    """Encrypt a plaintext API key for storage in the DB."""
    if not raw_key or not raw_key.strip():
        return ""
    return _get_fernet().encrypt(raw_key.strip().encode()).decode()


def decrypt_api_key(encrypted: str) -> str:
    """Decrypt a stored API key. Returns empty string on failure."""
    if not encrypted:
        return ""
    try:
        return _get_fernet().decrypt(encrypted.encode()).decode()
    except Exception:
        return ""


def get_user_keys(user_email: str) -> dict:
    """Load and decrypt API keys for the given user from the DB."""
    try:
        from models import User
        user = User.query.filter_by(email=user_email).first()
        if not user:
            return {}
        return {
            "gemini": decrypt_api_key(user.gemini_api_key or ""),
            "groq": decrypt_api_key(user.groq_api_key or ""),
            "deepseek": decrypt_api_key(user.deepseek_api_key or ""),
        }
    except Exception:
        return {}


# ─── Provider callers ─────────────────────────────────────────────────────────
def _call_gemini(api_key: str, system: str, user_msg: str) -> str:
    import google.generativeai as genai
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(
        model_name="gemini-3.5-flash",
        system_instruction=system,
    )
    response = model.generate_content(user_msg)
    return response.text


def _call_groq(api_key: str, system: str, user_msg: str) -> str:
    from groq import Groq
    client = Groq(api_key=api_key)
    resp = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_msg},
        ],
        max_tokens=2048,
        temperature=0.4,
    )
    return resp.choices[0].message.content


def _call_deepseek(api_key: str, system: str, user_msg: str) -> str:
    from openai import OpenAI
    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
    resp = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_msg},
        ],
        max_tokens=2048,
        temperature=0.4,
    )
    return resp.choices[0].message.content


def _is_rate_limit_error(e: Exception) -> bool:
    """Check if an exception is a rate-limit / quota error."""
    err_str = str(e).lower()
    return any(kw in err_str for kw in [
        "rate limit", "ratelimit", "429", "quota", "resource_exhausted",
        "too many requests", "ratelimitexceeded", "tokens per"
    ])


# ─── Main generation function ─────────────────────────────────────────────────
def get_system_prompt(doc_type: str, num_tables: int = 0, num_images: int = 0) -> str:
    attachment_instruction = ""
    if num_tables > 0 or num_images > 0:
        parts = []
        if num_tables > 0:
            parts.append(f"{num_tables} جداول")
        if num_images > 0:
            parts.append(f"{num_images} صور")
        
        tags = []
        for i in range(1, num_tables + 1):
            tags.append(f"{{{{TABLE_{i}}}}}")
        for i in range(1, num_images + 1):
            tags.append(f"{{{{IMAGE_{i}}}}}")
            
        attachment_instruction = f"ملاحظة هامة: المستخدم قام بإرفاق {' و'.join(parts)}. يجب عليك وضع العلامات التالية ({', '.join(tags)}) في الأماكن المناسبة داخل النص المُصاغ ليتم إدراج الجداول والصور مكانها تلقائياً."

    if doc_type == "letter":
        return LETTER_SYSTEM.format(attachment_instruction=attachment_instruction)
    return REQUEST_SYSTEM.format(attachment_instruction=attachment_instruction)


def generate_arabic_text(
    doc_type: str,
    sender: str,
    recipient: str,
    subject: str,
    raw_draft: str,
    user_email: str = "",
    num_tables: int = 0,
    num_images: int = 0,
) -> dict:
    """
    Generate formal Arabic letter/request body text using cloud AI providers.
    Tries Gemini → Groq → DeepSeek, failing over on rate-limit errors.
    """
    system_prompt = get_system_prompt(doc_type, num_tables, num_images)
    type_label = "خطاب رسمي" if doc_type == "letter" else "طلب رسمي"
    recipient_ar = normalize_recipient(recipient)

    user_message = f"""قم بصياغة {type_label} رسمي بناءً على المعلومات التالية:

المرسل: {sender}
المرسل إليه: {recipient_ar}
الموضوع: {subject}

المسودة / الفكرة الرئيسية:
{raw_draft}

اكتب {type_label} بشكل مباشر ومختصر وفقاً للتعليمات.
تذكر وضع النص النهائي بين <text> و </text> ولا تكتب أي كلمة أخرى خارجها."""

    # Load user API keys
    keys = get_user_keys(user_email) if user_email else {}

    PROVIDERS = [
        ("Gemini",   keys.get("gemini", ""),   _call_gemini),
        ("Groq",     keys.get("groq", ""),     _call_groq),
        ("DeepSeek", keys.get("deepseek", ""), _call_deepseek),
    ]

    last_error = None
    tried = []

    for name, api_key, caller in PROVIDERS:
        if not api_key:
            logger.info(f"Skipping {name}: no API key configured.")
            continue
        try:
            logger.info(f"Trying provider: {name}")
            raw = caller(api_key, system_prompt, user_message)
            text = _clean_output(raw)
            return {"success": True, "text": text, "model": name}
        except Exception as e:
            tried.append(name)
            if _is_rate_limit_error(e):
                logger.warning(f"{name} rate limited, failing over. Error: {e}")
                last_error = f"{name} rate limited"
                continue
            else:
                logger.error(f"{name} failed with non-rate-limit error: {e}")
                last_error = str(e)
                continue

    # All providers failed or had no keys
    if not tried:
        return {
            "success": False,
            "error": "لم يتم تكوين أي مفاتيح API. يرجى إضافة مفتاح API في صفحة الإعدادات.",
        }
    return {
        "success": False,
        "error": f"فشل الاتصال بجميع مزودي الذكاء الاصطناعي. آخر خطأ: {last_error}",
    }


def extract_document_fields(raw_text: str, user_email: str = "") -> dict:
    """
    Extract specific fields from a raw document text using cloud AI providers.
    Tries Gemini → Groq → DeepSeek, failing over on rate-limit errors.
    Returns a dictionary of extracted fields, or None if failed.
    """
    import json
    import re
    
    user_message = f"""استخرج الحقول المطلوبة من النص التالي وأعدها كـ JSON فقط بدون أي إضافات:
    
{raw_text}"""

    keys = get_user_keys(user_email) if user_email else {}

    PROVIDERS = [
        ("Gemini",   keys.get("gemini", ""),   _call_gemini),
        ("Groq",     keys.get("groq", ""),     _call_groq),
        ("DeepSeek", keys.get("deepseek", ""), _call_deepseek),
    ]

    for name, api_key, caller in PROVIDERS:
        if not api_key:
            continue
        def get_extraction_system():
            import os
            org_name = os.environ.get("SYSTEM_ORG_NAME", "مدير مركز الخدمات الإلكترونية")
            org_example = os.environ.get("SYSTEM_ORG_EXAMPLE", "كلية الهندسة")
            return EXTRACTION_SYSTEM.replace("مدير مركز الخدمات الإلكترونية", org_name).replace("كلية الهندسة", org_example)

        try:
            logger.info(f"Trying provider for extraction: {name}")
            raw = caller(api_key, get_extraction_system(), user_message)
            
            text = raw.strip()
            if text.startswith("```json"):
                text = text[7:]
            if text.startswith("```"):
                text = text[3:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()
            
            match = re.search(r'\{.*\}', text, re.DOTALL)
            if match:
                text = match.group(0)
                
            parsed = json.loads(text)
            
            expected_keys = ["sender", "recipient", "subject", "holder_name", "position", "full_body"]
            result = {}
            for k in expected_keys:
                result[k] = parsed.get(k, "")
            
            return result
        except Exception as e:
            logger.warning(f"Extraction failed with {name}: {e}")
            continue

    return None


def get_available_models() -> list:
    return ["Gemini 3.5 Flash", "Groq LLaMA-3.3-70B", "DeepSeek Chat"]


def build_full_document_text(generated_body: str) -> str:
    text = generated_body.strip()
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text
FORMAT_SYSTEM = """أنت محرر مراسلات رسمية ذكي.
مهمتك: تنسيق وضبط النص الإداري المقدم إليك ليكون جاهزاً للطباعة والاعتماد.
سيتم تزويدك بالنص الأساسي للخطاب، ومعلومات حول وجود "مرفقات" (جداول أو صور) سيتم إدراجها.

القواعد:
1. حافظ على محتوى النص والمعنى بالكامل ولكن أعد تنسيق الفقرات لتكون أكثر احترافية.
2. إذا تم إخبارك بوجود "جدول"، يجب عليك إدراج العلامة {{TABLE_1}} في المكان الأنسب داخل النص (عادةً بعد مقدمة تشير إلى بيانات أو إحصائيات، أو في منتصف الخطاب).
3. إذا تم إخبارك بوجود "صور"، يجب عليك إدراج العلامة {{IMAGE_1}} في المكان الأنسب داخل النص (عادةً بعد الإشارة لمرفق مصور، أو في نهاية النص قبل الختام).
4. أعد فقط النص المنسق بالكامل، جاهزاً للنسخ، دون أي تعليقات خارجية. لا تضف التوقيعات أو ترويسة الخطاب.
"""

def format_document_with_ai(full_body: str, has_table: bool, has_images: bool, user_email: str) -> dict:
    import json
    
    keys = get_user_keys(user_email) if user_email else {}
    
    providers = [
        ("Gemini 3.5 Flash", _call_gemini, keys.get("gemini")),
        ("Groq LLaMA-3.3-70B", _call_groq, keys.get("groq")),
        ("DeepSeek Chat", _call_deepseek, keys.get("deepseek"))
    ]
    
    attachments_info = []
    if has_table:
        attachments_info.append("ملاحظة: المستخدم سيقوم بإرفاق (جدول). الرجاء إدراج {{TABLE_1}} في المكان المناسب.")
    if has_images:
        attachments_info.append("ملاحظة: المستخدم سيقوم بإرفاق (صور). الرجاء إدراج {{IMAGE_1}} في المكان المناسب.")
        
    user_message = "النص المراد تنسيقه:\n" + full_body
    if attachments_info:
        user_message += "\n\n" + "\n".join(attachments_info)

    for name, caller, api_key in providers:
        if not api_key:
            continue
        try:
            logger.info(f"Trying provider for formatting: {name}")
            raw = caller(api_key, FORMAT_SYSTEM, user_message)
            return {"success": True, "text": _clean_output(raw), "model": name}
        except Exception as e:
            logger.warning(f"Formatting failed with {name}: {e}")
            continue

    return {"success": False, "error": "All configured AI providers failed or no API keys are set."}
