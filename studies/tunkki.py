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
    print(f"Dir '{dir}': {len(fnames_in_dir)} items")
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
    # commented out to reduce overhead
    #datastore.events = get_items(EVENTS_PATH)
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
        if e["period"] == 5 and e["type"] == "Shot" and e["shot"]["outcome"] == "Goal":
            if e["team"] == match["home_team"]:
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

def get_result_type(match_events: list):
    ending_period_event = max(match_events, key=lambda m:m["period"])
    ending_period = ending_period_event["period"]
    if ending_period <= 2:
        return ResultType.FULL_TIME
    elif ending_period <= 4:
        return ResultType.EXTRA_TIME
    return ResultType.PENALTY_SHOOTOUT

def report_ucl():
    ucl_matches = [m for m in datastore.matches if m["competition"]["competition_name"] == "Champions League"]
    # filter to have continuous block of seasons
    matches = [m for m in ucl_matches if int(m["season"]["season_name"].split("/")[0]) >= 2008]
    matches.sort(key=lambda m:m["season"]["season_name"])
    
    teams_involved = list(itertools.chain.from_iterable(map(lambda m: (m["home_team"], m["away_team"]), matches)))
    team_countries = [t["country"]["name"] for t in teams_involved]

    country_counts = Counter(team_countries)
    print(f"Number of teams reaching final by country")
    # We see top 5 leagues with the exception of france
    for c in country_counts.most_common():
        print(c)

    match_events = {m["match_id"]: load_events(m["match_id"]) for m in matches}
    
    for m in matches:
        season = m["season"]["season_name"]
        ht = m["home_team"]["home_team_name"]
        at = m["away_team"]["away_team_name"]
        home_score = m["home_score"]
        away_score = m["away_score"]
        res_type = get_result_type(match_events[m["match_id"]])
        m["result_type"] = res_type # TODO: refactor to something else than random populating
        print(f"* {season}: {ht}-{at} {home_score}-{away_score} {res_type.name}")

    winning_teams = [get_winning_team(match, match_events[match["match_id"]]) for match in matches]
    # compare winning teams to matches, should notice that spanish side has always won when present
    teams_by_country = {}
    for team in winning_teams:
        name = get_team_name(team)
        country = team["country"]["name"]
        if country in teams_by_country.keys():
            teams_by_country[country].append(name)
        else:
            teams_by_country[country] = [name]
    
    for country, teams in sorted(list(teams_by_country.items()), key=lambda pair: -len(pair[1])):
        c = Counter(teams).most_common()
        print(f"* {country} - {len(teams)} wins")
        for pair in c:
            print(f"\t {pair}")

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