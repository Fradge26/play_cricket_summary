## Play Cricket Match Summary Generator

### Getting Started

- Python 3.8 recommended
- install requirements: `pip install -r requirements.txt`
- Request a Play cricket API token here: https://play-cricket.ecb.co.uk/hc/en-us/requests/new
- Set environment variable: `PLAY_CRICKET_API_TOKEN`
- Set `play cricket club site id` for your club, in: `./resources/config.json`
- Set `from email address` and `to email addresses` for distribution of match summary images in: `./resources/config.json`
- Obtain app password for your email provider, for example [hotmail](https://support.microsoft.com/en-us/account-billing/using-app-passwords-with-apps-that-don-t-support-two-step-verification-5896ed9b-4263-e681-128a-a6f2979a7944) and store it in environment variable named `EMAIL_PASSWORD`
- Set `email host` and `email port` for your email provider in `./resources/config.json`
- Run script: ```python play_cricket_summary_generator.py``` will generate match summary images for all club matches in the past seven days, where; 2 innings have been completed and jpg for match has not been previously created