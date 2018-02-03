#!/usr/bin/env python3
import logging
from pprint import pprint
from functools import wraps
from phabricator import Phabricator
from telegram import ParseMode
from telegram.ext import Updater, CommandHandler

import config

def create_task(phab, title):
	transactions = [
		{'type': 'title', 'value': title},
	]

	# @TODO support exceptions/errors/blah :P

	result = phab.maniphest.edit(transactions=transactions)
	return result


def handler_add_task(bot, update, args):
	if update.message.chat.title != config.TELEGRAM_CHAT_NAME:
		update.message.reply_text('Niedozwolona grupa czatu!')
		return

	if len(args) < 3:
		update.message.reply_text('Podaj, proszę, tytuł jako argument')
		return

	args[0] = args[0].capitalize()

	title = ' '.join(args)

	global phab

	result = create_task(phab, title=title)
	task_id = result.object['id']

	url = '{}T{}'.format(config.PHABRICATOR_URL, task_id)
	reply = '*T{}: {}* ({})'.format(task_id, title, url)

	update.message.reply_text(reply, parse_mode=ParseMode.MARKDOWN)


def error_callback(bot, update, error):
	pprint(error)


if __name__ == '__main__':
	logging.basicConfig(level=logging.DEBUG)

	phab = Phabricator(host=config.PHABRICATOR_URL_API, token=config.PHABRICATOR_TOKEN)
	telegram_updater = Updater(config.TELEGRAM_TOKEN)
	telegram_dispatcher = telegram_updater.dispatcher

	telegram_dispatcher.add_handler(CommandHandler('add_task', handler_add_task, pass_args=True))

	telegram_dispatcher.add_error_handler(error_callback)

	telegram_updater.start_polling()
	telegram_updater.idle()
