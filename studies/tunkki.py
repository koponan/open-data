#!/usr/bin/env python3

from collections import Counter
from dataclasses import dataclass
from enum import Enum
import itertools
import json
import os

EVENTS_PATH = "../data/events/"
LINEUPS_PATH = "../data/lineups/"
MATCHES_ROOT_PATH = "../data/matches/"
COMPETITIONS_FILE = "../data/competitions.json"

class ResultType(Enum):
    FULL_TIME = 1
    EXTRA_TIME = 2
    PENALTY_SHOOTOUT = 3

@dataclass
class DataStore:
    competitions: list
    events: list
    lineups: list
    matches: list

datastore = DataStore([], [], [], [])

def get_items(dir: str) -> list:
    """List items within dir. If item is dir
    move within and list items there. Get file
    items and collect objects within them."""
    ret_items = []
    fnames_in_dir = os.listdir(dir)
    # print(f"Dir '{dir}': {len(fnames_in_dir)} items")
    fpaths = [os.path.join(dir, name) for name in fnames_in_dir]
    for fpath in fpaths:
        if os.path.isdir(fpath):
            subdir_items = get_items(fpath)
            ret_items += subdir_items
        else:
            with open(fpath, "r") as f:
                item_objs = json.load(f)
                ret_items += item_objs
    
    return ret_items

def load_data():
    with open(COMPETITIONS_FILE, "r") as f:
        datastore.competitions = json.load(f)
    # instead of fetching events for all matches, events are fetched later
    # only for specific matches to reduce overhead
    #datastore.events = get_items(EVENTS_PATH)
    # same goes for lineups
    #datastore.lineups = get_items(LINEUPS_PATH)
    datastore.matches = get_items(MATCHES_ROOT_PATH)

def load_events(match_id: int):
    with open(f"{EVENTS_PATH}/{match_id}.json") as f:
        return json.load(f)

def report_competitions():
    male_comps = [c for c in datastore.competitions if c["competition_gender"] == "male"]
    female_comps = [c for c in datastore.competitions if c["competition_gender"] == "female"]
    print("*** Competitions ***")
    for lst in [male_comps, female_comps]:
        for comp in lst:
            name = comp["competition_name"]
            season_yy = comp["season_name"]
            print(f"{name} {season_yy}")
        print()

def report_matches_by_competition(comp_name: str):
    comp_matches = [m for m in datastore.matches if m["competition"]["competition_name"] == comp_name]
    print(f"*** {comp_name.title()} matches ***")
    seasons = {}
    for m in comp_matches:
        season = m["season"]["season_name"]
        if season not in seasons.keys():
            seasons[season] = []
        ht = m["home_team"]["home_team_name"]
        at = m["away_team"]["away_team_name"]
        home_score = m["home_score"]
        away_score = m["away_score"]
        seasons[season].append(f"{ht}-{at} {home_score}-{away_score}")

    print(f"Seasons: {len(seasons.keys())}")
    print(f"Matches: {len(comp_matches)}")
    seasons_sorted = sorted(list(seasons.items()), key=lambda k: k[0])
    for (season, matches) in seasons_sorted:
        print(f"* {season} - {len(matches)} matches")
        for m in matches:
            print(f"\t{m}")
        print()

def get_team_name(team: dict):
    return team.get("home_team_name", team.get("away_team_name"))

def get_winning_team(match: dict, events: list):
    if match["home_score"] > match["away_score"]:
        return match["home_team"]
    elif match["home_score"] < match["away_score"]:
        return match["away_team"]

    successful_penalties_home = []
    successful_penalties_away = []
    for e in events:
        if e["period"] == 5 and e["type"]["name"] == "Shot" and e["shot"]["outcome"]["name"] == "Goal":
            if e["team"]["name"] == match["home_team"]["home_team_name"]:
                successful_penalties_home.append(e)
            else:
                successful_penalties_away.append(e)

    penalty_score_home = len(successful_penalties_home)
    penalty_score_away = len(successful_penalties_away)
    match["home_penalty_score"] = penalty_score_home
    match["away_penalty_score"] = penalty_score_away

    if penalty_score_home > penalty_score_away:
        return match["home_team"]
    else:
        return match["away_team"]

def get_goal_events(match_events: list):
    return [e for e in match_events if e["period"] <= 4 and e["type"]["name"] == "Shot" and e["shot"]["outcome"]["name"] == "Goal"]

def get_result_type(match_events: list):
    ending_period_event = max(match_events, key=lambda m:m["period"])
    ending_period = ending_period_event["period"]
    if ending_period <= 2:
        return ResultType.FULL_TIME
    elif ending_period <= 4:
        return ResultType.EXTRA_TIME
    return ResultType.PENALTY_SHOOTOUT

