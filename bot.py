
import os
import logging
from dotenv import load_dotenv
from groq import AsyncGroq
from telegram import Update
from telegram.ext import (
    Application,
    MessageHandler,
    ContextTypes,
    filters,
)

import memory

load_dotenv()
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("bud")

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
OWNER_ID = int(os.environ["ADMIN_ID"])
OWNER_NAME = os.getenv("OWNER_NAME", "Futa")
MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")

ai = AsyncGroq(api_key=os.environ["GROQ_API_KEY"])

PERSONALITY = f"""
You are Bud, {OWNER_NAME}'s AI best friend.

TEXTING STYLE:
- Default language is English. Use Burmese if the other person prefers it.
- Text like a normal human friend, not a formal assistant.
- Usually 1 short sentence; occasionally 2. Aim for under 30 words.
- React naturally to jokes, gossip, emotions and casual messages.
- No essays, headings or lists in ordinary conversations.
- Don't give advice unless it's wanted or genuinely needed.
- Don't repeat what the person just said.
- Use casual language and emojis naturally, not constantly.

IDENTITY:
- You are Bud, an AI, not {OWNER_NAME}.
- Never pretend to be {OWNER_NAME} or claim they personally wrote a message.
- You may send replies as an AI assistant authorized to help with chats.
- Never make promises or commitments on the owner's behalf.
- Never share private memories, secrets, or credentials.

PRIVACY:
- The owner's saved memories are private.
- Do not disclose private owner information to friends.
- Never invent facts about the owner.
"""


def is_owner(update):
    user = update.effective_user
    msg = update.effective_message
    return bool(
        user and msg
        and user.id == OWNER_ID
        and msg.chat.type == "private"
        and not getattr(msg, "business_connection_id", None)
    )


def is_away():
    return memory.get_setting("away") == "1"


def auto_reply():
    return memory.get_setting("auto_reply") == "1"


async def ask_ai(chat_id, text, owner=False, extra_context=None):
    system = PERSONALITY

    if owner:
        saved = "\n".join(
            "- " + item for item in memory.get_memories()
        ) or "(No saved memories.)"

        system += "\nPrivate memories for owner-only chats:\n" + saved

    messages = [{"role": "system", "content": system}]
    messages.extend(memory.get_chat(chat_id)[-8:])

    if extra_context:
        messages.append({
            "role": "system",
            "content": extra_context,
        })

    messages.append({"role": "user", "content": text})

    result = await ai.chat.completions.create(
        model=MODEL,
        messages=messages,
        max_completion_tokens=160,
        temperature=0.8,
    )

    answer = (result.choices[0].message.content or "LOL 😭").strip()

    # Only save owner-chat history as a conversation.
    # Business messages are logged separately.
    memory.save_chat(chat_id, "user", text)
    memory.save_chat(chat_id, "assistant", answer)

    return answer


async def summarize_away():
    rows = memory.get_away_messages()

    if not rows:
        return "Welcome back bro 💙 No new messages were logged while you were away."

    lines = []
    for chat_id, sender, content, created_at in rows:
        lines.append(f"Chat {chat_id} | {sender}: {content}")

    transcript = "\n".join(lines)[-12000:]

    result = await ai.chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "Summarize these Telegram conversations for the owner. "
                    "Be concise and casual. Mention important questions, "
                    "plans, requests, urgent matters, or anything needing "
                    "a reply. Ignore trivial small talk. Do not invent facts. "
                    "If nothing important happened, say so in one sentence."
                ),
            },
            {"role": "user", "content": transcript},
        ],
        max_completion_tokens=250,
    )

    summary = (
        result.choices[0].message.content or "No important updates, bro 💙"
    ).strip()

    memory.clear_away_messages()
    return "BROOO welcome back 💙 Here's what you missed:\n" + summary


