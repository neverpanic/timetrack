#!/usr/bin/env python3.4

from datetime import datetime, timedelta

import argparse
import os
import sqlite3
import sys
import random

ACT_ARRIVE = 'arrive'
ACT_BREAK  = 'break'
ACT_RESUME = 'resume'
ACT_LEAVE  = 'leave'

MSG_ERR_NOT_WORKING   = 1 << 0
MSG_ERR_HAVE_NOT_LEFT = 1 << 1
MSG_ERR_NOT_BREAKING  = 1 << 2
MSG_SUCCESS_ARRIVAL   = 1 << 3
MSG_SUCCESS_BREAK     = 1 << 4
MSG_SUCCESS_RESUME    = 1 << 5
MSG_SUCCESS_LEAVE     = 1 << 6

class ProgramAbortError(Exception):
	"""
	Exception class that wraps a critical error and encapsules it for
	pretty-printing of the error message.
	"""
	def __init__(self, message, cause):
		self.message = message
		self.cause = cause
	
	def __str__(self):
		if self.cause is not None:
			return "Error: {}\n       {}".format(self.message, self.cause)
		else:
			return "Error: {}".format(self.message)

def message(msg):
	"""
	Print an informational message
	"""
	print(msg)

def warning(msg):
	"""
	Print a warning message
	"""
	print("Warning: {}".format(msg), file=sys.stderr)

def error(msg, ex):
	"""
	Print an error message and abort execution
	"""
	raise ProgramAbortError(msg, ex)

def randomMessage(type, *args):
	messageList = []

	if type == MSG_SUCCESS_ARRIVAL:
		if len(args) > 0:
			arrivalTime = args[0]
			if arrivalTime.hour <= 7:
				messageList.append("The early bird catches the worm. Welcome and have a nice day!")
			elif arrivalTime.hour <= 9:
				messageList.append("Good morning.")
			elif arrivalTime.hour >= 10:
				messageList.append("Coming in late today? Have fun working anyway.")

			if arrivalTime.weekday() == 0: # Monday
				messageList.append("Have a nice start into the fresh week!")
				messageList.append("New week, new luck!")
			elif arrivalTime.weekday() == 4: # Friday
				messageList.append("Last day of the week! Almost done! Keep on going!")
				messageList.append("Just a couple more hours until weekend. Have fun!")
			elif arrivalTime.weekday() == 5: # Saturday
				messageList.append("Oh, so they made you work on Saturday? I'm sorry :/")
				messageList.append("Saturday, meh. Hang in there, it'll be over soon.")

		messageList.append("Welcome and have a nice day!")

	elif type == MSG_SUCCESS_BREAK:
		breakTime = None
		workStartTime = None
		if len(args) > 0:
			breakTime = args[0]
		if len(args) > 1:
			workStartTime = args[0]

		if breakTime is not None and workStartTime is not None:
			duration = breakTime - workStartTime
			durationHours = duration.total_seconds() // 3600
			durationMinutes = (duration.total_seconds() - (durationHours * 3600)) // 60
			msgText = ""
			if durationHours > 1:
				msgText += "{} hours".format(durationHours)
			elif durationHours == 1:
				msgText += "{} hour".format(durationHours)

			if durationHours > 0 and durationMinutes > 2: # avoid 1 hour 2 minutes
				msgText += " and "

			if durationHours == 0 or durationMinutes > 2:
				if durationMinutes > 1:
					msgText += "{} minutes".format(durationMinutes)
				else:
					msgText += "{} minutes".format(durationMinutes)

			msgText += " of work."

			if duration.total_seconds() >= 4 * 60 * 60: # more than 4h, time for a break
				msgText += " Time for a well-deserved break."
			else:
				msgText += " I guess a coffee break wouldn't hurt, would it?"

			messageList.append(msgText)

		if breakTime is not None:
			if breakTime.hour >= 11 and breakTime.hour <= 13:
				messageList.append("{:%H:%M}. A good time for lunch.".format(breakTime))
			if breakTime.hour < 11:
				messageList.append("{0.hour} o'clock. Breakfast time!".format(breakTime))
			if breakTime.hour > 13:
				messageList.append("Coffee?")
				messageList.append("Good idea, take a break and relax a little.")

		messageList.append("Enjoy your break!")
		messageList.append("Relax a little and all your problems will have gotten simpler once you're back :-)")
		messageList.append("Bye bye!")

	return random.choice(messageList)

