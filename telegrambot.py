import Constants as keys
from telegram.ext import *
from telegram import InlineKeyboardButton
from telegram import InlineKeyboardMarkup
from datetime import datetime
from espncricinfo.match import Match
from espncricinfo.summary import Summary
import threading
from time import sleep

# name: cricinfo
# username: cricinfo_telegram_bot

class updates_thread(threading.Thread):
    def __init__(self, update):
        threading.Thread.__init__(self)
        self.update = update

    def run(self):
        global tracker
        global refresh_rate
        chatid = self.update.callback_query.message.chat.id
        matchid = tracker[chatid].match
        while tracker[chatid].tracker:
            m = Match(matchid)
            if(len(m.innings) == 0):
                if(tracker[chatid].balls == -1):
                    tracker[chatid].balls = 0
                    self.update.callback_query.message.reply_text("You're early! looks like the match hasn't started. We'll be sending updates once the match starts.")
                sleep(refresh_rate)
                continue
            i = len(m.innings)-1
            while i >= 0:
                if m.innings[i]['balls'] != 0:
                    cur_balls = m.innings[i]['balls']
                    break
                i-=1
            if cur_balls > tracker[chatid].balls:
                summary = m.current_summary
                if summary == None or len(summary) == 0:
                    self.update.callback_query.message.reply_text("OOPS! we don't have anything about the selected match")
                else:
                    self.update.callback_query.message.reply_text(summary)
                tracker[chatid].balls = cur_balls
            sleep(refresh_rate)

refresh_rate = 2
# check for new delivery for every 2 seconds
tracker = dict()

class Tracker:
    def __init__(self):
        self.match = None
        self.balls = -1
        self.tracker = False
        self.thread = None

def start_command(update, context):
    update.message.reply_text("Welcome to cricinfo bot! type help if you don't know how to use me.")

def help_command(update, context):
    update.message.reply_text('If you need help! You may ask for it on Google!')

def display_score(message, data):
    chatid = message.chat.id
    if chatid not in tracker.keys() or tracker[chatid].match != data:
        new = Tracker()
        new.match = data
        new.tracker = False
        new.thread = None
        if chatid in tracker.keys() and tracker[chatid].tracker:
            tracker[chatid].tracker = False
            tracker[chatid].thread.join()
        tracker[chatid] = new
    m = Match(data)
    if len(m.innings) == 0:
        message.reply_text("You're early! looks like the match hasn't started. We'll be sending updates once the match starts.")
        return
    result = "Current summary: " + m.current_summary
    message.reply_text(result)
    result = "Full details:\n\n"
    team_ids = []
    teams = []
    team_ids.append(int(m.team_1_id))
    team_ids.append(int(m.team_2_id))
    teams.append(m.team_1_abbreviation)
    teams.append(m.team_2_abbreviation)
    #result += 'Match type: ' + m.match_class + '\n'
    result += "{0} won the toss and chose to {1} first \n\n".format(teams[int(m.toss_winner_team_id == team_ids[1])],m.toss_decision_name)
    for innings in m.innings:
        if innings['balls'] == 0:
            continue
        denominator = ''
        if innings['wickets'] != 10:
            denominator = "/" + str(innings['wickets'])
        overs = innings['overs']
        if m.scheduled_overs != 0:
            overs += "/{0}".format(str(m.scheduled_overs))
        inn = ""
        if innings['ball_limit'] == 0:
            inn = "({0} innings)".format(innings['innings_numth'])
        result += "{0}{1}: {2}{3}({4}) @ {5} runs per over\n".format(teams[int(innings['batting_team_id'] == team_ids[1])],inn,str(innings['runs']),denominator,overs, innings['run_rate'])
    
    if m.latest_batting is not None:
        result += '\nBatting:\n'
        for batsmen in m.latest_batting:
            notout = ""
            if(batsmen['notout'] == 1):
                notout = "*"
            run_rate = 0
            if batsmen['balls_faced'] != '0':
                run_rate = batsmen['runs']*100/int(batsmen['balls_faced'])
            run_rate = str(run_rate)
            run_rate = run_rate[0:min(5,len(run_rate))]
            result += "{0} - {1}{3}({2}) @ {4} \n".format(batsmen['known_as'],str(batsmen['runs']),batsmen['balls_faced'],notout,run_rate)

    if m.latest_bowling is not None:
        result += '\nBowling: (Overs - Wickets - Runs - Maidens - Economy)\n'
        for bowler in m.latest_bowling:
            economy = 0
            if convert_overs_to_balls(bowler['overs']) != 0:
                economy = bowler['conceded']*6/convert_overs_to_balls(bowler['overs'])
            economy = str(economy)
            economy = economy[0:min(4,len(economy))]
            result += "{0}: {1} - {2} - {3} - {4} - {5}\n".format(bowler['known_as'],bowler['overs'],bowler['wickets'],bowler['conceded'],bowler['maidens'],economy)

    if m.latest_innings_fow is not None:
        fow = []
        curballs = 0
        curruns = 0
        result += '\nFall of wickets: \n'
        last_players = None
        for iter in m.latest_innings_fow:
            curballs += convert_overs_to_balls(iter['overs'])
            curruns += iter['runs']
            p = []
            p.append(iter['player'][0]['known_as'])
            p.append(iter['player'][1]['known_as'])
            if last_players is not None:
                fow[-1].append(last_players[int(last_players[0] in p)])
            fow.append([curballs,curruns])
            last_players = [p[0],p[1]]

        for i in range(0,len(fow)-1):
            result += "{0}/{1} - {2} ov, {3}\n".format(str(fow[i][1]),str(i+1),str(convert_balls_to_overs(fow[i][0])),fow[i][2])

    message.reply_text(result)