def populate_player_nicknames(match_id: int, match_event_list: list):
    lineups: list = []
    with open(f"{LINEUPS_PATH}/{match_id}.json") as f:
        lineups = json.load(f)
    lineup_by_team_name = {}
    lineup_by_team_name[lineups[0]["team_name"]] = lineups[0]["lineup"]
    lineup_by_team_name[lineups[1]["team_name"]] = lineups[1]["lineup"]

    for e in match_event_list:
        team_name = e["team"]["name"]
        lineup = lineup_by_team_name[team_name]
        player = e["player"]
        player_in_lineup = [p for p in lineup if p["player_id"] == player["id"]][0]
        nickname = player_in_lineup["player_nickname"]
        player["nickname"] = nickname if nickname is not None else player["name"]

def report_ucl():
    ucl_matches = [m for m in datastore.matches if m["competition"]["competition_name"] == "Champions League"]
    # filter to have continuous block of seasons
    matches = [m for m in ucl_matches if int(m["season"]["season_name"].split("/")[0]) >= 2008]
    matches.sort(key=lambda m:m["season"]["season_name"])
    
    teams_involved = list(itertools.chain.from_iterable(map(lambda m: (m["home_team"], m["away_team"]), matches)))
    team_countries = [t["country"]["name"] for t in teams_involved]

    country_counts = Counter(team_countries)
    print(f"* Number of teams reaching final by country")
    # We see top 5 leagues with the exception of France
    for c in country_counts.most_common():
        print(f"\t{c}")
    print()

    match_events = {m["match_id"]: load_events(m["match_id"]) for m in matches}
    
    winning_teams = []
    print("* Match results")
    for m in matches:
        season = m["season"]["season_name"]
        ht = m["home_team"]["home_team_name"]
        at = m["away_team"]["away_team_name"]
        home_score = m["home_score"]
        away_score = m["away_score"]
        res_type = get_result_type(match_events[m["match_id"]])
        m["result_type"] = res_type # TODO: refactor to something else than random populating
        winner = get_winning_team(m, match_events[m["match_id"]])
        winning_teams.append(winner)
        match_overview = f"\t{season}: {ht}-{at} {home_score}-{away_score} {res_type.name}"
        print(match_overview)
        line_len = len(match_overview) + 7 # account fot tab character showing as 8 spaces
        goals = get_goal_events(match_events[m["match_id"]])
        m["goals"] = goals
        populate_player_nicknames(m["match_id"], goals)
        for g in goals:
            goal_time = g['minute'] + 1 # Not the latest full minute but the ongoing minute
            if g["team"]["name"] == ht:
                print(f"\t{goal_time}' {g['player']['nickname']}")
            else:
                away_goal_line = f"{goal_time}' {g['player']['nickname']}"
                away_padded = " " * (line_len - len(away_goal_line)) + away_goal_line
                print(away_padded)
        if m['result_type'] == ResultType.PENALTY_SHOOTOUT:
            print("\t** Penalties")
            print(f"\t\t{m['home_penalty_score']}-{m['away_penalty_score']}")
        print()

    # TODO: compare winning teams to matches, should notice that spanish side has always won when present
    teams_by_country = {}
    for team in winning_teams:
        name = get_team_name(team)
        country = team["country"]["name"]
        if country in teams_by_country.keys():
            teams_by_country[country].append(name)
        else:
            teams_by_country[country] = [name]

    print(f"* Wins by country and team")
    for country, teams in sorted(list(teams_by_country.items()), key=lambda pair: -len(pair[1])):
        c = Counter(teams).most_common()
        print(f"\t{country} - {len(teams)} wins")
        for pair in c:
            print(f"\t\t{pair}")
    print()
    goal_scorers = sorted(list(itertools.chain.from_iterable(
        map(lambda m: map(lambda g: g["player"]["nickname"], m["goals"]), matches))))
    goal_counter = Counter(goal_scorers)
    print("* Top 10 goal scorers")
    for g in goal_counter.most_common()[:10]:
        print(f"\t{g}")

def number_summary():
    match_count = len(datastore.matches)
    lineup_count = len(datastore.lineups)
    comp_count = len(datastore.competitions)
    event_count = len(datastore.events)
    print("*** Summary of data in numbers ***")
    print(f"Matches: {match_count}")
    print(f"Lineups: {lineup_count}")
    print(f"Competitions: {comp_count}")
    print(f"Match events: {event_count}")

def main():
    load_data()
    report_ucl()

if __name__ == "__main__":
    main()