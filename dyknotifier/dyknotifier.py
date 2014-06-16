import getpass
import json
import re
from wikitools.wiki import Wiki
from wikitools.page import Page
from wikitools import api

class DYKNotifier():
    """
    A Wikipedia bot to notify an editor if an article they had created/expanded
    was nominated for DYK by someone else.
    """

    def __init__(self):
        self._wiki = Wiki("http://en.wikipedia.org/w/api.php")
        def attempt_login():
            username = raw_input("Username: ")
            password = getpass.getpass()
            self._wiki.login(username, password)
        attempt_login()
        while not self._wiki.isLoggedIn():
            print "Error logging in. Try again."
            attempt_login()
        print "Successfully logged in as " + self._wiki.username + "."
        self._ttdyk = Page(self._wiki, title="Template talk:Did you know")
        self._dyk_noms = self.get_list_of_dyk_noms_from_ttdyk()
        self._people_to_notify = dict()

    #################
    ##
    ## MAIN FUNCTIONS
    ##
    #################

    def get_list_of_dyk_noms_from_ttdyk(self):
        """
        Returns a list of subpages of T:DYKN nominated for DYK.
        """
        dyk_noms = []
        wikitext = self._ttdyk.getWikiText()
        print "Got wikitext from T:TDYK."
        params = {"action":"parse", "page":"Template talk:Did you know",\
                  "prop":"templates"}
        api_request = api.APIRequest(self._wiki, params)
        print "Sending an APIRequest for the templates on T:TDYK..."
        api_result = api_request.query()
        print "APIRequest completed."
        templates = json.loads(json.dumps(api_result))
        for template in templates["parse"]["templates"]:
            if template["*"].startswith("Template:Did you know nominations/"):
                dyk_noms.append(template["*"])
        return dyk_noms

    def run(self):
        """
        Runs the task.
        """
        self.remove_resolved_noms()
        print "[run()] Removed resolved noms from the list of DYK noms."
        self.remove_self_nominated_noms()
        print "[run()] Removed self-noms from the list of DYK noms."
        self.get_people_to_notify()
        print "[run()] Got a list of people to notify."
        self.notify_people()
        print "[run()] Notified people."

    def remove_resolved_noms(self):
        """
        Removes all resolved noms from the list of DYK noms.
        """
        def resolved_handler(page):
            if self.should_prune_as_resolved(page):
                self._dyk_noms.remove(page["title"])
        dyk_noms_strings = self.list_to_pipe_separated_query(self._dyk_noms)
        self.run_query(dyk_noms_strings, {"prop":"categories"},
                       resolved_handler)

    def remove_self_nominated_noms(self):
        """
        Removes all resolved noms from the list of DYK noms.
        """
        def resolved_handler(page):
            if self.should_prune_as_self_nom(page):
                self._dyk_noms.remove(page["title"])
        dyk_noms_strings = self.list_to_pipe_separated_query(self._dyk_noms)
        self.run_query(dyk_noms_strings,
                       {"prop":"revisions", "rvprop":"content"},
                       resolved_handler)

    def should_prune_as_resolved(self, page):
        """
        Given a page, should it be pruned from the list of DYK noms
        since it's already been passed or failed?
        """
        try:
            test = page["categories"]
        except KeyError:
            return False
        for category in page["categories"]:
            if "Category:Passed DYK nominations" in category["title"] or\
               "Category:Failed DYK nominations" in category["title"]:
                return True
        return False

    def should_prune_as_self_nom(self, page):
        wikitext = ""
        try:
            wikitext = page["revisions"][0]["*"]
        except KeyError:
            return False
        return "Self nominated" in wikitext          
                
    def get_people_to_notify(self):
        """
        Returns a dict of user talkpages to notify about their creations and
        the noms about which they should be notified.
        """
        print "Getting whom to notify for " + str(len(self._dyk_noms)) +\
              " noms..."
        dyk_noms_strings = list_to_pipe_separated_query(self._dyk_noms)
        eventual_count = (len(self._dyk_noms) // 50) +\
                         (cmp(len(self._dyk_noms), 0))
        count = 1
        for dyk_noms_string in dyk_noms_strings:
            params = {"action":"query", "titles":dyk_noms_string,\
                      "prop":"revisions", "rvprop":"content"}
            api_request = api.APIRequest(self._wiki, params)
            api_result = api_request.query()
            print "Processing results from query number " + str(count) +\
                  " out of " + str(eventual_count) + "..."
            for wikitext, title in [(page["revisions"][0]["*"], page["title"])\
                                    for page in\
                                    api_result["query"]["pages"].values()]:
                success, talkpages = self._get_who_to_nominate_from_wikitext(\
                    wikitext, title)
                if success:
                    self._people_to_notify.update(talkpages)
            count += 1
        print "The dict of user talkpages has " +\
              str(len(self._people_to_notify)) + " members."

    def notify_people(self):
        """
        Substitutes User:APersonBot/DYKNotice at the end of each page in a list
        of user talkpages, given a list of usernames.
        """
        for person in self._people_to_notify:
            nom_name = self._people_to_notify[person]
            template = "{{subst:User:APersonBot/DYKNotice|" +\
                       nom_name + "}}"
            talkpage = Page(self._wiki, title="User talk:" + person)
            #result = talkpage.edit(appendtext=template)
            print "Notified " + person + " because of " + nom_name + "."

    #################
    ##
    ## IMPORTANT HELPER FUNCTIONS
    ##
    #################

    def _get_who_to_nominate_from_wikitext(self, wikitext, title):
        """
        Given the wikitext of a DYK nom and its title, return a tuple of (
        success, a dict of user talkpages of who to notify and the titles
        of the noms for which they should be notified).
        """
        if "<small>" not in wikitext: return (False, [])
        index = wikitext.find("<small>")
        index_end = wikitext[index:].find("</small>")
        whodunit = wikitext[index:index_end + index]
        # For people who use standard signatures
        usernames = [whodunit[m.end():m.end()+whodunit[m.end():].find("|talk")]\
                     for m in re.finditer(r"User talk:", whodunit)]
        remove_multi_duplicates(usernames)
        print "For " + title + ", " + str(usernames)
        result = dict()
        for username in usernames:
            result[username] = title
        return (True, result)

    def run_query(self, list_of_queries, params, function):
        count = 1 # The current query number.
        for titles_string in list_of_queries:
            localized_params = {"action":"query", "titles":titles_string}
            localized_params.update(params)
            api_request = api.APIRequest(self._wiki, localized_params)
            api_result = api_request.query()
            print "Processing results from query number " + str(count) +\
                  " out of " + str(len(list_of_queries)) + "..."
            for page in api_result["query"]["pages"].values():
                function(page)
            count += 1

    def get_template_names_from_page(self, page):
        """
        Returns a list of template names in the given page using an API query.
        """
        print "Parsing out all templates from " + page + "..."
        params = {"action":"parse", "page":page, "prop":"templates"}
        api_request = api.APIRequest(self._wiki, params)
        api_result = api_request.query()
        print "APIRequest for templates on " + page + " completed."
        result = api_result["parse"]["templates"]
        print "Parsed " + str(len(result)) + " templates from " + page + "."
        print self.pretty_print(result)
        return result        

    #################
    ##
    ## GENERIC HELPER FUNCTIONS
    ##
    #################

    def remove_multi_duplicates(self, the_list):
        """
        If there's a duplicate item in the_list, remove BOTH occurrences.
        """
        for item in the_list[:]:
            if the_list.count(item) > 1:
                while item in the_list:
                    the_list.remove(item)
        return the_list

    def pretty_print(self, query_result):
        """
        What **is** beauty?
        """
        print json.dumps(query_result, indent=4, separators=(",", ": "))

    def list_to_pipe_separated_query(self, the_list):
        """
        Breaks a list up into pipe-separated queries of 50.
        """
        result = []
        for index in xrange(0, len(the_list) - 1, 50):
            sub_result = ""
            for item in [x.encode("utf-8") for x in the_list[index : index + 50]]:
                sub_result += str(item) + "|"
            result.append(sub_result[:-1])
        return result

def main():
    print "[main()] Before DYKNotifier constructor"
    notifier = DYKNotifier()
    print "[main()] Constructed a DYKNotifier."
    notifier.run()
    print "[main()] Exiting main()"

if __name__ == "__main__":
    main()