def button(update, context):
    data = update.callback_query.data
    if data[0] == '#':
        global tracker
        if data[1] == '1':
            data = data[2:]
            new = Tracker()
            new.match = data
            new.tracker = True
            new.thread = updates_thread(update)
            chatid = update.callback_query.message.chat.id
            if chatid in tracker.keys() and tracker[chatid].tracker:
                tracker[chatid].tracker = False
                tracker[chatid].thread.join()
            tracker[chatid] = new
            update.callback_query.message.reply_text("Tracker has been turned on for the selected match. You'll get updates for every delivery.")
            tracker[chatid].thread.start()
        else:
            display_score(update.callback_query.message,data[2:])
    else:
        match = Match(data)
        chatid = update.callback_query.message.chat.id
        new = Tracker()
        new.match = match.match_id
        tracker[chatid] = new
        buttons = []
        buttons.append([InlineKeyboardButton("Track this match", callback_data = "#1"+data)])
        buttons.append([InlineKeyboardButton("Get scorecard", callback_data = "#2"+data)])
        keyboard = InlineKeyboardMarkup(buttons)
        update.callback_query.message.reply_text("Selected match: {0}".format(match.description), reply_markup=keyboard)

def convert_overs_to_balls(s):
    if len(s) <= 2 or s[-2] != '.':
        return int(s)*6
    else:
        result = int(s[0:len(s)-2])*6
        result += int(s[-1])
        return result

def convert_balls_to_overs(s):
    s = "{0}.{1}".format(str(s//6),str(s%6))
    return s

def handle_message(update, context):
    text = ""
    if(update.message is not None):
        text = str(update.message.text).lower()
    if text in ("score","scorecard"):
        chatid = update.message.chat.id
        if chatid not in tracker.keys() or tracker[chatid].match is None:
            update.message.reply_text("Yoo! Select a match first to get the score.")
        else:
            display_score(update.message,tracker[chatid].match)
        return
    if text in ("matches", "sup", "what's up?", "select"):
        first_message = "Hang on, we're fetching list of all the live matches. This might take a couple of minutes."
        update.message.reply_text(first_message)
        s = Summary()
        buttons = []
        for match_id in s.match_ids:
            m = Match(match_id)
            buttons.append([InlineKeyboardButton(m.description, callback_data = match_id)])
        keyboard = InlineKeyboardMarkup(buttons)
        update.message.reply_text("Select a match:", reply_markup=keyboard)
        return
    if text in ("off","stop"):
        chatid = update.message.chat.id
        if chatid not in tracker.keys() or tracker[chatid].tracker == False:
            update.message.reply_text("What? you don't have any tracker turned on.")
            return
        tracker[chatid].tracker = False
        tracker[chatid].thread.join()
        update.message.reply_text("Ok, we've called off the tracker.")
        return
    response = sample_responses(text)
    update.message.reply_text(response)

def error(update, context):
    print(f"Update {update} caused error {context.error}")

def sample_responses(input_text):
    user_message = str(input_text).lower()
    
    if user_message in ("who are you", "who are you?"):
        return "I am cricinfo bot, I can provide the information about the ongoing cricket matches. You may want to check the menu to access my services."
    
    if user_message in ("help","commands"):
        result = "Hey there! Here are the list of commands you can use\n\n"
        result += "help, commands - You get to see the message what you're looking at rn\n"
        result += "who are you, who are you? - To know what this bot does\n"
        result += "matches, select, what's up?, sup - To get the list of live matches out of which you can select one\n"
        result += "off, stop - To turnoff the tracker for the selected match\n" 
        result += "score, scorecard - To get the scorecard of previously selected match\n\n"
        result += "Note: all the commands are case insensitive\n"
        return result

    return "I don't understand what you've said."

def main():
    updater = Updater(keys.API_KEY, use_context = True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start_command))
    dp.add_handler(CommandHandler("start", help_command))
    dp.add_handler(CallbackQueryHandler(button))
    dp.add_handler(MessageHandler(Filters.text, handle_message))
    dp.add_error_handler(error)
    updater.start_polling()
    updater.idle()

main()