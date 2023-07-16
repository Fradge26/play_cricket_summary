import datetime
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
import requests
from PIL import ImageFont, ImageDraw, Image
from bs4 import BeautifulSoup

from play_cricket_api import PlayCricketAPI
from send_email import send_mail


class PlayCricketMatchSummary:
    def __init__(self):
        self.play_cricket_api = PlayCricketAPI()
        self.script_path = os.path.dirname(os.path.realpath(__file__))
        self.json_path = os.path.join(self.script_path, "output", "json")
        self.jpg_path = os.path.join(self.script_path, "output", "jpg")
        self.template_directory = os.path.join(
            self.script_path, "resources", "templates"
        )
        self.jpg_config = self.load_json(
            os.path.join(self.script_path, "resources", "config.json")
        )
        self.logos_directory = os.path.join(self.script_path, "resources", "logos")
        Path(self.logos_directory).mkdir(parents=True, exist_ok=True)
        Path(self.jpg_path).mkdir(parents=True, exist_ok=True)
        Path(self.json_path).mkdir(parents=True, exist_ok=True)
        self.dcl_divisions = (
            "PREMIER DIVISION",
            "A DIVISION",
            "B DIVISION",
            "B DIVISION",
            "C DIVISION EAST",
            "C DIVISION WEST",
            "D DIVISION EAST",
            "D DIVISION WEST",
            "E DIVISION EAST",
            "E DIVISION WEST",
            "F DIVISION EAST",
            "F DIVISION WEST",
            "G DIVISION EAST",
            "G DIVISION WEST",
            "H DIVISION EAST",
            "H DIVISION WEST",
        )

    def main(self):
        self.scrape_play_cricket_results()

    def load_json(self, json_path):
        with open(json_path) as json_file:
            return json.load(json_file)

    def get_play_cricket_result_ids(self):
        from_match_date = datetime.datetime.now() - datetime.timedelta(days=7)
        results = self.play_cricket_api.get_result_summary(
            from_match_date=from_match_date.strftime("%d/%m/%Y")
        )
        result_summary = results["result_summary"]
        match_ids = [m["id"] for m in result_summary if m["result"] != "M"]
        return match_ids

    def scrape_play_cricket_results(self):
        existing_summaries = self.get_existing_summaries()
        new_summaries = []
        for result_id in self.get_play_cricket_result_ids():
            if self.validate_match_detail(result_id):
                summary_data = self.get_result_data(result_id)
                if summary_data["filename"] not in existing_summaries:
                    new_summaries.append(
                        os.path.join(self.jpg_path, f'{summary_data["filename"]}.JPG')
                    )
                    self.get_club_logos(result_id)
                    self.write_summary_json(summary_data)
                    self.write_summary_jpg(summary_data)
        if new_summaries:
            send_mail(
                send_from="fradge@hotmail.co.uk",
                send_to=["fradge@hotmail.co.uk"],  # "billybuckingham00@gmail.com"],
                subject=f'Exeter CC Match Summaries {datetime.datetime.today().strftime("%d_%m_%Y")}',
                text="Exeter CC match summaries attached. Regards Fradge",
                files=new_summaries,
            )

    def get_existing_summaries(self):
        existing_summary_set = set()
        for file in os.listdir(self.jpg_path):
            if file.endswith(".JPG"):
                existing_summary_set.add(file.replace(".JPG", ""))
        return existing_summary_set

    def validate_match_detail(self, result_id):
        response_json = self.play_cricket_api.get_match_detail(result_id)
        match_details = response_json["match_details"][0]
        if (
            len(match_details["innings"]) < 2
            or len(match_details["innings"][0]["bat"]) == 0
            or len(match_details["innings"][0]["bowl"]) == 0
            or len(match_details["innings"][1]["bat"]) == 0
            or len(match_details["innings"][1]["bowl"]) == 0
        ):
            return False
        else:
            return True

    def write_summary_json(self, summary_data):
        with open(
            os.path.join(self.json_path, f'{summary_data["filename"]}.json'), "w"
        ) as out_file:
            out_file.write(json.dumps(summary_data, indent=4))

    def write_summary_jpg(self, summary_data):
        image = Image.open(
            os.path.join(self.template_directory, summary_data["template_filename"])
        )
        home_logo = Image.open(os.path.join(self.logos_directory, "home_club_logo.JPG"))
        away_logo = Image.open(os.path.join(self.logos_directory, "away_club_logo.JPG"))
        home_logo = home_logo.resize((100, 100))
        away_logo = away_logo.resize((100, 100))
        image.paste(home_logo, (107, 180))
        image.paste(away_logo, (875, 180))
        draw = ImageDraw.Draw(image)
        for field_name, conf in self.jpg_config.items():
            font = ImageFont.truetype(
                os.path.join(
                    self.script_path, "resources", "font", "Montserrat-Regular.ttf"
                ),
                conf["scale"],
            )
            print(summary_data[field_name])
            draw.text(
                (conf["x"], conf["y"]),
                summary_data[field_name],
                font=font,
                fill=tuple(conf["rgb"]),
                spacing=4,
                anchor=conf["anchor"],
                align="center",
            )
        image.save(os.path.join(self.jpg_path, f'{summary_data["filename"]}.JPG'))

    def get_template_filename(self, data):
        return f"{self.get_match_template_type(data)}_{self.get_exeter_cc_first_innings(data)}.JPG"

    def get_match_template_type(self, data):
        if (
            "UNDER" in data["home_team_name"].upper()
            or "UNDER" in data["away_team_name"].upper()
        ):
            return "juniors"
        elif (
            "WOMEN" in data["home_team_name"].upper()
            or "WOMEN" in data["away_team_name"].upper()
        ):
            return "womens"
        else:
            return "mens"

    def get_exeter_cc_first_innings(self, data):
        if "EXETER CC" in data["toss"].upper():
            if "ELECTED TO BAT" in data["toss"].upper():
                return "batting_first"
            elif "ELECTED TO FIELD" in data["toss"].upper():
                return "fielding_first"
        else:
            if "ELECTED TO BAT" in data["toss"].upper():
                return "fielding_first"
            elif "ELECTED TO FIELD" in data["toss"].upper():
                return "batting_first"

    def get_html_document(self, url):
        response = requests.get(url)
        return response.text

    def get_club_logos(self, match_id):
        html_document = self.get_html_document(
            f"https://exeter.play-cricket.com/website/results/{match_id}"
        )
        soup = BeautifulSoup(html_document, "html.parser")
        logo_class = soup.find_all("p", {"class": "team-ttl team-cov"})
        url = logo_class[0].contents[1].attrs["src"]
        r = requests.get(url)
        with open(os.path.join(self.logos_directory, "home_club_logo.JPG"), "wb") as f:
            f.write(r.content)
        logo_class = soup.find_all("p", {"class": "team-ttl team-att"})
        url = logo_class[0].contents[1].attrs["src"]
        r = requests.get(url)
        with open(os.path.join(self.logos_directory, "away_club_logo.JPG"), "wb") as f:
            f.write(r.content)

    def get_result_data(self, match_id):
        response_json = self.play_cricket_api.get_match_detail(match_id)
        match_details = response_json["match_details"][0]
        innings_1_bat_df = pd.DataFrame(match_details["innings"][0]["bat"])
        innings_1_bat_df["runs"] = pd.to_numeric(
            innings_1_bat_df["runs"], errors="coerce", downcast="integer"
        )
        innings_1_bat_df["balls"] = pd.to_numeric(
            innings_1_bat_df["balls"], errors="coerce", downcast="integer"
        )
        innings_1_bat_df.sort_values(
            by=["runs", "balls"], ascending=[False, True], inplace=True
        )
        innings_1_bat_df.reset_index(inplace=True)
        innings_1_bowl_df = pd.DataFrame(match_details["innings"][0]["bowl"])
        innings_1_bowl_df["wickets"] = pd.to_numeric(
            innings_1_bowl_df["wickets"], errors="coerce", downcast="integer"
        )
        innings_1_bowl_df["runs"] = pd.to_numeric(
            innings_1_bowl_df["runs"], errors="coerce", downcast="integer"
        )
        innings_1_bowl_df["overs"] = pd.to_numeric(
            innings_1_bowl_df["overs"], errors="coerce", downcast="integer"
        )
        innings_1_bowl_df["rr"] = innings_1_bowl_df["runs"] / innings_1_bowl_df["overs"]
        innings_1_bowl_df.sort_values(
            by=["wickets", "rr"], ascending=[False, True], inplace=True
        )
        innings_1_bowl_df.reset_index(inplace=True)
        innings_2_bat_df = pd.DataFrame(match_details["innings"][1]["bat"])
        innings_2_bat_df["runs"] = pd.to_numeric(
            innings_2_bat_df["runs"], errors="coerce", downcast="integer"
        )
        innings_2_bat_df["balls"] = pd.to_numeric(
            innings_2_bat_df["balls"], errors="coerce", downcast="integer"
        )
        innings_2_bat_df.sort_values(
            by=["runs", "balls"], ascending=[False, True], inplace=True
        )
        innings_2_bat_df.reset_index(inplace=True)
        innings_2_bowl_df = pd.DataFrame(match_details["innings"][1]["bowl"])
        innings_2_bowl_df["wickets"] = pd.to_numeric(
            innings_2_bowl_df["wickets"], errors="coerce", downcast="integer"
        )
        innings_2_bowl_df["runs"] = pd.to_numeric(
            innings_2_bowl_df["runs"], errors="coerce", downcast="integer"
        )
        innings_2_bowl_df["overs"] = pd.to_numeric(
            innings_2_bowl_df["overs"], errors="coerce", downcast="integer"
        )
        innings_2_bowl_df["rr"] = innings_2_bowl_df["runs"] / innings_2_bowl_df["overs"]
        innings_2_bowl_df.sort_values(
            by=["wickets", "rr"], ascending=[False, True], inplace=True
        )
        innings_2_bowl_df.reset_index(inplace=True)
        summary_data = {
            "match_type": self.get_match_type(
                match_details["competition_name"].upper()
            ),
            "match_summary": "MATCH SUMMARY",
            "toss": self.replace_strings(match_details["toss"]).upper(),
            "innings_1_team": self.get_team_name(
                match_details["innings"][0]["team_batting_name"]
            ),
            "innings_1_overs": f'OVERS {self.get_overs(match_details["innings"][0]["overs"])}',
            "innings_1_score": f'{match_details["innings"][0]["runs"]}/{match_details["innings"][0]["wickets"]}',
            "innings_1_bat_1_name": self.get_bat_name(innings_1_bat_df.loc[0]),
            "innings_1_bat_1_runs": self.get_bat_runs(innings_1_bat_df.loc[0]),
            "innings_1_bat_2_name": self.get_bat_name(innings_1_bat_df.loc[1]),
            "innings_1_bat_2_runs": self.get_bat_runs(innings_1_bat_df.loc[1]),
            "innings_1_bat_3_name": self.get_bat_name(innings_1_bat_df.loc[2]),
            "innings_1_bat_3_runs": self.get_bat_runs(innings_1_bat_df.loc[2]),
            "innings_1_bowl_1_name": self.get_bowl_name(innings_1_bowl_df.loc[0]),
            "innings_1_bowl_1_figures": self.get_bowler_figures(
                innings_1_bowl_df.loc[0]
            ),
            "innings_1_bowl_2_name": self.get_bowl_name(innings_1_bowl_df.loc[1]),
            "innings_1_bowl_2_figures": self.get_bowler_figures(
                innings_1_bowl_df.loc[1]
            ),
            "innings_1_bowl_3_name": self.get_bowl_name(innings_1_bowl_df.loc[2]),
            "innings_1_bowl_3_figures": self.get_bowler_figures(
                innings_1_bowl_df.loc[2]
            ),
            "innings_2_team": self.get_team_name(
                match_details["innings"][1]["team_batting_name"]
            ),
            "innings_2_overs": f'OVERS {self.get_overs(match_details["innings"][1]["overs"])}',
            "innings_2_score": f'{match_details["innings"][1]["runs"]}/{match_details["innings"][1]["wickets"]}',
            "innings_2_bat_1_name": self.get_bat_name(innings_2_bat_df.loc[0]),
            "innings_2_bat_1_runs": self.get_bat_runs(innings_2_bat_df.loc[0]),
            "innings_2_bat_2_name": self.get_bat_name(innings_2_bat_df.loc[1]),
            "innings_2_bat_2_runs": self.get_bat_runs(innings_2_bat_df.loc[1]),
            "innings_2_bat_3_name": self.get_bat_name(innings_2_bat_df.loc[2]),
            "innings_2_bat_3_runs": self.get_bat_runs(innings_2_bat_df.loc[2]),
            "innings_2_bowl_1_name": self.get_bowl_name(innings_2_bowl_df.loc[0]),
            "innings_2_bowl_1_figures": self.get_bowler_figures(
                innings_2_bowl_df.loc[0]
            ),
            "innings_2_bowl_2_name": self.get_bowl_name(innings_2_bowl_df.loc[1]),
            "innings_2_bowl_2_figures": self.get_bowler_figures(
                innings_2_bowl_df.loc[1]
            ),
            "innings_2_bowl_3_name": self.get_bowl_name(innings_2_bowl_df.loc[2]),
            "innings_2_bowl_3_figures": self.get_bowler_figures(
                innings_2_bowl_df.loc[2]
            ),
            "result": self.get_result_string(match_details),
            "template_filename": self.get_template_filename(match_details),
            "filename": self.get_filename(match_details),
        }
        return summary_data

    def get_team_name(self, name):
        name = name.split(" - ")[0]
        if len(name) > 28:
            short_name = self.replace_strings(name).upper()
            while len(short_name) > 28:
                if " " not in short_name:
                    return short_name[:28]
                short_name = short_name.rsplit(" ", 1)[0]
            return short_name
        else:
            return self.replace_strings(name).upper()

    def get_overs(self, value):
        if float(value).is_integer():
            return str(int(float(value)))
        else:
            return value

    def get_filename(self, match_details):
        return (
            f'{match_details["match_date"].replace("/", "_")} '
            f'{self.replace_strings(match_details["home_club_name"])} '
            f'{self.replace_strings(match_details["home_team_name"])} vs '
            f'{self.replace_strings(match_details["away_club_name"])} '
            f'{self.replace_strings(match_details["away_team_name"])}'
        )

    def get_result_string(self, data):
        description = data["result_description"]
        if data["innings"][0]["team_batting_name"] in description:
            innings_1_target = self.get_revised_target(data)
            return (
                self.replace_strings(description).upper()
                + f' BY {innings_1_target - int(data["innings"][1]["runs"])} RUNS'
            )
        elif data["innings"][1]["team_batting_name"] in description:
            return (
                self.replace_strings(description).upper()
                + f' BY {10 - int(data["innings"][1]["wickets"])} WICKETS'
            )
        raise ValueError

    def get_revised_target(self, data):
        if data["innings"][1]["revised_target_runs"]:
            return int(data["innings"][1]["revised_target_runs"])
        else:
            return int(data["innings"][0]["runs"])

    def get_match_type(self, match_type):
        if match_type in self.dcl_divisions:
            return "DCL " + match_type
        else:
            return match_type

    def get_bat_name(self, bat_series):
        name = bat_series["batsman_name"]
        if len(name) > 20:
            name = name.split(" ")[0][0] + " " + name.split(" ")[1]
        return name.upper()

    def get_bowl_name(self, bat_series):
        name = bat_series["bowler_name"]
        if len(name) > 20:
            name = name.split(" ")[0][0] + " " + name.split(" ")[1]
        return name.upper()

    def replace_strings(self, string):
        return (
            string.replace(" - ", " ")
            .replace("Under ", "U")
            .replace(", Devon", "")
            .replace("Devon and County T20 Cups", "T20 XI")
            .replace("Twenty20 ", "")
            .replace("!", "")
            .replace("/", " ")
            .replace("'", "")
        )

    @staticmethod
    def get_bat_runs(bat_series):
        if np.isnan(bat_series["balls"]):
            return f'{int(bat_series["runs"])}{"*" if bat_series["how_out"] == "not out" else ""}'
        else:
            return f'{int(bat_series["runs"])}{"*" if bat_series["how_out"]=="not out" else ""} ({int(bat_series["balls"])})'

    def get_bowler_figures(self, bowl_series):
        return f'{bowl_series["wickets"]}-{bowl_series["runs"]} ({self.get_overs(bowl_series["overs"])})'


if __name__ == "__main__":
    pcms = PlayCricketMatchSummary()
    pcms.main()
