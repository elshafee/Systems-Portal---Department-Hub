"""
services/ai_generator.py

Calls LM Studio local API (OpenAI-compatible) to generate/reformat
formal Arabic office text (letters and requests).
"""

import requests
import json

LM_STUDIO_URL  = "http://host.docker.internal:1234/v1/chat/completions"
DEFAULT_MODEL  = "openai/gpt-oss-20b"   # fallback if not specified


# ── Prompts ────────────────────────────────────────────────────────────────────

LETTER_SYSTEM = """أنت محرر مراسلات رسمية محترف متخصص في صياغة الخطابات الإدارية باللغة العربية الفصحى الرسمية.
مهمتك: إعادة صياغة وتحرير النص المقدم إليك ليكون خطاباً رسمياً متكاملاً ومضبوطاً.

القواعد الصارمة:
- استخدم اللغة العربية الفصحى الرسمية فقط
- الأسلوب: رسمي، مهذب، محترم، دبلوماسي
- لا تضف أي نص خارج الخطاب نفسه
- لا تضف تعليقات أو ملاحظات أو عناوين
- أعد فقط نص الخطاب الرسمي المنسق
- حافظ على جميع المعلومات التقنية والأسماء والعناوين الإلكترونية كما هي"""

REQUEST_SYSTEM = """أنت محرر مراسلات رسمية محترف متخصص في صياغة المذكرات والطلبات الإدارية باللغة العربية الفصحى الرسمية.
مهمتك: إعادة صياغة وتحرير النص المقدم إليك ليكون طلباً رسمياً متكاملاً ومضبوطاً.

القواعد الصارمة:
- استخدم اللغة العربية الفصحى الرسمية فقط
- الأسلوب: رسمي، واضح، مباشر، مهذب
- لا تضف أي نص خارج الطلب نفسه
- لا تضف تعليقات أو ملاحظات أو عناوين
- أعد فقط نص الطلب الرسمي المنسق
- حافظ على جميع المعلومات التقنية والأسماء والعناوين الإلكترونية كما هي"""


def get_available_models() -> list:
    """Fetch list of loaded models from LM Studio."""
    try:
        resp = requests.get(
            LM_STUDIO_URL.replace("/v1/chat/completions", "/v1/models"),
            timeout=5
        )
        if resp.status_code == 200:
            data = resp.json()
            return [m["id"] for m in data.get("data", [])]
    except Exception:
        pass
    return []


def generate_arabic_text(
    doc_type: str,
    sender: str,
    recipient: str,
    subject: str,
    raw_draft: str,
    model: str = DEFAULT_MODEL,
) -> dict:
    """
    Send draft to LM Studio and receive formal Arabic body text.

    Returns:
        {"success": True,  "text": "...", "model": "..."}
        {"success": False, "error": "...", "model": "..."}
    """
    type_label = "خطاب رسمي" if doc_type == "letter" else "طلب رسمي"
    system_prompt = LETTER_SYSTEM if doc_type == "letter" else REQUEST_SYSTEM

    user_message = f"""قم بصياغة {type_label} رسمي بناءً على المعلومات التالية:

المرسل: {sender}
المرسل إليه: {recipient}
الموضوع: {subject}

المسودة / الفكرة الرئيسية:
{raw_draft}

أعد فقط نص جسم {type_label} (بدون السطر الافتتاحي للمرسل والمرسل إليه والموضوع — هذه ستُضاف تلقائياً).
ابدأ مباشرةً بـ "عناية السيد..." أو ما يناسب."""

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_message},
        ],
        "temperature": 0.4,
        "max_tokens": 1024,
        "stream": False,
    }

    try:
        resp = requests.post(LM_STUDIO_URL, json=payload, timeout=120)
        resp.raise_for_status()
        data = resp.json()
        text = data["choices"][0]["message"]["content"].strip()
        return {"success": True, "text": text, "model": model}
    except requests.exceptions.ConnectionError:
        return {
            "success": False,
            "error": "لا يمكن الاتصال بـ LM Studio. تأكد من أن البرنامج يعمل على المنفذ 1234.",
            "model": model,
        }
    except requests.exceptions.Timeout:
        return {
            "success": False,
            "error": "انتهت مهلة الاتصال بـ LM Studio. النموذج قد يكون بطيئاً، حاول مرة أخرى.",
            "model": model,
        }
    except Exception as e:
        return {"success": False, "error": str(e), "model": model}


def build_full_document_text(
    doc_type: str,
    sender: str,
    recipient: str,
    subject: str,
    generated_body: str,
    signatory: str = "مدير مركز الخدمات الإلكترونية – كلية الهندسة\nالأستاذ(م) الدكتور/ محمد كمال عبد السلام",
) -> str:
    """
    Assembles the complete formal document text that goes into {{BODY_TEXT}}.
    """
    lines = [
        f"الراســــــــل: {sender}",
        f"المرسل إليه: {recipient}",
        f"الموضـــوع: {subject}",
        "",
        "",
        generated_body,
        "",
        "",
        signatory,
    ]
    return "\n".join(lines)
