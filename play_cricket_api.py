import datetime
import os
import requests


class PlayCricketAPI:
    """
    Play cricket API token must be stored in environment variable named PLAY_CRICKET_API_TOKEN
    """

    API_TOKEN = os.environ.get("PLAY_CRICKET_API_TOKEN")
    CLUB_SITE_ID = "2641"

    def __init__(self):
        pass

    def get_match_detail(self, match_id):
        """
        Call play cricket match details API
        :param match_id: match id
        :return: json of match details
        """
        response = requests.get(
            f"http://play-cricket.com/api/v2/match_detail.json?&match_id={match_id}&api_token={self.API_TOKEN}"
        )
        return response.json()

    def get_result_summary(
        self, site_id=None, season=None, from_match_date=None, end_match_date=None
    ):
        """
        Call play cricket result summary API
        :param site_id: site (club) id
        :param season: year, defaults to current year
        :param from_match_date: from match date
        :param end_match_date: to match date
        :return: json of results
        """
        if not site_id:
            site_id = self.CLUB_SITE_ID
        if not season:
            season = datetime.datetime.now().year
        request_string = (
            f"http://play-cricket.com/api/v2/result_summary.json?site_id={site_id}"
            f"&season={season}&api_token={self.API_TOKEN}"
        )
        if from_match_date:
            request_string += f"&from_match_date={from_match_date}"
        if end_match_date:
            request_string += f"&end_match_date={end_match_date}"
        response = requests.get(request_string)
        return response.json()