async def handle_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    msg = update.effective_message
    user = update.effective_user

    if not msg or not msg.text or not user:
        return

    text = msg.text.strip()
    lower = text.lower()
    owner = is_owner(update)

    # Control commands are sent in Bud's private bot chat.
    if owner:
        if any(p in lower for p in (
            "i'm going offline", "im going offline",
            "i am going offline", "i'm going outside",
            "im going outside", "i am going outside",
            "i'm going out", "im going out",
            "i am going out", "take my place",
            "go offline for me", "ငါ offline သွားတော့မယ်",
            "ငါ အပြင်သွားတော့မယ်",
        )):
            memory.set_setting("away", "1")
            memory.set_setting("auto_reply", "1")
            await msg.reply_text(
                "Gotchu bro 💙 Takeover ON. I'll reply in chats "
                "I’m authorized to manage and keep a summary."
            )
            return

        if any(p in lower for p in (
            "i'm back", "im back", "i am back",
            "i came back", "i'm home", "im home",
            "ငါပြန်လာပြီ", "ငါ ပြန်လာပြီ",
        )):
            memory.set_setting("away", "0")
            memory.set_setting("auto_reply", "0")
            try:
                summary = await summarize_away()
            except Exception:
                log.exception("Summary failed")
                summary = (
                    "Welcome back bro 💙 I turned takeover off, "
                    "but couldn't make the summary just now."
                )

            await msg.reply_text(summary)
            return

        if any(p in lower for p in (
            "let bud reply", "bud can reply",
            "turn on auto reply", "enable auto reply",
        )):
            memory.set_setting("auto_reply", "1")
            await msg.reply_text(
                "Auto-reply ON 💙 I'll answer messages in chats "
                "you've authorized, even while you're online."
            )
            return

        if any(p in lower for p in (
            "stop auto reply", "turn off auto reply",
            "pause bud replies", "disable auto reply",
        )):
            memory.set_setting("auto_reply", "0")
            memory.set_setting("away", "0")
            await msg.reply_text("Auto-reply OFF. You're in control, bro 💙")
            return

        if lower.startswith(("remember that ", "remember this ")):
            fact = text.split(" ", 2)[-1].strip()
            if fact:
                memory.remember(fact)
                await msg.reply_text("Got it bro 🧠💙")
                return

        # Ask Bud for a summary without turning takeover off.
        if "summarize" in lower and ("chat" in lower or "message" in lower):
            try:
                await msg.reply_text(await summarize_away())
            except Exception:
                log.exception("Summary request failed")
                await msg.reply_text("My summary brain lagged 😭 Try again.")
            return

        # Normal private chat with Bud.
        try:
            answer = await ask_ai(msg.chat_id, text, owner=True)
            await msg.reply_text(answer)
        except Exception:
            log.exception("Owner AI reply failed")
            await msg.reply_text("My brain lagged 😭 Try again in a bit.")
        return

    # Only process authorized Telegram Business messages here.
    connection_id = getattr(msg, "business_connection_id", None)
    if not connection_id:
        return

    # Never answer messages sent by the account owner.
    if user.id == OWNER_ID:
        return

    # Store received messages while away, even if replies are paused.
    if is_away():
        memory.log_away_message(
            msg.chat_id,
            user.full_name or "Friend",
            text,
        )

    if not auto_reply():
        return

    try:
        answer = await ask_ai(
            msg.chat_id,
            text,
            owner=False,
            extra_context=(
                "You are replying to a friend in the owner's "
                "authorized Telegram Business chat. Be natural, brief, "
                "and friendly. Never reveal the owner's private memories."
            ),
        )

        await context.bot.send_message(
            chat_id=msg.chat_id,
            text=answer,
            business_connection_id=connection_id,
        )

    except Exception:
        log.exception("Business reply failed")


async def post_init(app):
    memory.setup()
    log.info("Bud is ready.")


def main():
    memory.setup()

    app = (
        Application.builder()
        .token(TOKEN)
        .post_init(post_init)
        .build()
    )

    # Receives normal messages and supported Business messages.
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    )

    log.info("Starting Bud...")
    app.run_polling(
        allowed_updates=[
            "message",
            "business_connection",
            "business_message",
            "edited_business_message",
            "deleted_business_messages",
        ]
    )


if __name__ == "__main__":
    main()