def dbSetup():
	"""
	Create a new SQLite database in the user's home, creating and initializing
	the database if it doesn't exist. Returns an sqlite3 connection object.
	"""
	con = sqlite3.connect(os.path.expanduser("~/.timetrack.db"), detect_types = sqlite3.PARSE_DECLTYPES)
	con.row_factory = sqlite3.Row

	dbVersion = con.execute("PRAGMA user_version").fetchone()['user_version']
	if dbVersion == 0:
		# database is uninitialized, create the tables we need
		con.execute("BEGIN EXCLUSIVE")
		con.execute("""
				CREATE TABLE times (
					  type TEXT NOT NULL CHECK (
						   type == "{}"
						OR type == "{}"
						OR type == "{}"
						OR type == "{}")
					, ts TIMESTAMP NOT NULL
					, PRIMARY KEY (type, ts)
				)
			""".format(ACT_ARRIVE, ACT_BREAK, ACT_RESUME, ACT_LEAVE))
		con.execute("PRAGMA user_version = 1")
		con.commit()
	# database upgrade code would go here

	return con

def addEntry(con, type, ts):
	con.execute("INSERT INTO times (type, ts) VALUES (?, ?)", (type, ts))
	con.commit()

def getLastType(con):
	cur = con.execute("SELECT type FROM times ORDER BY ts DESC LIMIT 1")
	row = cur.fetchone()
	if row is None:
		return None
	return row['type']

def getLastTime(con):
	cur = con.execute("SELECT ts FROM times ORDER BY ts DESC LIMIT 1")
	row = cur.fetchone()
	if row is None:
		return None
	return row['ts']

def startTracking(con):
	"""
	Start your day: Records your arrival time in the morning.
	"""
	# Make sure you're not already at work.
	lastType = getLastType(con)
	if lastType is not None and lastType != ACT_LEAVE:
		error(randomMessage(MSG_ERR_HAVE_NOT_LEFT))

	arrivalTime = datetime.now()
	addEntry(con, ACT_ARRIVE, arrivalTime)
	message(randomMessage(MSG_SUCCESS_ARRIVAL, arrivalTime))

def suspendTracking(con):
	"""
	Suspend tracking for today: Records the start of your break time. There can
	be an infinite number of breaks per day.
	"""

	# Make sure you're currently working; can't suspend if you weren't even working
	lastType = getLastType(con)
	lastTime = getLastTime(con)
	if lastType not in [ACT_ARRIVE, ACT_RESUME]:
		error(randomMessage(MSG_ERR_NOT_WORKING, lastType))

	breakTime = datetime.now()
	addEntry(con, ACT_BREAK, breakTime)
	message(randomMessage(MSG_SUCCESS_BREAK, breakTime, lastTime))

def resumeTracking(con):
	"""
	Resume tracking after a break. Records the end time of your break. There
	can be an infinite number of breaks per day.
	"""

	# Make sure you're currently taking a break; can't resume if you were not taking a break
	lastType = getLastType(con)
	lastTime = getLastTime(con)
	if lastType != ACT_BREAK:
		error(randomMessage(MSG_ERR_NOT_BREAKING, lastType))

	resumeTime = datetime.now()
	addEntry(con, ACT_RESUME, resumeTime)
	message(randomMessage(MSG_SUCCESS_RESUME, resumeTime, lastTime))

def endTracking(con):
	"""
	End tracking for the day. Records the time of your leave.
	"""
	# Make sure you've actually been at work. Can't leave if you're not even here!
	lastType = getLastType(con)
	if lastType not in [ACT_ARRIVE, ACT_RESUME]:
		error(randomMessage(MSG_ERR_NOT_WORKING, lastType))

	leaveTime = datetime.now()
	addEntry(con, ACT_LEAVE, leaveTime)
	message(randomMessage(MSG_SUCCESS_LEAVE, leaveTime))

def dayStatistics(con):
	pass

def weekStatistics(con):
	pass

parser = argparse.ArgumentParser(description='Track your work time')
parser.add_argument('action', help="Select the mode of operation. Possible \
	values are 'morning' to start tracking, 'break' to suspend, 'resume' or \
	'continue' to resume tracking, 'closing' to end tracking for the day. Daily \
	and weekly progress can be obtained using 'day' and 'week', respectively.")
args = parser.parse_args()

actions = {
	'morning':  startTracking,
	'break':    suspendTracking,
	'resume':   resumeTracking,
	'continue': resumeTracking,
	'day':      dayStatistics,
	'week':     weekStatistics,
	'closing':  endTracking
}

if args.action not in actions:
	print('Unsupported action "{}". Use --help to get usage information.'.format(args.action), file=sys.stderr)
	sys.exit(1)

try:
	connection = dbSetup()

	actions[args.action](connection)
	sys.exit(0)
except ProgramAbortError as e:
	print(str(e), file=sys.stderr)
	sys.exit(1)
except KeyboardInterrupt as e:
	print()
	sys.exit(255)
