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

	###########
	# Arrival #
	###########
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

	#########
	# Break #
	#########
	elif type == MSG_SUCCESS_BREAK:
		breakTime = None
		workStartTime = None
		if len(args) > 0:
			breakTime = args[0]
		if len(args) > 1:
			workStartTime = args[1]

		if breakTime is not None and workStartTime is not None:
			duration = breakTime - workStartTime
			durationHours = int(duration.total_seconds() // 3600)
			durationMinutes = int((duration.total_seconds() - (durationHours * 3600)) // 60)
			msgText = ""
			if durationHours > 1:
				msgText += "{:d} hours".format(durationHours)
			elif durationHours == 1:
				msgText += "{:d} hour".format(durationHours)

			if durationHours > 0 and durationMinutes > 2: # avoid 1 hour 2 minutes
				msgText += " and "

			if durationHours == 0 or durationMinutes > 2:
				if durationMinutes > 1:
					msgText += "{:02d} minutes".format(durationMinutes)
				else:
					msgText += "{:02d} minutes".format(durationMinutes)

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

	################
	# End of break #
	################
	elif type == MSG_SUCCESS_RESUME:
		resumeTime = None
		breakStartTime = None
		if len(args) > 0:
			resumeTime = args[0]
		if len(args) > 1:
			breakStartTime = args[1]

		if resumeTime is not None:
			if resumeTime.hour <= 12:
				messageList.append("With renewed vigour into the rest of the day! Welcome back.")
				messageList.append("The rest of the day right ahead, but with fresh strength.")
			elif resumeTime.hour >= 15:
				messageList.append("Just a few more hours. Hang in, closing time is near!")
				messageList.append("Almost there. Just a few more minutes.")

		if resumeTime is not None and breakStartTime is not None:
			duration = resumeTime - breakStartTime
			durationMinutes = int(duration.total_seconds() // 60)

			msgText = "{:d}".format(durationMinutes)
			if durationMinutes != 1:
				msgText += " minutes"
			else:
				msgText += " minute"
			msgText += " break. Welcome back and have fun with the rest of your day."
			messageList.append(msgText)

			if durationMinutes < 30:
				messageList.append("Quick coffee break finished? Back to work, getting things done!")
				messageList.append("That break certainly was a quick one! Welcome back!")
			elif durationMinutes >= 30 and durationMinutes < 45:
				messageList.append("Average size break, now back to work.")
			else:
				messageList.append("That was a pretty long break. You can pull off more then 9 hours today.")
				messageList.append("Pretty extensive {:d} minute break. Hope you're feeling refreshed now :)".format(durationMinutes))

		messageList.append("Welcome back at your desk. Your laptop has been missing you.")
		messageList.append("Back into work! Enjoy!")
		messageList.append("Welcome back.")

	###################
	# End of work day #
	###################
	elif type == MSG_SUCCESS_LEAVE:
		endTime = None
		if len(args) > 0:
			endTime = args[0]

		if endTime is not None:
			if endTime.hour <= 14:
				messageList.append("Going home early today? Go ahead, I'm sure you earned it.")
				messageList.append("Short work day, enjoy your afternoon.")
			elif endTime.hour > 14 and endTime.hour < 18:
				messageList.append("Have a nice evening.")
				messageList.append("Bon appetit and enjoy your evening!")
			else:
				messageList.append("Leaving late today?")
				messageList.append("Did you just stay because the job was interesting or did something have to get done today?")
				messageList.append("Finally. Have a good night's sleep!")
			if endTime.weekday() == 4: # Friday
				messageList.append("Friday! Have a nice weekend!")
				messageList.append("Finally, this week has come to an end.")
				messageList.append("Fuck this shit, it's Friday and I'm going home!")
			elif endTime.weekday() == 5: # Saturday
				messageList.append("Ugh, somebody made you come in on Saturday. Enjoy your Sunday then.")
				messageList.append("About time the week was over, isn't it?")

		messageList.append("A good time to leave. Because it's always a good time to do that. :)")
		messageList.append("You're right, go home. Tomorrow's yet another day.")

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
