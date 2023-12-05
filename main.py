#!/usr/bin/env python3
import logging
from pprint import pprint
from functools import wraps
from typing import Optional, Union
from phabricator import Phabricator
from telegram import (
    Message,
    Update,
    ForceReply,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from telegram.ext import (
    Application,
    ApplicationBuilder,
    Updater,
    CommandHandler,
    CallbackContext,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)
from telegram.constants import ParseMode

import json
import config
import random
import string
import re


def create_task(title: str, description: str):
    transactions = [
        {"type": "title", "value": title},
        {"type": "description", "value": description},
    ]

    phab = Phabricator(host=config.PHABRICATOR_URL_API, token=config.PHABRICATOR_TOKEN)
    result = phab.maniphest.edit(transactions=transactions)
    return result


def extract_title_and_description(
    update: Union[str, "Update"]
) -> (Optional[str], Optional[str]):
    msg_text = re.sub(
        r"^\s*\/add_task(@\w+)?\s*", "", update.message.text, flags=re.IGNORECASE
    )

    first_newline = msg_text.find("\n")

    title = ""
    description = None

    if first_newline == -1:
        title = msg_text.capitalize().strip()
    else:
        title = msg_text[:first_newline].capitalize()
        # extract the description from text_markdown separately,
        # because Phabricator supports markdown in the description, but not in the title
        msg_text_markdown = update.message.text_markdown
        first_newline = msg_text_markdown.find("\n")
        description = msg_text_markdown[first_newline:].strip()
        description += "\n\n"
    if not title:
        return None, None

    return title, description


message_ids_waiting_for_reply: dict[int, Message] = {}


def gen_id() -> str:
    return "".join(random.choice(string.ascii_lowercase) for i in range(15))


tasks_awaiting_confirmation: dict[str, dict] = {}


async def handler_add_task(update: Union[str, "Update"], context: CallbackContext):
    global message_ids_waiting_for_reply
    if update.message.chat and update.message.chat.title != config.TELEGRAM_CHAT_NAME:
        await update.message.reply_text("Niedozwolona grupa czatu!")
        return

    title, description = extract_title_and_description(update)
    print([title, description])
    if not title:
        reply_msg = await update.message.reply_text(
            "Proszę podaj tytuł (oraz opcjonalnie opis w nowej linii):",
            reply_markup=ForceReply(
                selective=True,
                input_field_placeholder="Tytuł zadania i opcjonalny opis w nowej linii",
            ),
        )
        message_ids_waiting_for_reply[reply_msg.message_id] = reply_msg
        return
    if not description:
        description = ""

    description += "*Dodane przez:* {} ".format(update.message.from_user.name)
    description += "\nlink do wiadomości: {} ".format(update.message.link)

    confirmation_id = gen_id()
    tasks_awaiting_confirmation[confirmation_id] = {
        "title": title,
        "description": description,
    }

    await update.message.reply_markdown(
        """Podgląd zadania:
*Tytuł:* {}
*Opis:*
{}

Czy chcesz dodać zadanie?""".format(
            title, description
        ),
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "✅ Dodaj zadanie",
                        # callback_data=json.dumps({
                        #     "action": "add_task",
                        #     "title": title,
                        #     "description": description,
                        # }),
                        callback_data="ok " + confirmation_id,
                    ),
                    InlineKeyboardButton(
                        "❌ Anuluj", callback_data="cancel " + confirmation_id
                    ),
                ]
            ]
        ),
    )


async def callback_query_handler(update: Update, context: CallbackContext):
    data = update.callback_query.data
    op, confirmation_id = data.split(" ", 1)
    if op == "ok":
        if confirmation_id not in tasks_awaiting_confirmation:
            return
        task = tasks_awaiting_confirmation.pop(confirmation_id)
        result = None
        try:
            result = create_task(title=task["title"], description=task["description"])
        except Exception as e:
            await update.callback_query.edit_message_text(
                "Wystąpił błąd podczas dodawania zadania: {}".format(e)
            )
            # print error and traceback
            logging.exception("Error while creating task", exc_info=e)
            return
        task_id = result.object["id"]

        url = "{}T{}".format(config.PHABRICATOR_URL, task_id)
        reply = "*T{}: {}* ({})".format(task_id, task["title"], url)

        await update.callback_query.edit_message_text(
            reply, parse_mode=ParseMode.MARKDOWN
        )
        await update.callback_query.edit_message_reply_markup(
            InlineKeyboardMarkup(
                [[InlineKeyboardButton("🔗 T{}".format(task_id), url=url)]]
            )
        )
    elif op == "cancel":
        if confirmation_id not in tasks_awaiting_confirmation:
            return
        tasks_awaiting_confirmation.pop(confirmation_id)
        await update.callback_query.edit_message_text("Anulowano dodawanie zadania")
    else:
        await update.callback_query.edit_message_text(
            "Nieznana operacja: {}".format(op)
        )


async def message_handler(update: Union[str, "Update"], context: CallbackContext):
    if (
        update.message.reply_to_message
        and update.message.reply_to_message.message_id in message_ids_waiting_for_reply
    ):
        # delete the message from the chat
        await update.message.reply_to_message.delete()
        message_ids_waiting_for_reply.pop(update.message.reply_to_message.message_id)
        await handler_add_task(update, context)
        return


def error_callback(update, context: CallbackContext):
    pprint(context.error)


async def post_init(application: Application) -> None:
    await application.bot.set_my_commands(
        [("add_task", "Dodaj zadanie do Phabricatora")]
    )


if __name__ == "__main__":
    # logging.basicConfig(level=logging.DEBUG)

    app = ApplicationBuilder().token(config.TELEGRAM_TOKEN).post_init(post_init).build()

    app.add_handler(CommandHandler("add_task", handler_add_task))
    app.add_handler(MessageHandler(filters.TEXT, message_handler, True))
    app.add_handler(CallbackQueryHandler(callback_query_handler))
    app.add_error_handler(error_callback)

    app.run_polling()
