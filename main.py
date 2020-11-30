#!/usr/bin/env python3
import logging
from pprint import pprint
from functools import wraps
from phabricator import Phabricator
from telegram import ParseMode
from telegram.ext import Updater, CommandHandler

import config


def create_task(title):
	transactions = [
		{'type': 'title', 'value': title},
	]

	# @TODO support exceptions/errors/blah :P

	phab = Phabricator(host=config.PHABRICATOR_URL_API, token=config.PHABRICATOR_TOKEN)
	result = phab.maniphest.edit(transactions=transactions)
	return result


def handler_add_task(update, context):
	if update.message.chat and update.message.chat.title != config.TELEGRAM_CHAT_NAME:
		update.message.reply_text('Niedozwolona grupa czatu!')
		return

	if len(context.args) < 3:
		update.message.reply_text('Podaj, proszę, tytuł jako argument')
		return

	context.args[0] = context.args[0].capitalize()

	title = ' '.join(context.args)

	result = create_task(title=title)
	task_id = result.object['id']

	url = '{}T{}'.format(config.PHABRICATOR_URL, task_id)
	reply = '*T{}: {}* ({})'.format(task_id, title, url)

	update.message.reply_text(reply, parse_mode=ParseMode.MARKDOWN)


def error_callback(update, context):
	pprint(context.error)


if __name__ == '__main__':
	logging.basicConfig(level=logging.DEBUG)

	telegram_updater = Updater(config.TELEGRAM_TOKEN)
	telegram_dispatcher = telegram_updater.dispatcher

	telegram_dispatcher.add_handler(CommandHandler('add_task', handler_add_task, pass_args=True))

	telegram_dispatcher.add_error_handler(error_callback)

	telegram_updater.start_polling()
	telegram_updater.idle()
