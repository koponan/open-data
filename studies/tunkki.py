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

def load_all_data():
    """Load all data (except 360 data which is TODO).
    Store loaded data into `datastore` to be shared
    between functions. Loading everything (especially events)
    takes time so omitted from Champions League reporting
    which is the only maintained reporting at the moment.
    """
    with open(COMPETITIONS_FILE, "r") as f:
        datastore.competitions = json.load(f)
    datastore.events = get_items(EVENTS_PATH)
    datastore.lineups = get_items(LINEUPS_PATH)
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

def get_winning_team(match: dict):
    """Return winning team or None in case of a draw
    """
    if match["home_score"] > match["away_score"]:
        return match["home_team"]
    elif match["home_score"] < match["away_score"]:
        return match["away_team"]
    elif match["home_penalty_score"] > match["away_penalty_score"]:
        return match["home_team"]
    elif match["home_penalty_score"] < match["away_penalty_score"]:
        return match["away_team"]
    else:
        return None

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

def populate_penalty_scores(match: dict, events: list):
    successful_penalties_home = []
    successful_penalties_away = []
    for e in events:
        if e["period"] == 5 and e["type"]["name"] == "Shot" and e["shot"]["outcome"]["name"] == "Goal":
            if e["team"]["name"] == match["home_team"]["home_team_name"]:
                successful_penalties_home.append(e)
            else:
                successful_penalties_away.append(e)

    match["home_penalty_score"] = len(successful_penalties_home)
    match["away_penalty_score"] = len(successful_penalties_away)

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

def print_match_result(match: dict):
    season = match["season"]["season_name"]
    ht = match["home_team"]["home_team_name"]
    at = match["away_team"]["away_team_name"]
    home_score = match["home_score"]
    away_score = match["away_score"]
    match_overview = f"{' ' * 8}{season} {ht}{' ' * 4}- {at} {home_score}-{away_score}"
    print(match_overview)
    ht_pos = match_overview.index(ht)
    at_pos = match_overview.index(at)
    for g in match["goals"]:
        goal_time = g['minute'] + 1 # Not the latest full minute but the ongoing minute
        team_pos = ht_pos if g["team"]["name"] == ht else at_pos
        print(f"{' ' * team_pos}{goal_time}' {g['player']['nickname']}")

    if match['result_type'] == ResultType.PENALTY_SHOOTOUT:
        print(f"{' ' * ht_pos}* Penalties {match['home_penalty_score']}-{match['away_penalty_score']}")

def fmt_pair(pair: tuple):
    return f"{pair[0]} {pair[1]}"

def report_ucl():
    ucl_matches = [m for m in get_items(MATCHES_ROOT_PATH) if m["competition"]["competition_name"] == "Champions League"]
    # filter to have continuous block of seasons
    matches = [m for m in ucl_matches if int(m["season"]["season_name"].split("/")[0]) >= 2008]
    matches.sort(key=lambda m:m["season"]["season_name"])
    first_season = matches[0]["season"]["season_name"]
    last_season = matches[-1]["season"]["season_name"]
    print(f"Study of Champions League finals for seasons {first_season} - {last_season}\n")
    teams_involved = list(itertools.chain.from_iterable(map(lambda m: (m["home_team"], m["away_team"]), matches)))
    team_countries = [t["country"]["name"] for t in teams_involved]

    country_counts = Counter(team_countries)
    print(f"* Number of teams reaching final by country")
    # We see top 5 leagues with the exception of France
    for c in country_counts.most_common():
        print(f"\t{fmt_pair(c)}")
    print()

    match_events = {m["match_id"]: load_events(m["match_id"]) for m in matches}

    print("* Match results")
    for m in matches:
        m["result_type"] = get_result_type(match_events[m["match_id"]])
        m["goals"] = get_goal_events(match_events[m["match_id"]])
        populate_penalty_scores(m, match_events[m["match_id"]])
        populate_player_nicknames(m["match_id"], m["goals"])
        print_match_result(m)
        print()

    winning_teams = [get_winning_team(m) for m in matches]
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
            print(f"\t\t{fmt_pair(pair)}")
    print()

    goal_scorers = sorted(list(itertools.chain.from_iterable(
        map(lambda m: map(lambda g: g["player"]["nickname"], m["goals"]), matches))))
    goal_counter = Counter(goal_scorers)
    print("* Top 10 goal scorers")
    for g in goal_counter.most_common()[:10]:
        print(f"\t{fmt_pair(g)}")

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
    report_ucl()

if __name__ == "__main__":
    main()