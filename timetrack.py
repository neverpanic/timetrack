#!/usr/bin/env python3.4

from datetime import datetime

import argparse
import os
import sqlite3
import sys

ACT_ARRIVE = 'arrive'
ACT_BREAK  = 'break'
ACT_RESUME = 'resume'
ACT_LEAVE  = 'leave'

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
						   type == ?
						OR type == ?
						OR type == ?
						OR type == ?)
					, ts TIMESTAMP NOT NULL
					, PRIMARY KEY (type, ts)
				)
			""", (ACT_ARRIVE, ACT_BREAK, ACT_RESUME, ACT_LEAVE))
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
	if lastType is not None && lastType != ACT_LEAVE:
		error(randomMessage(ERR_HAVE_NOT_LEFT))

	arrivalTime = datetime.now()
	addEntry(con, ACT_ARRIVE, arrivalTime)
	message(randomMessage(SUCCESS_ARRIVAL, arrivalTime))

def suspendTracking(con):
	"""
	Suspend tracking for today: Records the start of your break time. There can
	be an infinite number of breaks per day.
	"""

	# Make sure you're currently working; can't suspend if you weren't even working
	lastType = getLastType(con)
	lastTime = getLastTime(con)
	if lastType not in [ACT_ARRIVE, ACT_RESUME]:
		error(randomMessage(ERR_NOT_WORKING, lastType))

	breakTime = datetime.now()
	addEntry(con, ACT_BREAK, breakTime)
	message(randomMessage(SUCCESS_BREAK, breakTime, lastTime))

def resumeTracking(con):
	"""
	Resume tracking after a break. Records the end time of your break. There
	can be an infinite number of breaks per day.
	"""

	# Make sure you're currently taking a break; can't resume if you were not taking a break
	lastType = getLastType(con)
	lastTime = getLastTime(con)
	if lastType != ACT_BREAK:
		error(randomMessage(ERR_NOT_BREAKING, lastType))

	resumeTime = datetime.now()
	addEntry(con, ACT_RESUME, resumeTime)
	message(randomMessage(SUCCESS_RESUME, resumeTime, lastTime))

def endTracking(con):
	"""
	End tracking for the day. Records the time of your leave.
	"""
	# Make sure you've actually been at work. Can't leave if you're not even here!
	lastType = getLastType(con)
	if lastType not in [ACT_ARRIVE, ACT_RESUME]:
		error(randomMessage(ERR_NOT_WORKING, lastType)

	leaveTime = datetime.now()
	addEntry(con, ACT_LEAVE, leaveTime)
	message(randomMessage(SUCCESS_LEAVE, leaveTime))

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
