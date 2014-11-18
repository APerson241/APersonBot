"A Python script to notify a bunch of people about their DYK nominations."

import getpass
import json
import sys

# pylint: disable=import-error
from wikitools.wiki import Wiki
# pylint: disable=import-error
from wikitools.page import Page

wiki = Wiki("http://en.wikipedia.org/w/api.php")
people_to_notify = dict()

# CONFIGURATION
SUMMARY = "[[Wikipedia:Bots/Requests for approval/APersonBot " +\
		"2|Robot]] notification about the DYK nomination of" +\
		" %(nom_name)s."
CONFIRM = raw_input("Confirm before each edit (y/n)? ") == "y"

###################
# LOGIN
###################
while True:
    username = raw_input("Username: ")
    password = getpass.getpass()
    wiki.login(username, password)
    if wiki.isLoggedIn():
        break
    print "Error logging in. Try again."
print "Successfully logged in as " + wiki.username + "."

###################
# GET PEOPLE TO NOTIFY
###################
while True:
    user_input = raw_input("JSON: ")
    try:
        data = json.loads(user_input)
        keys = data.keys()
        people_to_notify = data
        break
    except ValueError as ex:
        print "ValueError: " + str(ex)
        print "ERROR parsing JSON. Try again."
    except AttributeError as ex:
        print "AttributeError: " + str(ex)
        print "ERROR parsing JSON. Try again."

print "Loaded " + str(len(data.keys())) + " people. Cool!"

prompt = "How many people have I notified so far (0's okay)? "
people_notified_count = int(raw_input(prompt))

###################
# NOTIFY PEOPLE
###################
for person in people_to_notify.keys():
    nom_name = people_to_notify[person]
    template = "\n\n{{subst:DYKNom|" +\
               nom_name[34:] + "|passive=yes}}"
    print "ABOUT TO NOTIFY " + str(person) + " BECAUSE OF " +\
          nom_name + "..."
    if CONFIRM and raw_input("Continue (y/n)? ") == "n":
        print "Exiting loop..."
        sys.exit(0)
    talkpage = Page(wiki, title="User talk:" + person)
    # cross fingers here
    result = talkpage.edit(appendtext=template, bot=True,\
                            summary=SUMMARY %\
                            {"nom_name":nom_name.encode(\
                                "ascii", "ignore")})
    print "Result: " + str(result)
    people_notified_count += 1
    print str(people_notified_count) + " have been notified so far."
    print "Notified " + person + " because of " + nom_name + "."

###################
# FINISH UP
###################
print()
print("TOTAL # of people notified so far: " +\
      str(people_notified_count))
print "Done! Exiting."