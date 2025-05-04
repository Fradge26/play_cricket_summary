import datetime
import json
import logging
import os
import shutil
import subprocess
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
        self.jpg_temp_path = os.path.join(self.script_path, "output", "jpg", "temp")
        self.jpg_sent_path = os.path.join(self.script_path, "output", "jpg", "sent")
        self.template_directory = os.path.join(
            self.script_path, "resources", "templates"
        )
        self.config = self.load_json(
            os.path.join(self.script_path, "resources", "config.json")
        )
        self.logos_directory = os.path.join(self.script_path, "resources", "logos")
        Path(self.logos_directory).mkdir(parents=True, exist_ok=True)
        Path(self.jpg_sent_path).mkdir(parents=True, exist_ok=True)
        Path(self.jpg_temp_path).mkdir(parents=True, exist_ok=True)
        Path(self.json_path).mkdir(parents=True, exist_ok=True)
        self.dcl_divisions = (
                {"PREMIER DIVISION"}
                | set(f"{a} DIVISION" for a in "ABC")
                | set(f"{a} DIVISION {d}" for a in "DEFGH" for d in ["EAST", "WEST"])
        )

        # set up logging to file
        logging.basicConfig(
            filename="pcsg.log",
            level=logging.INFO,
            format="[%(asctime)s] {%(pathname)s:%(lineno)d} %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d,%H:%M:%S",
        )
        # set up logging to console
        console = logging.StreamHandler()
        console.setLevel(logging.DEBUG)
        # set a format which is simpler for console use
        formatter = logging.Formatter("%(asctime)s - %(name)-12s: %(levelname)-8s %(message)s")
        console.setFormatter(formatter)
        # add the handler to the root logger
        logging.getLogger("").addHandler(console)
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"Starting run of play_cricket_summary_generator.py")

    def main(self):
        self.scrape_play_cricket_results()

    def load_json(self, json_path):
        with open(json_path) as json_file:
            return json.load(json_file)

    def get_play_cricket_result_ids(self):
        from_match_date = datetime.datetime.now() - datetime.timedelta(days=7)
        results = self.play_cricket_api.get_result_summary(
            site_id=self.config["play cricket club site id"],
            from_match_date=from_match_date.strftime("%d/%m/%Y"),
        )
        result_summary = results["result_summary"]
        match_ids = [m["id"] for m in result_summary if m["result"] != "M"]
        return match_ids

    def scrape_play_cricket_results(self):
        existing_summaries = self.get_sent_summaries()
        new_summaries = []
        for result_id in self.get_play_cricket_result_ids():
            new_summary = self.scrape_play_cricket_result(result_id, existing_summaries)
            if new_summary:
                new_summaries.append(new_summary)
        self.sync_summaries(new_summaries)

    def scrape_play_cricket_result(self, result_id, existing_summaries):
        if self.validate_match_detail(result_id):
            summary_data = self.get_result_data(result_id)
            if summary_data["filename"] not in existing_summaries:
                try:
                    self.get_club_logos(result_id)
                    self.write_summary_json(summary_data)
                    self.write_summary_jpg(summary_data)
                    self.logger.info(
                        f'Summary graphic generated successfully for match: {summary_data["filename"]}'
                    )
                    return os.path.join(self.jpg_temp_path, f'{summary_data["filename"]}.JPG')
                except Exception as e:
                    self.logger.warning(
                        f'Summary graphic error for match: {summary_data["filename"]} {e}'
                    )
                    return None
            else:
                self.logger.info(
                    f'Summary graphic not generated for match: {summary_data["filename"]} '
                    f"because it has been produced previously"
                )
        else:
            self.logger.info(
                f"Summary graphic not generated for match id: {result_id} because it failed validation"
            )
        return None

    def sync_summaries(self, new_summaries):
        album_name = "exeter_cc_scorecards"
        remote_path = f"gphotos:album/{album_name}"
        for path in new_summaries:
            self.logger.info(f"Uploading: {path}")
            try:
                result = subprocess.run(
                    ["rclone", "copy", path, remote_path, "--progress"],
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                shutil.copy(os.path.join(self.jpg_temp_path, path), os.path.join(self.jpg_sent_path, path))
                self.logger.info(result.stdout)
            except subprocess.CalledProcessError as e:
                self.logger.info(f"Error uploading {path}:\n{e.stderr}")

    def email_summaries(self, new_summaries):
        self.logger.info(os.environ.get("EMAIL_PASSWORD"))
        new_line = "\n"
        if new_summaries:
            self.logger.info(
                f"Summary graphics generated for {len(new_summaries)} matches"
            )
            new_matches = [os.path.basename(m) for m in new_summaries]
            try:
                send_mail(
                    host=self.config["email host"],
                    port=self.config["email port"],
                    send_from=self.config["from email address"],
                    send_to=self.config["to email addresses"],
                    subject=f'{self.config["club name"]} Match Summaries {datetime.datetime.today().strftime("%d_%m_%Y")}',
                    text=f'{self.config["club name"]} match summaries attached for the following matches;\n'
                         f"{new_line.join(new_matches)}",
                    files=new_summaries,
                )
                self.logger.info(f'Email sent to: {self.config["to email addresses"]}')
                for file in new_matches:
                    shutil.copy(os.path.join(self.jpg_temp_path, file), os.path.join(self.jpg_sent_path, file))
            except Exception as e:
                self.logger.error(
                    f"Email sending failed with the following error: {e}"
                )

        else:
            self.logger.info(f'Email not sent because there were no new summaries to send')

    def get_sent_summaries(self):
        existing_summary_set = set()
        for file in os.listdir(self.jpg_sent_path):
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
        elif not self.get_result_string(match_details):
            return False
        else:
            return True

    def write_summary_json(self, summary_data):
        with open(
                os.path.join(self.json_path, f'{summary_data["filename"]}.json'), "w"
        ) as out_file:
            out_file.write(json.dumps(summary_data, indent=4))

    def write_summary_jpg(self, summary_data, template_name=None):
        if template_name is None:
            template_name = summary_data["template_filename"]
        image = Image.open(
            os.path.join(self.template_directory, template_name)
        )
        home_logo = Image.open(os.path.join(self.logos_directory, "home_club_logo.JPG"))
        away_logo = Image.open(os.path.join(self.logos_directory, "away_club_logo.JPG"))
        home_logo = home_logo.resize((100, 100))
        away_logo = away_logo.resize((100, 100))
        image.paste(home_logo, (107, 180))
        image.paste(away_logo, (875, 180))
        draw = ImageDraw.Draw(image)
        for conf in self.config.get("text fields", []):
            font = ImageFont.truetype(
                os.path.join(
                    self.script_path, "resources", "font", "Montserrat-Regular.ttf"
                ),
                conf["scale"],
            )
            draw.text(
                (conf["x"], conf["y"]),
                summary_data[conf["field name"]],
                font=font,
                fill=tuple(conf["rgb"]),
                spacing=4,
                anchor=conf["anchor"],
                align="center",
            )
        image.save(os.path.join(self.jpg_temp_path, f'{summary_data["filename"]}.JPG'))

    def get_template_filename(self, data):
        return f"{self.get_match_template_type(data)}_{self.get_this_club_first_innings(data)}.JPG"

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

    def get_this_club_first_innings(self, data):
        if self.config["club name"].upper() in data["toss"].upper():
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
            "innings_1_bat_1_name": self.get_bat_name(innings_1_bat_df, 0),
            "innings_1_bat_1_runs": self.get_bat_runs(innings_1_bat_df, 0),
            "innings_1_bat_2_name": self.get_bat_name(innings_1_bat_df, 1),
            "innings_1_bat_2_runs": self.get_bat_runs(innings_1_bat_df, 1),
            "innings_1_bat_3_name": self.get_bat_name(innings_1_bat_df, 2),
            "innings_1_bat_3_runs": self.get_bat_runs(innings_1_bat_df, 2),
            "innings_1_bowl_1_name": self.get_bowl_name(innings_1_bowl_df, 0),
            "innings_1_bowl_1_figures": self.get_bowler_figures(innings_1_bowl_df, 0),
            "innings_1_bowl_2_name": self.get_bowl_name(innings_1_bowl_df, 1),
            "innings_1_bowl_2_figures": self.get_bowler_figures(innings_1_bowl_df, 1),
            "innings_1_bowl_3_name": self.get_bowl_name(innings_1_bowl_df, 2),
            "innings_1_bowl_3_figures": self.get_bowler_figures(innings_1_bowl_df, 2),
            "innings_2_team": self.get_team_name(match_details["innings"][1]["team_batting_name"]),
            "innings_2_overs": f'OVERS {self.get_overs(match_details["innings"][1]["overs"])}',
            "innings_2_score": f'{match_details["innings"][1]["runs"]}/{match_details["innings"][1]["wickets"]}',
            "innings_2_bat_1_name": self.get_bat_name(innings_2_bat_df, 0),
            "innings_2_bat_1_runs": self.get_bat_runs(innings_2_bat_df, 0),
            "innings_2_bat_2_name": self.get_bat_name(innings_2_bat_df, 1),
            "innings_2_bat_2_runs": self.get_bat_runs(innings_2_bat_df, 1),
            "innings_2_bat_3_name": self.get_bat_name(innings_2_bat_df, 2),
            "innings_2_bat_3_runs": self.get_bat_runs(innings_2_bat_df, 2),
            "innings_2_bowl_1_name": self.get_bowl_name(innings_2_bowl_df, 0),
            "innings_2_bowl_1_figures": self.get_bowler_figures(innings_2_bowl_df, 0),
            "innings_2_bowl_2_name": self.get_bowl_name(innings_2_bowl_df, 1),
            "innings_2_bowl_2_figures": self.get_bowler_figures(innings_2_bowl_df, 1),
            "innings_2_bowl_3_name": self.get_bowl_name(innings_2_bowl_df, 2),
            "innings_2_bowl_3_figures": self.get_bowler_figures(innings_2_bowl_df, 2),
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
        dt = datetime.datetime.strptime(match_details["match_date"], "%d/%m/%Y")
        output_date = dt.strftime("%Y_%m_%d")
        return (
            f'{output_date} '
            f'{self.replace_strings(match_details["home_club_name"])} '
            f'{self.replace_strings(match_details["home_team_name"])} vs '
            f'{self.replace_strings(match_details["away_club_name"])} '
            f'{self.replace_strings(match_details["away_team_name"])}'
        )

    def get_result_string(self, data):
        description = data["result_description"]
        if description == "Abandoned":
            return "MATCH ABANDONED"
        if data["innings"][0]["team_batting_name"] in description:
            innings_1_target = self.get_revised_target(data)
            return (
                    self.replace_strings(description).upper()
                    + f' BY {innings_1_target - int(data["innings"][1]["runs"])} RUNS'
            )
        elif data["innings"][1]["team_batting_name"] in description:
            if data["innings"][1]["wickets"] == '':
                return None
            return (
                    self.replace_strings(description).upper()
                    + f' BY {10 - int(data["innings"][1]["wickets"])} WICKETS'
            )
        return None

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

    def get_bat_name(self, bat_df, rank):
        if len(bat_df) <= rank:
            return ""
        bat_row = bat_df.loc[rank]
        name = bat_row["batsman_name"]
        if len(name) > 20:
            name = name.split(" ")[0][0] + " " + name.split(" ")[1]
        return name.upper()

    def get_bowl_name(self, bowl_df, rank):
        if len(bowl_df) <= rank:
            return ""
        bowl_row = bowl_df.loc[rank]
        name = bowl_row["bowler_name"]
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
    def get_bat_runs(bat_df, rank):
        if len(bat_df) <= rank:
            return ""
        bat_row = bat_df.loc[rank]
        if bat_row["how_out"] == "did not bat":
            return ''
        if np.isnan(bat_row["balls"]):
            return f'{int(bat_row["runs"])}{"*" if bat_row["how_out"] == "not out" else ""}'
        else:
            return f'{int(bat_row["runs"])}{"*" if bat_row["how_out"] == "not out" else ""} ({int(bat_row["balls"])})'

    def get_bowler_figures(self, bowl_df, rank):
        if len(bowl_df) <= rank:
            return ""
        bowl_row = bowl_df.loc[rank]
        return f'{bowl_row["wickets"]}-{bowl_row["runs"]} ({self.get_overs(bowl_row["overs"])})'


if __name__ == "__main__":
    pcms = PlayCricketMatchSummary()
    pcms.main()


def generate_graphic_for_flask(match_id, template_name):
    pcms = PlayCricketMatchSummary()
    pcms.jpg_sent_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "static")
    summary_data = pcms.get_result_data(match_id)
    pcms.get_club_logos(match_id)
    pcms.write_summary_json(summary_data)
    pcms.write_summary_jpg(summary_data, template_name)
    return f'{summary_data["filename"]}.JPG'
