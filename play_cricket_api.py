import datetime

import requests


class PlayCricketAPI:
    API_TOKEN = "198ea055366910f1929b047ce86b6ea9"
    EXETER_CC_SITE_ID = "2641"

    def __init__(self):
        pass

    def get_match_detail(self, match_id):
        response = requests.get(
            f"http://play-cricket.com/api/v2/match_detail.json?&match_id={match_id}&api_token={self.API_TOKEN}"
        )
        return response.json()

    def get_result_summary(
        self, site_id=None, season=None, from_match_date=None, end_match_date=None
    ):
        if not site_id:
            site_id = self.EXETER_CC_SITE_ID
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
